"""
通用 SPA 网页抓取器——通过 Playwright 渲染后从 DOM 提取岗位列表。

适用于自建官网（字节/腾讯/美团/京东/拼多多等）。
策略：
  1. Playwright 打开页面，等待渲染
  2. 监听 XHR 响应，自动捕获含岗位数据的 JSON
  3. 如果 XHR 捕获成功，用 JSON 数据；否则从 DOM 提取
  4. 启发式选择器匹配岗位卡片
"""
from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import urljoin, urlparse

from ..base import PlaywrightScraper


class GenericWebScraper(PlaywrightScraper):
    """通用网页抓取器——自动发现岗位数据。

    优先用 XHR 拦截（最精确），失败则回退到 DOM 提取。
    """

    source_platform = "official_web"
    source_type = "official"
    rate_limit_per_min = 10
    needs_browser = True

    # 岗位列表常见的 CSS 选择器（按优先级尝试）
    ITEM_SELECTORS = [
        ".job-item", ".position-item", ".job-card", ".position-card",
        ".list-item", ".job-list li", ".position-list li",
        ".job", ".post-item", ".position",
        "tr[data-id]", "tr[data-job-id]",
        ".recruit-item", ".recruit-list li",
        ".ant-table-tbody tr", ".el-table__row",
        "[class*='job'][class*='item']", "[class*='position'][class*='item']",
        "[class*='job'][class*='card']", "[class*='position'][class*='card']",
    ]

    TITLE_SELECTORS = [
        "a.job-title", ".job-title", ".position-name", ".job-name",
        "h3 a", "h4 a", ".title a", ".name a",
        "a[href*='detail']", "a[href*='job']", "a[href*='position']",
        "a", ".title", ".name",
    ]

    async def fetch_list(self) -> list[dict]:
        """抓取岗位列表——XHR 拦截 + DOM 提取双策略。"""
        page = await self.page
        career_url = self.cfg["career_urls"].get("campus") or self.cfg["career_urls"].get("social") or list(self.cfg["career_urls"].values())[0]

        # XHR 拦截：收集所有含岗位数据的 JSON 响应
        xhr_job_data: list[dict] = []

        async def on_response(resp):
            if resp.request.resource_type not in ("xhr", "fetch"):
                return
            url = resp.url
            # 排除监控/统计类请求
            if any(k in url for k in ["monitor", "track", "log", "analytics", "captcha", "csrf", "setting"]):
                return
            try:
                body = await resp.text()
                if not body or len(body) < 50:
                    return
                data = json.loads(body)
                # 启发式：JSON 中含 job/position 列表
                job_list = self._extract_job_list_from_json(data)
                if job_list:
                    xhr_job_data.extend(job_list)
                    print(f"  [XHR捕获] {url[:80]} -> {len(job_list)} 条岗位")
            except Exception:
                pass

        page.on("response", on_response)

        # 访问页面
        print(f"  访问: {career_url}")
        try:
            await page.goto(career_url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print(f"  页面加载警告: {e}")

        # 等待渲染
        await page.wait_for_timeout(5000)

        # 滚动触发懒加载
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

        # 策略1: 如果 XHR 拦截到了数据，直接用
        if xhr_job_data:
            print(f"  XHR 拦截成功: 共 {len(xhr_job_data)} 条")
            return xhr_job_data

        # 策略2: 从 DOM 提取
        print(f"  XHR 未捕获，尝试 DOM 提取...")
        dom_items = await self._extract_from_dom(page, career_url)
        if dom_items:
            print(f"  DOM 提取成功: {len(dom_items)} 条")
            return dom_items

        print(f"  ⚠ 未能提取岗位数据")
        return []

    def _extract_job_list_from_json(self, data) -> list[dict]:
        """从 JSON 响应中递归查找岗位列表。"""
        results = []

        def search(obj, depth=0):
            if depth > 5 or not obj:
                return
            if isinstance(obj, list) and len(obj) > 0:
                first = obj[0]
                if isinstance(first, dict):
                    # 判断是否是岗位对象：含 title/position_name 等字段
                    title_keys = ["title", "name", "position_name", "job_title", "post_name", "zwmc"]
                    if any(k in first for k in title_keys):
                        results.extend(obj)
                        return
                    # 递归搜索子结构
                    for item in obj[:20]:  # 限制搜索数量
                        search(item, depth + 1)
            elif isinstance(obj, dict):
                # 检查是否有 job_list/positions 等键
                list_keys = ["job_list", "jobList", "positions", "position_list", "positionList",
                             "job_post_list", "data", "result", "records", "rows", "list", "items"]
                for k in list_keys:
                    if k in obj:
                        search(obj[k], depth + 1)
                        if results:
                            return
                # 递归搜索
                for v in obj.values():
                    if isinstance(v, (list, dict)):
                        search(v, depth + 1)
                        if results:
                            return

        search(data)
        # 标准化每条记录
        normalized = []
        for item in results:
            if not isinstance(item, dict):
                continue
            normalized.append(self._normalize_json_item(item))
        return normalized

    def _normalize_json_item(self, item: dict) -> dict:
        """把各种 JSON 字段名标准化为统一格式。"""
        # 标题字段映射
        title = (item.get("title") or item.get("name") or item.get("position_name") or
                 item.get("job_title") or item.get("post_name") or item.get("zwmc") or "")

        # 地点字段映射
        location = item.get("city") or item.get("location") or item.get("work_place") or item.get("workplace") or ""
        if isinstance(location, list):
            location_list = []
            for l in location:
                if isinstance(l, dict):
                    location_list.append(str(l.get("name", "")))
                else:
                    location_list.append(str(l))
            location = ",".join([l for l in location_list if l])

        # ID 和 URL
        job_id = str(item.get("id") or item.get("position_id") or item.get("uuid") or "")
        source_url = item.get("url") or item.get("detail_url") or ""
        if not source_url and job_id:
            source_url = f"job_id:{job_id}"

        # 描述
        desc = item.get("description") or item.get("responsibility") or item.get("job_detail") or ""
        req = item.get("requirement") or item.get("qualification") or ""

        return {
            "title": str(title).strip(),
            "title_raw": str(title).strip(),
            "location": [l.strip() for l in str(location).split(",") if l.strip()] if location else [],
            "location_raw": str(location),
            "source_url": str(source_url),
            "post_date": str(item.get("update_time") or item.get("create_time") or item.get("publish_time") or ""),
            "responsibilities": f"{desc}\n\n{req}".strip() if desc or req else "",
            "job_type": "autumn_campus",
            "_raw_json": item,  # 保留原始 JSON 供 parse_item 使用
        }

    async def _extract_from_dom(self, page, base_url: str) -> list[dict]:
        """从 DOM 提取岗位列表。"""
        return await page.evaluate(f"""() => {{
            const selectors = {json.dumps(self.ITEM_SELECTORS)};
            const titleSelectors = {json.dumps(self.TITLE_SELECTORS)};

            for (const sel of selectors) {{
                const els = document.querySelectorAll(sel);
                if (els.length === 0) continue;

                const items = [];
                for (const el of els) {{
                    let title = '', href = '', location = '', company = '', dateStr = '';

                    // 找标题
                    for (const ts of titleSelectors) {{
                        const t = el.querySelector(ts);
                        if (t) {{
                            title = t.innerText.trim();
                            href = t.href || t.getAttribute('href') || '';
                            break;
                        }}
                    }}
                    if (!title) {{
                        title = el.innerText.trim().split('\\n')[0].substring(0, 100);
                    }}
                    if (!title || title.length < 2) continue;

                    // 找地点
                    const locEl = el.querySelector('[class*="location"], [class*="city"], [class*="place"], .location, .city');
                    if (locEl) location = locEl.innerText.trim();

                    // 找公司
                    const compEl = el.querySelector('[class*="company"], .company-name, .ent-name');
                    if (compEl) company = compEl.innerText.trim();

                    // 找日期
                    const dateEl = el.querySelector('[class*="date"], [class*="time"], .date, .time');
                    if (dateEl) dateStr = dateEl.innerText.trim();

                    items.push({{
                        title: title,
                        title_raw: title,
                        location: location ? [location] : [],
                        location_raw: location,
                        company_raw: company,
                        source_url: href ? new URL(href, location.href).href : '',
                        post_date: dateStr,
                        job_type: 'autumn_campus'
                    }});
                }}
                if (items.length > 0) return items;
            }}
            return [];
        }}""")

    def parse_item(self, raw: dict) -> dict:
        """解析为统一 schema。"""
        title = raw.get("title", "").strip()
        # 判断招聘类型
        job_type = raw.get("job_type", "autumn_campus")
        title_lower = title.lower()
        if "实习" in title or "intern" in title_lower:
            job_type = "intern"

        return {
            "title": title,
            "title_raw": raw.get("title_raw", title),
            "location": raw.get("location", []),
            "location_raw": raw.get("location_raw", ""),
            "education": "",
            "experience": "应届",
            "salary_range": None,
            "salary_raw": "",
            "skills": [],
            "responsibilities": raw.get("responsibilities", ""),
            "description_html": "",
            "job_type": job_type,
            "category": "unknown",
            "ai_relevance": "unknown",
            "ai_keywords": [],
            "source_url": raw.get("source_url", ""),
            "post_date": raw.get("post_date", ""),
        }
