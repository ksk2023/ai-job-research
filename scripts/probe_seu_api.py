"""深入探测 91job——监听 XHR 请求，找出数据 API。"""
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright


async def probe():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="zh-CN",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        # 监听所有网络请求
        api_calls = []
        async def on_request(req):
            if req.resource_type in ("xhr", "fetch"):
                api_calls.append({"url": req.url, "method": req.method, "type": req.resource_type})

        page.on("request", on_request)

        # 也监听响应
        api_responses = []
        async def on_response(resp):
            if resp.request.resource_type in ("xhr", "fetch"):
                try:
                    body = await resp.text()
                    api_responses.append({
                        "url": resp.url,
                        "status": resp.status,
                        "body_preview": body[:2000] if body else "",
                        "body_len": len(body) if body else 0,
                    })
                except Exception:
                    api_responses.append({"url": resp.url, "status": resp.status, "error": "无法读取 body"})

        page.on("response", on_response)

        url = "https://seu.91job.org.cn/sub-station/listJob?xxdm=10286"
        print(f"访问: {url}")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        print(f"页面标题: {await page.title()}")

        # 等待更长时间
        await page.wait_for_timeout(5000)

        # 尝试滚动触发加载
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(3000)

        print(f"\n=== XHR/Fetch 请求 ({len(api_calls)}) ===")
        for c in api_calls:
            print(f"  [{c['method']}] {c['url']}")

        print(f"\n=== XHR/Fetch 响应 ({len(api_responses)}) ===")
        for r in api_responses:
            print(f"\n  [{r.get('status')}] {r['url']}")
            if r.get("body_preview"):
                print(f"  预览: {r['body_preview'][:500]}")

        # 最后再看看页面内容
        text = await page.evaluate("document.body.innerText")
        print(f"\n=== 页面文本内容（前 1000 字符）===")
        print(text[:1000])

        await browser.close()


if __name__ == "__main__":
    asyncio.run(probe())
