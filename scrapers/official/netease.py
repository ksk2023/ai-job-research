"""网易招聘直接 API 抓取器——hr.163.com/api/hr163/position/queryPage

社区已验证的明文 JSON 接口，直接 httpx 调用。
"""
from __future__ import annotations

from ..base import BaseScraper
from ..ua_pool import ua_pool
import httpx


class NetEaseScraper(BaseScraper):
    """网易招聘直连 API 抓取器。"""

    source_platform = "netease_official"
    source_type = "official"
    needs_browser = False
    rate_limit_per_min = 30

    API_URL = "https://hr.163.com/api/hr163/position/queryPage"

    async def fetch_list(self) -> list[dict]:
        results: list[dict] = []

        for type_str in ["技术类", "产品类", "设计类"]:
            for page in range(1, 6):
                try:
                    payload = {
                        "pageNumber": page,
                        "pageSize": 20,
                        "categoryStr": "",
                        "typeStr": type_str,
                        "cityStr": "",
                        "searchStr": "AI",
                    }
                    headers = {
                        **ua_pool.headers(),
                        "Content-Type": "application/json",
                        "Referer": "https://hr.163.com/campus.html",
                        "Origin": "https://hr.163.com",
                    }

                    async with httpx.AsyncClient(timeout=20) as client:
                        resp = await client.post(self.API_URL, json=payload, headers=headers)
                        data = resp.json()

                    job_list = data.get("data", {}).get("list", [])
                    if not job_list:
                        break

                    results.extend(job_list)
                    print(f"    [{type_str}] 第 {page} 页: {len(job_list)} 条")

                    if len(job_list) < 20:
                        break

                except Exception as e:
                    print(f"    [{type_str}] 第 {page} 页失败: {type(e).__name__}")
                    break

        return results

    def parse_item(self, raw: dict) -> dict:
        title = raw.get("productName", "") or raw.get("name", "")
        locations = raw.get("workPlaceNameList", [])
        if not isinstance(locations, list):
            locations = [str(locations)] if locations else []
        location = [str(l) for l in locations if l]

        education = raw.get("reqEducationName", "")
        experience = raw.get("reqWorkYearsName", "")
        department = raw.get("firstDepName", "")
        update_time = raw.get("updateTime", "")
        job_id = raw.get("id", "")

        source_url = ""
        if job_id:
            source_url = f"https://hr.163.com/campus.html?id={job_id}"

        return {
            "title": title,
            "title_raw": title,
            "location": location,
            "location_raw": ",".join(location),
            "education": education,
            "experience": experience,
            "salary_range": None,
            "salary_raw": "",
            "skills": [],
            "responsibilities": "",
            "description_html": "",
            "job_type": "autumn_campus",
            "category": "unknown",
            "ai_relevance": "unknown",
            "ai_keywords": [],
            "source_url": source_url,
            "post_date": update_time,
        }
