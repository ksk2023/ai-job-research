"""阿里巴巴招聘抓取器——talent.alibaba.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class AlibabaScraper(BrowserAPIScraper):
    """阿里巴巴专用抓取器。"""

    source_platform = "alibaba_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8

    async def fetch_list(self) -> list[dict]:
        # 先尝试通用浏览器拦截
        results = await super().fetch_list()
        if results:
            return results

        # 尝试直接 API
        from playwright.async_api import async_playwright
        from ..ua_pool import ua_pool
        import json

        api_urls = [
            "https://talent.alibaba.com/api/job/search?keyword=AI&size=50",
            "https://talent.alibaba.com/api/job/list?keyword=AI",
        ]

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = await browser.new_context(user_agent=ua_pool.chrome_only(), locale="zh-CN")
            page = await context.new_page()

            captured: list[dict] = []
            async def on_response(resp):
                try:
                    if "json" not in resp.headers.get("content-type", "").lower():
                        return
                    body = await resp.text()
                    if not body or len(body) < 50:
                        return
                    data = json.loads(body)
                    if isinstance(data, dict):
                        jobs = data.get("data") or data.get("content") or data.get("jobs") or []
                        if isinstance(jobs, list):
                            captured.extend(jobs)
                except Exception:
                    pass

            page.on("response", on_response)

            for url in api_urls:
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(2)
                except Exception:
                    continue

            await browser.close()
            if captured:
                return [self.parse_item(j) for j in captured[:100]]

        return []
