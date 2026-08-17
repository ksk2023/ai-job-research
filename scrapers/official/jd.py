"""京东招聘直接 API 抓取器——campus.jd.com/api/wx/position/index

岗位列表接口为明文 GET JSON。
"""
from __future__ import annotations

from ..base import BaseScraper
from ..ua_pool import ua_pool
import httpx


class JDScraper(BaseScraper):
    """京东招聘直连 API 抓取器。"""

    source_platform = "jd_official"
    source_type = "official"
    needs_browser = False
    rate_limit_per_min = 30

    API_URL = "https://campus.jd.com/api/wx/position/index"

    async def fetch_list(self) -> list[dict]:
        results: list[dict] = []

        for page in range(1, 11):
            try:
                params = {
                    "pageNum": page,
                    "pageSize": 20,
                    "keyword": "AI",
                    "emplErp": "",
                }
                headers = {
                    **ua_pool.headers(),
                    "Referer": "https://campus.jd.com/",
                }

                async with httpx.AsyncClient(timeout=20) as client:
                    resp = await client.get(self.API_URL, params=params, headers=headers)
                    data = resp.json()

                job_list = data.get("data", [])
                if not job_list:
                    # 也许是另一种结构
                    job_list = data.get("data", {}).get("list", []) if isinstance(data.get("data"), dict) else []
                if not job_list:
                    break

                results.extend(job_list)
                print(f"    第 {page} 页: {len(job_list)} 条")

                if len(job_list) < 20:
                    break

            except Exception as e:
                print(f"    第 {page} 页失败: {type(e).__name__}")
                break

        return results

    def parse_item(self, raw: dict) -> dict:
        title = raw.get("name", "") or raw.get("positionName", "")
        location_raw = raw.get("workPlace", "") or raw.get("cityName", "")
        location = []
        if location_raw:
            if "/" in location_raw:
                location = [p.strip() for p in location_raw.split("/") if p.strip()]
            elif "," in location_raw:
                location = [p.strip() for p in location_raw.split(",") if p.strip()]
            else:
                location = [location_raw]

        return {
            "title": title,
            "title_raw": title,
            "location": location,
            "location_raw": location_raw,
            "education": raw.get("education", ""),
            "experience": "",
            "salary_range": None,
            "salary_raw": "",
            "skills": [],
            "responsibilities": raw.get("description", ""),
            "description_html": "",
            "job_type": "autumn_campus",
            "category": "unknown",
            "ai_relevance": "unknown",
            "ai_keywords": [],
            "source_url": raw.get("url", ""),
            "post_date": raw.get("publishDate", ""),
        }
