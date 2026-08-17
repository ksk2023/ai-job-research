"""
飞书招聘 SaaS 适配器——适用于 *.jobs.feishu.cn 站点。

使用公司：智谱AI、百川智能等。

技术方案：Playwright 浏览器内执行 fetch 调用 API（绕过 _signature 签名校验）。
飞书招聘 API:
  POST /api/v1/search/job/posts  —— 岗位列表（需先获取 CSRF token）
  POST /api/v1/csrf/token        —— 获取 CSRF token
"""
from __future__ import annotations

import json
from urllib.parse import urlparse

from ..base import PlaywrightScraper


class FeishuScraper(PlaywrightScraper):
    """飞书招聘 SaaS 通用适配器。"""

    source_platform = "feishu_recruitment"
    source_type = "official"
    rate_limit_per_min = 12  # 飞书有签名校验，慢一点
    needs_browser = True

    PAGE_SIZE = 20  # 每页岗位数
    MAX_PAGES = 50  # 最多翻 50 页（1000 条）

    async def fetch_list(self) -> list[dict]:
        """通过浏览器内 fetch 调用飞书 API 获取岗位列表。"""
        page = await self.page
        career_url = self.cfg["career_urls"].get("campus") or list(self.cfg["career_urls"].values())[0]

        # 1. 先访问页面，让浏览器建立 session
        print(f"  访问页面: {career_url}")
        try:
            await page.goto(career_url, wait_until="networkidle", timeout=60000)
        except Exception as e:
            print(f"  页面加载警告: {e}")
        await page.wait_for_timeout(3000)

        # 2. 在浏览器内执行 fetch 获取 CSRF token
        csrf_token = await page.evaluate("""async () => {
            try {
                const resp = await fetch('/api/v1/csrf/token', {
                    method: 'POST',
                    credentials: 'include',
                    headers: {'Content-Type': 'application/json'}
                });
                const data = await resp.json();
                return data.data?.token || data.token || '';
            } catch(e) { return ''; }
        }""")
        print(f"  CSRF token: {csrf_token[:20]}..." if csrf_token else "  ⚠ 未获取到 CSRF token")

        # 3. 确定portal_type（6=校招，其他类型从URL判断）
        portal_type = 6  # 默认校招
        url_str = career_url.lower()
        if "intern" in url_str or "实习" in url_str:
            portal_type = 6  # 飞书 intern 也在 campus portal
        elif "social" in url_str or "社招" in url_str:
            portal_type = 7  # 社招

        # 4. 循环翻页获取所有岗位
        all_posts: list[dict] = []
        for offset in range(0, self.MAX_PAGES * self.PAGE_SIZE, self.PAGE_SIZE):
            posts = await page.evaluate(f"""async () => {{
                try {{
                    const resp = await fetch('/api/v1/search/job/posts?keyword=&limit={self.PAGE_SIZE}&offset={offset}&job_category_id_list=&tag_id_list=&location_code_list=&subject_id_list=&recruitment_id_list=&portal_type={portal_type}&job_function_id_list=&storefront_id_list=&portal_entrance=1', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/json',
                            'x-csrf-token': '{csrf_token}'
                        }},
                        body: JSON.stringify({{}})
                    }});
                    if (!resp.ok) return {{error: 'HTTP ' + resp.status, posts: []}};
                    const data = await resp.json();
                    return {{
                        posts: data.data?.job_post_list || [],
                        total: data.data?.total || 0
                    }};
                }} catch(e) {{
                    return {{error: e.message, posts: []}};
                }}
            }}""")

            if posts.get("error"):
                print(f"  第 {offset//self.PAGE_SIZE + 1} 页错误: {posts['error']}")
                break

            page_posts = posts.get("posts", [])
            if not page_posts:
                break

            all_posts.extend(page_posts)
            total = posts.get("total", 0)
            print(f"  第 {offset//self.PAGE_SIZE + 1} 页: {len(page_posts)} 条（累计 {len(all_posts)}/{total}）")

            # 停止条件：不足一页（已是末页）
            # 注意：飞书 total 可能返回 0 不可靠，主要靠"不足一页"判断
            if len(page_posts) < self.PAGE_SIZE:
                break

            # 翻页间隔
            import asyncio
            await asyncio.sleep(2)

        return all_posts

    def parse_item(self, raw: dict) -> dict:
        """把飞书 API 返回的岗位数据解析为统一 schema。"""
        # 飞书字段映射
        title = raw.get("title", "").strip()
        # city 可能是字符串、list[str] 或 list[dict]
        city = raw.get("city", "") or raw.get("city_list", [])
        if isinstance(city, list):
            location = []
            for c in city:
                if isinstance(c, dict):
                    location.append(str(c.get("name", "")).strip())
                elif c:
                    location.append(str(c).strip())
            location = [l for l in location if l]
            location_raw = ",".join(location)
        elif isinstance(city, str):
            location = [c.strip() for c in city.split(",") if c.strip()]
            location_raw = city
        else:
            location = []
            location_raw = ""

        # 招聘类型判断
        recruit_type = raw.get("recruitment_type", 0)
        job_type = "autumn_campus"
        if recruit_type == 2 or "实习" in title or "intern" in title.lower():
            job_type = "intern"
        elif "社招" in title or "experienced" in title.lower():
            job_type = "social"

        # 学历要求
        education = ""
        degree_require = raw.get("degree_requirement") or raw.get("degree_require")
        if degree_require:
            education = str(degree_require)

        # 详情 URL
        job_id = raw.get("id", "")
        base_host = "zhipu-ai.jobs.feishu.cn"
        for u in self.cfg["career_urls"].values():
            if isinstance(u, str) and "feishu.cn" in u:
                parsed = urlparse(u)
                base_host = parsed.netloc
                break
        source_url = f"https://{base_host}/position/detail/{job_id}" if job_id else ""

        # 职责描述
        description = raw.get("description", "") or ""
        requirement = raw.get("requirement", "") or ""
        responsibilities = f"{description}\n\n{requirement}".strip()

        return {
            "title": title,
            "title_raw": title,
            "location": location,
            "location_raw": location_raw,
            "education": education,
            "experience": raw.get("experience_requirement", "") or "应届",
            "salary_range": None,
            "salary_raw": "",
            "skills": [],  # 飞书 API 通常不单独提供技能字段
            "responsibilities": responsibilities,
            "description_html": "",
            "job_type": job_type,
            "category": "unknown",  # 待 classify 阶段判定
            "ai_relevance": "unknown",
            "ai_keywords": [],
            "source_url": source_url,
            "post_date": raw.get("update_time", "") or raw.get("create_time", ""),
        }
