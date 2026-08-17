"""OpenAI 招聘页抓取器。

OpenAI 用 AshbyHQ，但 API 需要鉴权。
策略：直接抓渲染后的页面 HTML，提取岗位卡片。
"""
from __future__ import annotations

import asyncio
import json
import re

from ..foreign.base_foreign import ForeignScraper


class Scraper(ForeignScraper):
    """OpenAI 专用抓取器。"""

    source_platform = "openai_foreign"
    source_type = "official"

    async def fetch_list(self) -> list[dict]:
        """从 OpenAI 招聘搜索页提取岗位卡片。"""
        from playwright.async_api import async_playwright

        url = "https://openai.com/careers/search/"
        print(f"  OpenAI: {url}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0",
                locale="en-US",
                viewport={"width": 1920, "height": 1080},
            )
            page = await ctx.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=60000)
            except Exception as e:
                print(f"  goto: {type(e).__name__}")

            await asyncio.sleep(8)

            # 滚动加载更多
            for _ in range(8):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

            # 提取所有岗位链接（openai.com/careers/{slug}/）
            jobs_data = await page.evaluate("""
                () => {
                    const jobs = [];
                    // 找所有指向岗位详情的链接
                    const links = document.querySelectorAll('a[href*="/careers/"]');
                    for (const link of links) {
                        const href = link.href;
                        // 岗位 URL 模式: /careers/{slug}/
                        const match = href.match(/\\/careers\\/([^/?#]+)\\/?$/);
                        if (!match) continue;
                        const slug = match[1];
                        // 跳过非岗位页
                        if (['search', 'emerging-talent', 'residency'].includes(slug)) continue;
                        const text = link.innerText.trim();
                        if (text && text.length > 3 && text.length < 200) {
                            jobs.push({title: text, slug: slug, url: href});
                        }
                    }
                    return jobs;
                }
            """)

            # 去重（按 slug）
            seen_slugs = set()
            unique_jobs = []
            for j in jobs_data:
                if j["slug"] not in seen_slugs:
                    seen_slugs.add(j["slug"])
                    # 清理标题（去掉导航等噪声）
                    title = j["title"].split("\n")[0].strip()
                    if len(title) > 2 and len(title) < 150:
                        unique_jobs.append({
                            "title": title,
                            "source_url": j["url"],
                            "slug": j["slug"],
                        })

            print(f"  OpenAI: 提取到 {len(unique_jobs)} 条岗位")

            # 尝试获取每条的地点信息（从卡片同级元素）
            try:
                location_data = await page.evaluate("""
                    () => {
                        const results = {};
                        // 找所有岗位卡片
                        const cards = document.querySelectorAll('[class*="job"], [class*="position"], [class*="career"]');
                        return results;
                    }
                """)
            except Exception:
                pass

            await browser.close()

        return unique_jobs

    def parse_item(self, raw: dict) -> dict:
        title = raw.get("title", "").strip()

        return {
            "title": title,
            "title_raw": title,
            "location": [],
            "location_raw": "",
            "education": "",
            "experience": "",
            "salary_range": None,
            "salary_raw": "",
            "skills": [],
            "responsibilities": "",
            "description_html": "",
            "job_type": "social",
            "category": "unknown",
            "ai_relevance": "high",  # OpenAI 全部算高相关
            "ai_keywords": ["OpenAI", "AGI"],
            "source_url": raw.get("source_url", ""),
            "post_date": "",
        }
