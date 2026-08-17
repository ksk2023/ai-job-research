"""外企 AI 岗位抓取器。

大多数外企用标准招聘 SaaS 平台（Greenhouse/Lever/Workday），
这些平台有公开 JSON API，无需逆向。

支持的源：
- Greenhouse: https://boards-api.greenhouse.io/v1/boards/{board}/jobs
- Lever: https://api.lever.co/v0/postings/{company}?mode=json
- Workday: 需浏览器渲染
- 自建: 各公司不同
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

import httpx

from ..base import BaseScraper
from ..ua_pool import ua_pool


# 外企招聘板配置
FOREIGN_BOARDS = {
    # AshbyHQ（需浏览器拦截 XHR）
    "openai": {
        "platform": "custom",
        "url": "https://openai.com/careers/search/",
        "name": "OpenAI",
    },
    "perplexity": {
        "platform": "custom",
        "url": "https://www.perplexity.ai/careers",
        "name": "Perplexity",
    },
    # Greenhouse 板（公开 API）
    "anthropic": {
        "platform": "greenhouse",
        "board": "anthropic",
        "name": "Anthropic",
    },
    "stability": {
        "platform": "greenhouse",
        "board": "stabilityai",
        "name": "Stability AI",
    },
    # Workday 或自建（需浏览器）
    "nvidia": {
        "platform": "custom",
        "url": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/jobFamilyGroup/Artificial-Intelligence",
        "name": "NVIDIA",
    },
    "google": {
        "platform": "custom",
        "url": "https://www.google.com/about/careers/applications/jobs/results/?location=China&q=AI",
        "name": "Google",
    },
    "microsoft": {
        "platform": "custom",
        "url": "https://jobs.microsoft.com/explore/jobs?keyword=AI&location=China",
        "name": "Microsoft",
    },
    "meta": {
        "platform": "custom",
        "url": "https://www.metacareers.com/jobs/?q=AI",
        "name": "Meta",
    },
    "amazon": {
        "platform": "custom",
        "url": "https://www.amazon.jobs/en/teams?q=AI",
        "name": "Amazon",
    },
    "apple": {
        "platform": "custom",
        "url": "https://jobs.apple.com/en-us/search?search=AI",
        "name": "Apple",
    },
}


class ForeignScraper(BaseScraper):
    """外企抓取器——按 board 配置路由。"""

    source_platform = "foreign_official"
    source_type = "official"
    rate_limit_per_min = 15
    needs_browser = False

    def __init__(self, company_cfg, cache, output_dir="data/raw"):
        super().__init__(company_cfg, cache, output_dir)
        self.board_config = FOREIGN_BOARDS.get(company_cfg["id"], {})
        self.foreign_platform = self.board_config.get("platform", "custom")

    async def fetch_list(self) -> list[dict]:
        if self.foreign_platform == "greenhouse":
            return await self._fetch_greenhouse()
        elif self.foreign_platform == "lever":
            return await self._fetch_lever()
        else:
            return await self._fetch_custom()

    async def _fetch_greenhouse(self) -> list[dict]:
        """Greenhouse 公开 API。"""
        board = self.board_config["board"]
        url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
        print(f"  Greenhouse API: {url[:80]}")
        try:
            resp = await self._request_with_retry(url)
            data = resp.json()
            jobs = data.get("jobs", [])
            print(f"  获取 {len(jobs)} 条")
            return jobs
        except Exception as e:
            print(f"  ✗ Greenhouse 失败: {type(e).__name__}: {e}")
            return []

    async def _fetch_lever(self) -> list[dict]:
        """Lever 公开 API。"""
        board = self.board_config["board"]
        url = f"https://api.lever.co/v0/postings/{board}?mode=json"
        print(f"  Lever API: {url[:80]}")
        try:
            resp = await self._request_with_retry(url)
            data = resp.json()
            # Lever 返回的可能是列表或包装在 data 里
            if isinstance(data, list):
                print(f"  获取 {len(data)} 条")
                return data
            elif isinstance(data, dict):
                postings = data.get("data", [])
                print(f"  获取 {len(postings)} 条")
                return postings
            return []
        except Exception as e:
            print(f"  ✗ Lever 失败: {type(e).__name__}: {e}")
            return []

    async def _fetch_custom(self) -> list[dict]:
        """自建外企招聘页——用浏览器 API 拦截。"""
        from scrapers.official.browser_api import BrowserAPIScraper

        url = self.board_config.get("url", "")
        if not url:
            return []

        # 创建临时配置
        temp_cfg = {
            **self.cfg,
            "career_urls": {"campus": url},
        }
        browser_scraper = BrowserAPIScraper(temp_cfg, self.cache)
        browser_scraper.source_platform = f"{self.cfg['id']}_foreign"
        return await browser_scraper.fetch_list()

    def parse_item(self, raw: dict) -> dict:
        if self.foreign_platform == "greenhouse":
            return self._parse_greenhouse(raw)
        elif self.foreign_platform == "lever":
            return self._parse_lever(raw)
        else:
            # 自建平台用 BrowserAPIScraper 的解析
            from scrapers.official.browser_api import BrowserAPIScraper

            temp_scraper = BrowserAPIScraper.__new__(BrowserAPIScraper)
            temp_scraper.cfg = self.cfg
            return temp_scraper.parse_item(raw)

    def _parse_greenhouse(self, raw: dict) -> dict:
        """Greenhouse 岗位格式。"""
        title = raw.get("title", "").strip()
        # 地点
        loc_data = raw.get("location", {})
        if isinstance(loc_data, dict):
            location_raw = loc_data.get("name", "")
        else:
            location_raw = str(loc_data)
        location = [location_raw] if location_raw else []

        # Greenhouse 的 departments
        departments = raw.get("departments", [])
        dept_names = [d.get("name", "") for d in departments if isinstance(d, dict)]

        # 职责描述
        content = raw.get("content", "") or ""

        # 招聘类型
        title_lower = title.lower()
        job_type = "social"  # 外企默认社招
        if "intern" in title_lower:
            job_type = "intern"

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
            "responsibilities": content[:5000],
            "description_html": "",
            "job_type": job_type,
            "category": "unknown",
            "ai_relevance": "unknown",
            "ai_keywords": [],
            "source_url": raw.get("absolute_url", ""),
            "post_date": raw.get("updated_at", "") or raw.get("first_published", ""),
        }

    def _parse_lever(self, raw: dict) -> dict:
        """Lever 岗位格式。"""
        title = raw.get("text", "").strip()

        # 地点
        categories = raw.get("categories", {})
        location_raw = categories.get("location", "") or categories.get("allLocations", "")
        if isinstance(location_raw, list):
            location = location_raw
            location_raw = ", ".join(location_raw)
        else:
            location = [location_raw] if location_raw else []

        # 描述
        desc_parts = []
        for key in ["description", "descriptionPlain"]:
            if raw.get(key):
                desc_parts.append(raw[key])
        responsibilities = "\n\n".join(desc_parts)

        # 招聘类型
        title_lower = title.lower()
        job_type = "social"
        if "intern" in title_lower:
            job_type = "intern"

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
            "responsibilities": responsibilities[:5000],
            "description_html": "",
            "job_type": job_type,
            "category": "unknown",
            "ai_relevance": "unknown",
            "ai_keywords": [],
            "source_url": raw.get("hostedUrl", "") or raw.get("applyUrl", ""),
            "post_date": raw.get("createdAt", "") or raw.get("updatedAt", ""),
        }
