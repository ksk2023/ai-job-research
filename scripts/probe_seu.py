"""探测 91job 网站真实结构——用 Playwright 渲染后 dump HTML。"""
import asyncio
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

        url = "https://seu.91job.org.cn/sub-station/listJob?xxdm=10286"
        print(f"访问: {url}")
        resp = await page.goto(url, wait_until="networkidle", timeout=60000)
        print(f"状态码: {resp.status if resp else 'N/A'}")
        print(f"页面标题: {await page.title()}")

        # 等待列表渲染
        await page.wait_for_timeout(3000)

        # 保存完整 HTML
        html = await page.content()
        out = PROJECT_ROOT / "data" / "raw" / "_probe_seu_91job.html"
        out.write_text(html, encoding="utf-8")
        print(f"HTML 已保存: {out} ({len(html)} 字符)")

        # 打印关键结构信息
        info = await page.evaluate("""() => {
            const result = {};
            // 找出所有可能的列表容器
            result.candidates = [];
            for (const sel of ['.job-list', '.position-list', '.list-job', '.job-item', '.position-item', 'table tr', '.list-item', '.recruit-list', '.job', '.post-item']) {
                const els = document.querySelectorAll(sel);
                if (els.length > 0) result.candidates.push({selector: sel, count: els.length});
            }
            // 找出所有 a 链接中含 viewJob 或 detail 的
            result.detail_links = [];
            document.querySelectorAll('a[href]').forEach(a => {
                const href = a.getAttribute('href');
                if (href && (href.includes('viewJob') || href.includes('detail') || href.includes('job/'))) {
                    result.detail_links.push({href: href, text: a.innerText.trim().substring(0, 50)});
                }
            });
            // 找出可能的分页
            result.pagination = [];
            for (const sel of ['.pagination', '.page-nav', '.pager', '.page-list', '.pagination-wrap']) {
                const els = document.querySelectorAll(sel);
                if (els.length > 0) result.pagination.push({selector: sel, html: els[0].outerHTML.substring(0, 200)});
            }
            // 看看有没有 script 含 jobList
            result.scripts_with_data = [];
            document.querySelectorAll('script').forEach(s => {
                const text = s.innerText;
                if (text && (text.includes('jobList') || text.includes('positionList') || text.includes('window.') && text.includes('data'))) {
                    result.scripts_with_data.push(text.substring(0, 500));
                }
            });
            return result;
        }""")
        import json
        print("\n=== 探测结果 ===")
        print(json.dumps(info, ensure_ascii=False, indent=2))

        # 截图
        await page.screenshot(path=str(PROJECT_ROOT / "data" / "raw" / "_probe_seu_91job.png"), full_page=True)
        print("\n截图已保存: data/raw/_probe_seu_91job.png")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(probe())
