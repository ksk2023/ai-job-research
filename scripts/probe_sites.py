"""并行探测多个招聘官网的 API 结构——找出可直连的 JSON 接口。"""
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright


SITES = [
    {
        "id": "zhipu_feishu",
        "name": "智谱AI（飞书招聘）",
        "url": "https://zhipu-ai.jobs.feishu.cn/zhipucampus/position/list",
        "api_hints": ["/api/v1/search/job/posts", "/api/v1/job/list"],
    },
    {
        "id": "bytedance",
        "name": "字节跳动官网",
        "url": "https://jobs.bytedance.com/campus/position?keywords=AI&project=7525009396952582407&type=2",
        "api_hints": ["/api/v1/job/list", "/api/v1/search/positions"],
    },
    {
        "id": "sensetime_beisen",
        "name": "商汤（北森）",
        "url": "https://hr.sensetime.com/SU604c56f9bef57c3d1a752c60/pb/school.html",
        "api_hints": ["/api/", "/pb/"],
    },
]


async def probe_one(playwright, site):
    """探测单个站点。"""
    print(f"\n{'='*60}")
    print(f"探测: {site['name']}")
    print(f"URL: {site['url']}")
    print('='*60)

    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        locale="zh-CN",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    )
    page = await context.new_page()

    api_calls = []
    api_responses = []

    def on_request(req):
        if req.resource_type in ("xhr", "fetch"):
            api_calls.append({"url": req.url, "method": req.method})

    async def on_response(resp):
        if resp.request.resource_type in ("xhr", "fetch"):
            try:
                body = await resp.text()
                api_responses.append({
                    "url": resp.url,
                    "status": resp.status,
                    "body": body[:3000] if body else "",
                    "body_len": len(body) if body else 0,
                })
            except Exception as e:
                api_responses.append({"url": resp.url, "status": resp.status, "error": str(e)})

    page.on("request", on_request)
    page.on("response", on_response)

    try:
        await page.goto(site["url"], wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)
        # 滚动触发加载
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(3000)
    except Exception as e:
        print(f"  访问失败: {e}")

    print(f"\nXHR/Fetch 请求 ({len(api_calls)}):")
    for c in api_calls:
        print(f"  [{c['method']}] {c['url'][:120]}")

    print(f"\nXHR/Fetch 响应含数据 ({len(api_responses)}):")
    for r in api_responses:
        url = r["url"]
        body = r.get("body", "")
        # 只打印看起来含岗位数据的响应
        is_data = any(k in body for k in ["job", "position", "职位", "岗位", "title", "list"]) and r.get("body_len", 0) > 100
        if is_data:
            print(f"\n  [{r['status']}] {url[:120]}")
            print(f"  body_len={r.get('body_len')}")
            print(f"  预览: {body[:800]}")

    # 保存到文件供后续分析
    out = PROJECT_ROOT / "data" / "raw" / f"_probe_{site['id']}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"site": site, "api_calls": api_calls, "api_responses": api_responses}, f, ensure_ascii=False, indent=2)
    print(f"\n  已保存探测结果: {out}")

    await browser.close()


async def main():
    async with async_playwright() as p:
        for site in SITES:
            await probe_one(p, site)


if __name__ == "__main__":
    asyncio.run(main())
