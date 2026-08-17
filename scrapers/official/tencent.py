"""腾讯招聘专用抓取器——直接调用公开 JSON API，无需浏览器。

API: https://careers.tencent.com/tencentcareer/api/post/Query
返回: {Code: 200, Data: {Count: N, Posts: [...]}}
"""
from __future__ import annotations

import time
from urllib.parse import urlencode

from ..base import BaseScraper


class Scraper(BaseScraper):
    source_platform = "tencent_official"
    source_type = "official"
    rate_limit_per_min = 20
    needs_browser = False

    API_URL = "https://careers.tencent.com/tencentcareer/api/post/Query"
    PAGE_SIZE = 50
    MAX_PAGES = 30  # 最多 1500 条

    async def fetch_list(self) -> list[dict]:
        results: list[dict] = []
        for page in range(self.MAX_PAGES):
            params = {
                "timestamp": str(int(time.time() * 1000)),
                "pageIndex": str(page),
                "pageSize": str(self.PAGE_SIZE),
                "keyword": "AI",
            }
            try:
                resp = await self._request_with_retry(self.API_URL, params=params)
                data = resp.json()
            except Exception as e:
                print(f"  第 {page+1} 页失败: {e}")
                break

            if data.get("Code") != 200:
                print(f"  API 返回错误: {data}")
                break

            posts = data.get("Data", {}).get("Posts", []) or []
            total = data.get("Data", {}).get("Count", 0)
            if not posts:
                break

            results.extend(posts)
            print(f"  第 {page+1} 页: {len(posts)} 条（累计 {len(results)}/{total}）")

            if len(results) >= total or len(posts) < self.PAGE_SIZE:
                break

            import asyncio
            await asyncio.sleep(1.5)

        return results

    def parse_item(self, raw: dict) -> dict:
        title = raw.get("RecruitPostName", "").strip()
        location_raw = raw.get("LocationName", "") or raw.get("CountryName", "")
        # 腾讯地点格式如 "中国-北京-北京" 或 "Japan-Tokyo-Business Tower"
        location = []
        if location_raw:
            parts = [p.strip() for p in location_raw.split("-") if p.strip()]
            # 取最后一个有意义的城市名
            if parts:
                location = [parts[-1]]

        # 招聘类型：腾讯 API 有 CategoryName 字段
        category_name = raw.get("CategoryName", "")
        job_type = "autumn_campus"  # 默认秋招
        if "实习" in title or "intern" in title.lower():
            job_type = "intern"
        elif "社招" in category_name or "experienced" in category_name.lower():
            job_type = "social"

        # 详情 URL
        post_id = raw.get("PostId", "")
        source_url = f"https://careers.tencent.com/jobdesc.html?postId={post_id}" if post_id else ""

        return {
            "title": title,
            "title_raw": title,
            "location": location,
            "location_raw": location_raw,
            "education": "",
            "experience": "",
            "salary_range": None,
            "salary_raw": "",
            "skills": [],
            "responsibilities": raw.get("Responsibility", "") or "",
            "description_html": "",
            "job_type": job_type,
            "category": "unknown",
            "ai_relevance": "unknown",
            "ai_keywords": [],
            "source_url": source_url,
            "post_date": raw.get("LastUpdateTime", "") or raw.get("PublishDate", ""),
        }
