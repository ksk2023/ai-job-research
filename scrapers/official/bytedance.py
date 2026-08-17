"""字节跳动招聘抓取器——jobs.bytedance.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class ByteDanceScraper(BrowserAPIScraper):
    """字节跳动专用抓取器。"""

    source_platform = "bytedance_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8

    async def fetch_list(self) -> list[dict]:
        # 尝试多个可能的 API 端点
        urls = self.cfg.get("career_urls", {})
        results: list[dict] = []

        # 策略1: 直接用 Playwright 访问并拦截
        base_results = await super().fetch_list()
        if base_results:
            return base_results

        # 策略2: 尝试已知的字节 API 模式
        from playwright.async_api import async_playwright
        from ..ua_pool import ua_pool

        api_candidates = [
            "https://jobs.bytedance.com/api/v1/search/?keyword=AI&limit=50",
            "https://jobs.bytedance.com/api/v1/job/list/?keyword=AI",
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
                    data = __import__("json").loads(body)
                    # 字节常见的响应结构
                    if isinstance(data, dict):
                        jobs = data.get("jobs") or data.get("data") or data.get("list") or []
                        if isinstance(jobs, list) and len(jobs) > 0:
                            captured.extend(jobs)
                except Exception:
                    pass

            page.on("response", on_response)

            for url in api_candidates:
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(2)
                except Exception:
                    continue

            await browser.close()

            if captured:
                return [self.parse_item(j) for j in captured[:100]]

        return []
