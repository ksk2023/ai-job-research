"""Moka 招聘平台 httpx 直连抓取器。

Moka 的前端 API 是公开的 GET 接口，可以直接调用：
https://app.mokahr.com/api/outer/ats-apply/website/job-list

从 career_urls 中提取 company_slug，直接请求 API。
"""
from __future__ import annotations

import re
from typing import Any

import httpx

from ..base import BaseScraper
from ..ua_pool import ua_pool


class MokaDirectScraper(BaseScraper):
    """Moka 平台 httpx 直连抓取器——无需浏览器。"""

    source_platform = "moka_official"
    source_type = "official"
    needs_browser = False
    rate_limit_per_min = 20

    async def fetch_list(self) -> list[dict]:
        """直接调用 Moka API。"""
        urls_config = self.cfg.get("career_urls", {})
        target_url = urls_config.get("campus") or urls_config.get("social") or ""
        if not target_url:
            return []

        # 从 URL 提取 company slug 和 recruitment type
        # 例: https://app.mokahr.com/campus-recruitment/kuaishou/
        # 例: https://app.mokahr.com/campus-recruitment/megviihr/38642
        # 例: https://joinus.cambricon.com/apply/cambricon
        company_slug = ""
        recruit_type = "campus"

        if "mokahr.com" in target_url:
            # 提取 slug
            match = re.search(r'/(?:campus|social)-recruitment/([^/]+)', target_url)
            if match:
                company_slug = match.group(1)
            if "social" in target_url:
                recruit_type = "social"
        elif "joinus.cambricon.com" in target_url or "/apply/" in target_url:
            # 自定义域名 Moka 站点
            match = re.search(r'/apply/([^/]+)', target_url)
            if match:
                company_slug = match.group(1)

        if not company_slug:
            # 用公司 name_en 做回退
            company_slug = self.cfg.get("name_en", "").lower().replace(" ", "")

        # 尝试多个 API 格式
        api_urls = [
            f"https://app.mokahr.com/api/outer/ats-apply/website/job-list?recruitType={recruit_type}&page=1&size=30&companySlug={company_slug}",
            f"https://app.mokahr.com/api/outer/ats-apply/website/social-job-list?page=1&size=30&companySlug={company_slug}",
            f"https://app.mokahr.com/api/outer/ats-apply/website/campus-job-list?page=1&size=30&companySlug={company_slug}",
        ]

        headers = {
            **ua_pool.headers(),
            "Accept": "application/json, text/plain, */*",
            "Referer": target_url,
        }

        results: list[dict] = []
        for api_url in api_urls:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(api_url, headers=headers)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()

                job_list = data.get("data", {}).get("jobList", [])
                if not job_list:
                    job_list = data.get("data", {}).get("list", [])
                if not job_list and isinstance(data.get("data"), list):
                    job_list = data["data"]

                if job_list and len(job_list) > 0:
                    results.extend(job_list)
                    print(f"    [Moka API] {api_url[:60]}... → {len(job_list)} 条")
                    break

            except Exception as e:
                print(f"    [Moka API] {type(e).__name__}")
                continue

        # 翻页
        if results:
            page = 2
            while len(results) > 0 and page <= 10:
                try:
                    paginated_url = api_url.replace("page=1", f"page={page}")
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.get(paginated_url, headers=headers)
                        data = resp.json()
                    job_list = data.get("data", {}).get("jobList", [])
                    if not job_list:
                        break
                    results.extend(job_list)
                    print(f"    [Moka API] 第 {page} 页: {len(job_list)} 条")
                    page += 1
                except Exception:
                    break

        return results

    def parse_item(self, raw: dict) -> dict:
        title = raw.get("title", "") or raw.get("jobTitle", "") or raw.get("name", "")
        location_raw = ""
        for k in ["city", "location", "workPlace", "workCity", "workLocation", "cityName"]:
            if k in raw and raw[k]:
                val = raw[k]
                if isinstance(val, list):
                    location_raw = ",".join(str(v) for v in val if v)
                else:
                    location_raw = str(val)
                break
        location = [l.strip() for l in location_raw.split(",") if l.strip()] if location_raw else []

        education = ""
        for k in ["education", "degree", "educationRequirement", "educationName"]:
            if k in raw and raw[k]:
                education = str(raw[k])
                break

        # 职责描述
        responsibilities = raw.get("description", "") or raw.get("responsibility", "") or raw.get("jobDescription", "")

        # 招聘类型
        job_type = "autumn_campus"
        title_lower = title.lower()
        if "实习" in title or "intern" in title_lower:
            job_type = "intern"

        # 来源 URL
        source_url = ""
        job_id = raw.get("id") or raw.get("jobId")
        if job_id:
            base_url = self.cfg.get("career_urls", {}).get("campus", "")
            source_url = f"{base_url}?jobId={job_id}"

        return {
            "title": title,
            "title_raw": title,
            "location": location,
            "location_raw": location_raw,
            "education": education,
            "experience": raw.get("experience", ""),
            "salary_range": None,
            "salary_raw": raw.get("salary", ""),
            "skills": [],
            "responsibilities": responsibilities[:5000] if responsibilities else "",
            "description_html": "",
            "job_type": job_type,
            "category": "unknown",
            "ai_relevance": "unknown",
            "ai_keywords": [],
            "source_url": source_url,
            "post_date": raw.get("openedAt", "") or raw.get("publishDate", "") or raw.get("createdAt", ""),
        }
