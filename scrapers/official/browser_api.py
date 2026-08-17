"""基于 Playwright 的通用 API 拦截抓取器。

策略：用真实浏览器访问招聘页面，监听所有 XHR/fetch 网络响应，
自动识别并提取包含岗位数据的 JSON 响应，无需逆向 API。

优势：绕过反爬、自动适配各种 API 格式、无需逆向签名。
"""
from __future__ import annotations

import asyncio
import json
import random
import re
from datetime import datetime
from typing import Any

from ..base import BaseScraper
from ..ua_pool import ua_pool


class BrowserAPIScraper(BaseScraper):
    """通用浏览器 API 拦截抓取器。

    使用方式：
      1. 在 companies.json 配置 career_urls
      2. 设置 platform = "custom"
      3. 本抓取器作为 custom 的默认回退

    工作流程：
      1. Playwright 打开页面（带反检测）
      2. 监听所有 XHR/fetch 响应
      3. 滚动、点击"加载更多"、翻页
      4. 从响应中提取岗位数据
    """

    source_platform = "browser_api"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 10

    # 拦截到的岗位数据
    MAX_SCROLL = 15  # 最多滚动次数
    MAX_WAIT = 30  # 最长等待秒数

    async def fetch_list(self) -> list[dict]:
        """用 Playwright 打开页面，拦截 API 响应。"""
        from playwright.async_api import async_playwright

        urls_config = self.cfg.get("career_urls", {})
        # 优先 campus，其次 intern，最后 social
        target_url = urls_config.get("campus") or urls_config.get("intern") or urls_config.get("social")
        if not target_url:
            print(f"  ✗ 未配置 career_urls")
            return []

        company_name = self.cfg.get("name", self.cfg["id"])
        print(f"  浏览器打开: {target_url}")

        captured_jobs: list[dict] = []
        captured_raw: list[dict] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-infobars",
                    "--window-size=1920,1080",
                    "--start-maximized",
                ],
            )
            context = await browser.new_context(
                user_agent=ua_pool.chrome_only(),
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                extra_http_headers={
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
                window.chrome = {runtime: {}};
                // 覆盖 permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)
            page = await context.new_page()

            # 拦截所有请求类型（不只是 XHR）
            async def on_response(response):
                """拦截所有响应，找岗位数据。"""
                try:
                    url = response.url
                    ct = response.headers.get("content-type", "")
                    if "json" not in ct.lower():
                        return
                    if any(url.endswith(ext) for ext in [".js", ".css", ".png", ".jpg", ".svg", ".woff", ".map"]):
                        return

                    body = await response.text()
                    if not body or len(body) < 50:
                        return

                    try:
                        data = json.loads(body)
                    except Exception:
                        return

                    jobs = self._extract_jobs(data)
                    if jobs:
                        captured_raw.append({
                            "url": url[:200],
                            "status": response.status,
                            "jobs": jobs,
                        })
                        print(f"    [拦截] {url[:80]}... → {len(jobs)} 条岗位")
                except Exception:
                    pass

            page.on("response", on_response)
            page.on("requestfailed", lambda req: None)

            # 访问页面
            try:
                await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            except Exception as e:
                print(f"  goto 错误: {type(e).__name__}")

            # 等待初始渲染
            await asyncio.sleep(4)

            # 模拟人类行为：随机滚动 + 等待
            for i in range(self.MAX_SCROLL):
                try:
                    # 随机滚动距离
                    scroll_distance = random.randint(300, 800)
                    await page.evaluate(f"window.scrollBy(0, {scroll_distance})")
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(1.0, 2.0))

                # 尝试点击"加载更多"或"下一页"
                try:
                    for sel in [
                        "text=加载更多", "text=下一页", "text=更多岗位",
                        "text=查看更多", "text=加载更多岗位",
                        ".next", ".load-more", "[aria-label='next']",
                        "button:has-text('下一页')", "button:has-text('加载更多')",
                        "[class*='load-more']", "[class*='next-page']",
                        "[class*='loadMore']", "[class*='nextPage']",
                    ]:
                        try:
                            el = page.locator(sel).first
                            if await el.is_visible(timeout=500):
                                await el.click(timeout=1000)
                                print(f"    [点击] {sel}")
                                await asyncio.sleep(random.uniform(1.5, 2.5))
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

                # 提前结束条件
                if len(captured_raw) > 0 and i > 5:
                    last_count = sum(len(r["jobs"]) for r in captured_raw)
                    await asyncio.sleep(1)
                    new_count = sum(len(r["jobs"]) for r in captured_raw)
                    if new_count == last_count:
                        break

            # 如果没拦截到 API，尝试从页面 HTML 中提取岗位卡片
            if not captured_raw:
                print(f"  未拦截到 API，尝试从页面 HTML 提取岗位卡片...")
                html_jobs = await self._extract_from_html(page)
                if html_jobs:
                    captured_raw.append({
                        "url": target_url,
                        "status": 200,
                        "jobs": html_jobs,
                    })
                    print(f"    [HTML] 提取到 {len(html_jobs)} 条岗位")

            await browser.close()

        # 合并所有拦截到的岗位（去重）
        seen_ids = set()
        all_jobs: list[dict] = []
        for r in captured_raw:
            for job in r["jobs"]:
                key = json.dumps(job, sort_keys=True, ensure_ascii=False)
                if key not in seen_ids:
                    seen_ids.add(key)
                    all_jobs.append(job)

        print(f"  拦截到 {len(captured_raw)} 个 API 响应，共 {len(all_jobs)} 条去重岗位")
        return all_jobs

    async def _extract_from_html(self, page) -> list[dict]:
        """从页面 HTML 中提取岗位卡片（兜底方案）。

        尝试多种常见选择器模式。
        """
        jobs = []
        try:
            # 策略 1: 找所有带岗位相关 class 的元素
            selectors = [
                # 常见岗位列表容器
                ".job-item", ".position-item", ".job-card", ".position-card",
                ".job-list li", ".position-list li", ".jobs-list li",
                ".recruit-list li", ".campus-list li",
                "[class*='job-item']", "[class*='position-item']",
                "[class*='JobItem']", "[class*='PositionItem']",
                "[class*='job-card']", "[class*='position-card']",
                "[class*='JobCard']", "[class*='PositionCard']",
                ".list-item", ".card-item",
            ]
            for sel in selectors:
                try:
                    elements = await page.query_selector_all(sel)
                    if elements and len(elements) > 2:
                        print(f"    [HTML] 选择器 '{sel}' 匹配 {len(elements)} 个元素")
                        for el in elements:
                            try:
                                text = await el.inner_text()
                                # 解析文本：第一行通常是标题
                                lines = [l.strip() for l in text.split("\n") if l.strip()]
                                if lines:
                                    title = lines[0]
                                    # 找地点（含常见城市名）
                                    location = ""
                                    for line in lines:
                                        for city in ["北京", "上海", "广州", "深圳", "杭州", "成都",
                                                     "南京", "武汉", "西安", "苏州", "厦门", "长沙",
                                                     "青岛", "大连", "天津", "重庆", "济南"]:
                                            if city in line:
                                                location = city
                                                break
                                        if location:
                                            break
                                    if len(title) > 2 and len(title) < 100:
                                        jobs.append({
                                            "title": title,
                                            "location": location or "",
                                            "_source": "html",
                                        })
                            except Exception:
                                continue
                        if jobs:
                            break
                except Exception:
                    continue

            # 策略 2: 提取 Next.js __NEXT_DATA__ 中的岗位数据
            if not jobs:
                try:
                    next_data = await page.evaluate("""
                        () => {
                            const el = document.getElementById('__NEXT_DATA__');
                            if (el) return JSON.parse(el.textContent);
                            return null;
                        }
                    """)
                    if next_data:
                        # 递归找岗位列表
                        extracted = self._extract_jobs(next_data)
                        if extracted:
                            jobs.extend(extracted)
                            print(f"    [HTML] __NEXT_DATA__ 提取到 {len(extracted)} 条")
                except Exception:
                    pass

        except Exception as e:
            print(f"    [HTML] 提取失败: {type(e).__name__}: {e}")

        return jobs[:200]  # 限制数量

    def _extract_jobs(self, data: Any, depth: int = 0) -> list[dict]:
        """从 JSON 数据递归提取岗位列表。

        判定规则：列表中每个 dict 至少含标题类字段。
        """
        if depth > 5:
            return []
        result: list[dict] = []

        if isinstance(data, list):
            # 看是否是岗位列表
            if len(data) > 0 and isinstance(data[0], dict):
                if self._looks_like_job(data[0]):
                    return data
            # 否则递归
            for item in data:
                if isinstance(item, dict):
                    result.extend(self._extract_jobs(item, depth + 1))
            return result

        if isinstance(data, dict):
            # 看是否有明确的岗位列表字段
            for key in ["Posts", "posts", "job_post_list", "list", "rows", "records",
                        "jobs", "positions", "Data", "List", "data", "result", "items"]:
                if key in data and isinstance(data[key], (list, dict)):
                    sub = self._extract_jobs(data[key], depth + 1)
                    if sub:
                        result.extend(sub)
            return result

        return result

    def _looks_like_job(self, d: dict) -> bool:
        """判断一个 dict 是否是岗位记录。"""
        title_keys = ["title", "name", "RecruitPostName", "positionName", "job_title",
                      "postName", "recruitName", "zwmc", "gwmc", "posName", "PositionName"]
        for k in title_keys:
            if k in d:
                val = d[k]
                if isinstance(val, str) and len(val) > 1 and len(val) < 200:
                    # 排除一些明显不是岗位名的值
                    if not any(x in val.lower() for x in ["http", "success", "error", "null"]):
                        return True
        return False

    def parse_item(self, raw: dict) -> dict:
        """把拦截到的原始岗位数据解析为统一 schema。

        自动尝试多种字段名。
        """
        # 标题
        title = ""
        for k in ["title", "name", "RecruitPostName", "positionName", "job_title",
                  "postName", "recruitName", "zwmc", "gwmc", "posName", "PositionName",
                  "position_name", "recruit_post_name"]:
            if k in raw and raw[k] and isinstance(raw[k], str):
                title = raw[k].strip()
                break

        # 地点
        location_raw = ""
        for k in ["LocationName", "location", "city", "workPlace", "workplace",
                  "CityName", "cityName", "work_city", "workLocation", "gpsName",
                  "workAddress", "address"]:
            if k in raw and raw[k]:
                location_raw = str(raw[k])
                break

        location = []
        if location_raw:
            # 处理多种格式
            if "-" in location_raw:
                parts = [p.strip() for p in location_raw.split("-") if p.strip()]
                if parts:
                    location = [parts[-1]]  # 取城市部分
            elif "," in location_raw:
                location = [p.strip() for p in location_raw.split(",") if p.strip()]
            else:
                location = [location_raw]

        # 招聘类型
        title_lower = title.lower()
        category_name = str(raw.get("CategoryName", "") or raw.get("category", ""))
        job_type = "autumn_campus"
        if "实习" in title or "intern" in title_lower:
            job_type = "intern"
        elif "社招" in category_name or "experienced" in category_name.lower():
            job_type = "social"

        # 学历
        education = ""
        for k in ["education", "degree", "educational", "xl", "xlyq"]:
            if k in raw and raw[k]:
                education = str(raw[k])
                break

        # 技能要求
        skills = []
        for k in ["skill", "skills", "technology", "tags", "labels"]:
            if k in raw and raw[k]:
                val = raw[k]
                if isinstance(val, list):
                    skills = [str(s) for s in val]
                elif isinstance(val, str):
                    skills = [s.strip() for s in val.split(",") if s.strip()]
                break

        # 职责描述
        responsibilities = ""
        for k in ["Responsibility", "responsibility", "description", "jobDesc",
                  "job_desc", "duty", "content", "gwzz", "zwyx"]:
            if k in raw and raw[k]:
                responsibilities = str(raw[k])
                break

        # 来源 URL
        source_url = ""
        post_id = raw.get("PostId") or raw.get("id") or raw.get("postId") or raw.get("positionId")
        if post_id:
            # 多种详情页 URL 模式
            base_urls = self.cfg.get("career_urls", {})
            campus_url = base_urls.get("campus", "")
            if "tencent" in campus_url:
                source_url = f"https://careers.tencent.com/jobdesc.html?postId={post_id}"
            elif "feishu" in campus_url:
                domain = campus_url.split("/")[2] if "/" in campus_url else ""
                source_url = f"https://{domain}/position/detail/{post_id}"
            else:
                source_url = campus_url

        # 发布日期
        post_date = ""
        for k in ["LastUpdateTime", "PublishDate", "publishDate", "updateTime",
                  "createTime", "post_date", "publishTime"]:
            if k in raw and raw[k]:
                post_date = str(raw[k])
                break

        return {
            "title": title,
            "title_raw": title,
            "location": location,
            "location_raw": location_raw,
            "education": education,
            "experience": "",
            "salary_range": None,
            "salary_raw": "",
            "skills": skills,
            "responsibilities": responsibilities,
            "description_html": "",
            "job_type": job_type,
            "category": "unknown",
            "ai_relevance": "unknown",
            "ai_keywords": [],
            "source_url": source_url,
            "post_date": post_date,
            "_raw_keys": list(raw.keys())[:20],  # 保留原始字段名用于调试
        }
