"""
91job 平台抓取器——东南大学就业指导中心等高校就业网通用适配器。

URL 特征: *.91job.org.cn
技术方案: httpx + BeautifulSoup（相对好抓，无需浏览器渲染）
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..base import BaseScraper


class Job91Scraper(BaseScraper):
    """91job 高校就业网抓取器。"""

    source_platform = "seu_91job"
    source_type = "campus"
    rate_limit_per_min = 15  # 校园网关，慢一点
    needs_browser = False

    BASE_URL = "https://seu.91job.org.cn"
    LIST_PATH = "/sub-station/listJob"
    DETAIL_PATH = "/sub-station/viewJob"

    async def fetch_list(self) -> list[dict]:
        """抓取岗位列表（含分页）。"""
        results: list[dict] = []
        page = 1
        max_pages = 30  # 安全上限

        while page <= max_pages:
            params = {"xxdm": "10286", "pageNo": str(page)}
            url = f"{self.BASE_URL}{self.LIST_PATH}"
            try:
                resp = await self._request_with_retry(url, params=params)
                html = resp.text
            except Exception as e:
                print(f"  第 {page} 页抓取失败: {e}")
                break

            items = self._parse_list_page(html)
            if not items:
                break
            results.extend(items)
            print(f"  第 {page} 页: {len(items)} 条")
            if len(items) < 20:  # 不足一页，已是末页
                break
            page += 1

        return results

    def _parse_list_page(self, html: str) -> list[dict]:
        """解析列表页 HTML，返回原始 job dict 列表。"""
        soup = BeautifulSoup(html, "lxml")
        items: list[dict] = []

        # 91job 列表项通常在 .job-list 或 .position-list 等容器内
        # 实际选择器需根据真实页面调整——先尝试多种常见模式
        candidates = [
            soup.select(".job-item"),
            soup.select(".position-item"),
            soup.select(".list-item"),
            soup.select("tr[data-id]"),
            soup.select(".job-list li"),
            soup.select(".table-list tr"),
        ]

        for node_list in candidates:
            if node_list:
                for node in node_list:
                    item = self._parse_list_item(node)
                    if item:
                        items.append(item)
                break

        # 如果以上选择器都没命中，尝试从 JSON-LD 或 script 提取
        if not items:
            items = self._extract_from_script(soup)

        return items

    def _parse_list_item(self, node) -> dict | None:
        """解析单条列表项。"""
        try:
            # 标题——尝试多种选择器
            title_node = node.select_one("a, .title, .job-title, .name")
            if not title_node:
                return None
            title = title_node.get_text(strip=True)
            if not title:
                return None

            # 详情链接
            href = title_node.get("href", "")
            if href:
                source_url = urljoin(self.BASE_URL, href)
            else:
                source_url = ""

            # 公司名
            company_node = node.select_one(".company, .company-name, .ent-name")
            company = company_node.get_text(strip=True) if company_node else self.cfg.get("name", "")

            # 地点
            location_node = node.select_one(".location, .work-place, .city")
            location = location_node.get_text(strip=True) if location_node else ""

            # 发布日期
            date_node = node.select_one(".date, .time, .publish-date")
            post_date = ""
            if date_node:
                post_date = date_node.get_text(strip=True)

            return {
                "title": title,
                "title_raw": title,
                "company_raw": company,
                "location": [location] if location else [],
                "location_raw": location,
                "source_url": source_url,
                "post_date": post_date,
                "job_type": "autumn_campus",  # 91job 主要是校招
            }
        except Exception:
            return None

    def _extract_from_script(self, soup: BeautifulSoup) -> list[dict]:
        """从页面 script 中提取 JSON 数据（部分站点用 JSON 渲染列表）。"""
        items: list[dict] = []
        for script in soup.find_all("script"):
            text = script.string or script.get_text()
            if not text:
                continue
            # 尝试找到 jobList / positionList 等变量
            m = re.search(r'(?:jobList|positionList|job_list|positions)\s*=\s*(\[.*?\]);', text, re.S)
            if m:
                try:
                    import json
                    data = json.loads(m.group(1))
                    for d in data:
                        items.append({
                            "title": d.get("jobTitle") or d.get("title") or d.get("name", ""),
                            "title_raw": d.get("jobTitle") or d.get("title") or d.get("name", ""),
                            "company_raw": d.get("companyName") or d.get("company", ""),
                            "location": [d.get("workPlace") or d.get("city", "")] if d.get("workPlace") or d.get("city") else [],
                            "location_raw": d.get("workPlace") or d.get("city", ""),
                            "source_url": urljoin(self.BASE_URL, d.get("url", "") or d.get("detailUrl", "")),
                            "post_date": d.get("publishDate") or d.get("createTime", ""),
                            "job_type": "autumn_campus",
                        })
                except Exception:
                    continue
        return items

    async def fetch_detail(self, raw: dict) -> dict:
        """抓取详情页补充信息。"""
        if not raw.get("source_url"):
            return {}
        try:
            resp = await self._request_with_retry(raw["source_url"])
            soup = BeautifulSoup(resp.text, "lxml")

            # 提取详情正文
            detail = {}
            content = soup.select_one(".job-detail, .position-detail, .detail-content, .content")
            if content:
                detail["responsibilities"] = content.get_text("\n", strip=True)
                detail["description_html"] = str(content)[:5000]

            # 学历要求
            edu_node = soup.select_one(".education, .degree, .requirement")
            if edu_node:
                detail["education"] = edu_node.get_text(strip=True)

            return detail
        except Exception as e:
            print(f"  详情页抓取失败: {e}")
            return {}

    def parse_item(self, raw: dict) -> dict:
        """解析为统一 schema。"""
        return {
            "title": raw.get("title", "").strip(),
            "title_raw": raw.get("title_raw", raw.get("title", "")),
            "company_raw": raw.get("company_raw", ""),
            "location": raw.get("location", []),
            "location_raw": raw.get("location_raw", ""),
            "education": raw.get("education", ""),
            "experience": "应届",
            "salary_range": None,
            "salary_raw": "",
            "skills": [],
            "responsibilities": raw.get("responsibilities", ""),
            "description_html": raw.get("description_html", ""),
            "job_type": raw.get("job_type", "autumn_campus"),
            "category": "unknown",  # 待 classify 阶段判定
            "ai_relevance": "unknown",  # 待 classify 阶段判定
            "ai_keywords": [],
            "source_url": raw.get("source_url", ""),
            "post_date": raw.get("post_date", ""),
        }
