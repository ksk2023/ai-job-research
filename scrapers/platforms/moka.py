"""Moka 招聘平台抓取器。

Moka 是国内流行的招聘 SaaS，很多 AI 公司用它。
API: https://api.mokahr.com/v1/jobs/{company_id}
需要通过浏览器拦截获取正确的请求头（含 token）。
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from ..base import BaseScraper
from ..ua_pool import ua_pool


class MokaScraper(BaseScraper):
    """Moka 平台抓取器——通过浏览器拦截获取岗位数据。"""

    source_platform = "moka_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 10

    async def fetch_list(self) -> list[dict]:
        """用浏览器访问 Moka 招聘页，拦截岗位 API 响应。"""
        from playwright.async_api import async_playwright

        urls_config = self.cfg.get("career_urls", {})
        target_url = urls_config.get("campus") or urls_config.get("social") or ""
        if not target_url:
            print(f"  ✗ 未配置 career_urls")
            return []

        company_name = self.cfg.get("name", self.cfg["id"])
        print(f"  Moka 浏览器: {target_url}")

        captured_jobs: list[dict] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            context = await browser.new_context(
                user_agent=ua_pool.chrome_only(),
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
            )
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()

            async def on_response(response):
                try:
                    url = response.url
                    ct = response.headers.get("content-type", "")
                    if "json" not in ct.lower():
                        return
                    # Moka API 模式
                    if "mokahr.com" not in url and "api" not in url:
                        return

                    body = await response.text()
                    if not body or len(body) < 100:
                        return

                    try:
                        data = json.loads(body)
                    except Exception:
                        return

                    # 递归找岗位列表
                    jobs = self._extract_jobs_from_data(data)
                    if jobs:
                        captured_jobs.extend(jobs)
                        print(f"    [拦截] {url[:80]}... → {len(jobs)} 条")
                except Exception:
                    pass

            page.on("response", on_response)

            try:
                await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                print(f"  goto: {type(e).__name__}")

            await asyncio.sleep(5)

            # 尝试点击交互触发 API
            for i in range(8):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.5)

                # 尝试点击各种按钮
                for sel in [
                    "text=社招",
                    "text=校招",
                    "text=实习",
                    "text=下一页",
                    "text=加载更多",
                    ".next",
                    "[aria-label='next page']",
                    "button:has-text('搜索')",
                ]:
                    try:
                        el = page.locator(sel).first
                        if await el.is_visible(timeout=300):
                            await el.click(timeout=1000)
                            await asyncio.sleep(2)
                            break
                    except Exception:
                        continue

                if len(captured_jobs) > 0 and i > 4:
                    break

            await browser.close()

        # 去重
        seen_ids = set()
        unique = []
        for j in captured_jobs:
            jid = j.get("id") or j.get("title", "")
            if jid and jid not in seen_ids:
                seen_ids.add(jid)
                unique.append(j)

        print(f"  Moka: 共 {len(unique)} 条岗位")
        return unique

    def _extract_jobs_from_data(self, data: Any, depth: int = 0) -> list[dict]:
        """从 Moka API 响应递归提取岗位列表。"""
        if depth > 5:
            return []
        result: list[dict] = []

        if isinstance(data, list):
            if len(data) > 0 and isinstance(data[0], dict):
                if self._looks_like_job(data[0]):
                    return data
            for item in data:
                if isinstance(item, dict):
                    result.extend(self._extract_jobs_from_data(item, depth + 1))
            return result

        if isinstance(data, dict):
            for key in ["jobs", "list", "data", "result", "records", "rows", "postList", "jobList"]:
                if key in data and isinstance(data[key], (list, dict)):
                    sub = self._extract_jobs_from_data(data[key], depth + 1)
                    if sub:
                        result.extend(sub)
            return result

        return result

    def _looks_like_job(self, d: dict) -> bool:
        """Moka 岗位通常有 title 字段。"""
        title_keys = ["title", "name", "jobTitle", "positionName"]
        for k in title_keys:
            if k in d:
                val = d[k]
                if isinstance(val, str) and len(val) > 1:
                    return True
        return False

    def parse_item(self, raw: dict) -> dict:
        title = raw.get("title", "").strip()

        # 地点
        location_raw = ""
        for k in ["city", "location", "workPlace", "workCity", "workLocation"]:
            if k in raw and raw[k]:
                location_raw = str(raw[k])
                break
        location = [location_raw] if location_raw else []

        # 学历
        education = ""
        for k in ["education", "degree", "educationRequirement"]:
            if k in raw and raw[k]:
                education = str(raw[k])
                break

        # 薪资
        salary_raw = ""
        min_sal = raw.get("minSalary")
        max_sal = raw.get("maxSalary")
        if min_sal and max_sal:
            unit = raw.get("salaryUnit", "")
            salary_raw = f"{min_sal}-{max_sal}{unit}"
        elif min_sal:
            salary_raw = f"{min_sal}+"

        # 经验
        experience = ""
        min_exp = raw.get("minExperience")
        max_exp = raw.get("maxExperience")
        if min_exp and max_exp:
            experience = f"{min_exp}-{max_exp}年"
        elif min_exp:
            experience = f"{min_exp}年+"

        # 职责描述
        responsibilities = raw.get("description", "") or raw.get("responsibility", "")

        # 招聘类型
        title_lower = title.lower()
        job_type = "autumn_campus"
        if "实习" in title or "intern" in title_lower:
            job_type = "intern"
        elif "社招" in str(raw.get("jobType", "")):
            job_type = "social"

        # 来源 URL
        source_url = ""
        job_id = raw.get("id")
        if job_id:
            base = self.cfg.get("career_urls", {}).get("campus", "")
            if "mokahr.com" in base:
                source_url = f"https://app.mokahr.com/position/{job_id}"

        return {
            "title": title,
            "title_raw": title,
            "location": location,
            "location_raw": location_raw,
            "education": education,
            "experience": experience,
            "salary_range": (min_sal, max_sal) if min_sal and max_sal else None,
            "salary_raw": salary_raw,
            "skills": [],
            "responsibilities": responsibilities[:5000],
            "description_html": "",
            "job_type": job_type,
            "category": "unknown",
            "ai_relevance": "unknown",
            "ai_keywords": [],
            "source_url": source_url,
            "post_date": raw.get("openedAt", "") or raw.get("createdAt", ""),
        }
