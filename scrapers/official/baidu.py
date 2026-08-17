"""百度招聘直接 API 抓取器——talent.baidu.com/httservice/getPostListNew

社区已验证的明文 JSON 接口，无需 Playwright，直接 httpx 调用。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import httpx

from ..base import BaseScraper
from ..ua_pool import ua_pool


class BaiduScraper(BaseScraper):
    """百度招聘直连 API 抓取器。"""

    source_platform = "baidu_official"
    source_type = "official"
    needs_browser = False
    rate_limit_per_min = 30

    API_URL = "https://talent.baidu.com/httservice/getPostListNew"

    async def fetch_list(self) -> list[dict]:
        """直接调用百度招聘 API。"""
        results: list[dict] = []

        for recruit_type, job_type in [("CAMPUS", "autumn_campus"), ("SOCIAL", "social")]:
            for page in range(1, 6):  # 抓前5页
                try:
                    params = {
                        "recruitType": recruit_type,
                        "pageSize": 20,
                        "curPage": page,
                        "keyWord": "AI",
                    }
                    headers = {
                        **ua_pool.headers(),
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Referer": f"https://talent.baidu.com/jobs/{'campus' if recruit_type == 'CAMPUS' else 'social'}-list?search=AI",
                        "Origin": "https://talent.baidu.com",
                    }

                    async with httpx.AsyncClient(timeout=20) as client:
                        resp = await client.post(self.API_URL, data=params, headers=headers)
                        data = resp.json()

                    job_list = data.get("data", {}).get("list", [])
                    if not job_list:
                        break

                    results.extend(job_list)
                    print(f"    [{recruit_type}] 第 {page} 页: {len(job_list)} 条")

                    if len(job_list) < 20:
                        break

                except Exception as e:
                    print(f"    [{recruit_type}] 第 {page} 页失败: {type(e).__name__}")
                    break

        return results

    def parse_item(self, raw: dict) -> dict:
        title = raw.get("name", "")
        location_raw = raw.get("workPlace", "")
        location = []
        if location_raw:
            if "," in location_raw:
                location = [p.strip() for p in location_raw.split(",") if p.strip()]
            else:
                location = [location_raw]

        education = raw.get("education", "")
        responsibilities = raw.get("serviceCondition", "") or raw.get("workContent", "")
        post_date = raw.get("publishDate", "")
        post_id = raw.get("postId", "")

        source_url = ""
        if post_id:
            source_url = f"https://talent.baidu.com/jobs/social-list/detail/{post_id}"

        return {
            "title": title,
            "title_raw": title,
            "location": location,
            "location_raw": location_raw,
            "education": education,
            "experience": "",
            "salary_range": None,
            "salary_raw": "",
            "skills": [],
            "responsibilities": responsibilities,
            "description_html": "",
            "job_type": "autumn_campus",
            "category": "unknown",
            "ai_relevance": "unknown",
            "ai_keywords": [],
            "source_url": source_url,
            "post_date": post_date,
        }
