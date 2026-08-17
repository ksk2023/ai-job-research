"""
BaseScraper 抽象基类——所有抓取器的统一接口。

设计要点：
1. 抽象方法 fetch_list() 和 parse_item()，子类必须实现
2. 统一流程：限速 → 抓列表 → 增量去重 → 抓详情 → 标准化 → 输出 jsonl
3. 支持两种模式：httpx (静态) 和 Playwright (动态)
4. 集成 cache / rate_limiter / ua_pool
5. 失败指数退避
"""
from __future__ import annotations

import asyncio
import json
import random
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from .cache import ScraperCache
from .rate_limiter import rate_limiter
from .ua_pool import ua_pool


class BaseScraper(ABC):
    """所有抓取器的抽象基类。

    子类需要：
      1. 覆盖类属性 source_platform / source_type
      2. 实现 fetch_list() 和 parse_item()
      3. 如有详情页，覆盖 fetch_detail()

    抓取流程由 run() 统一编排，子类无需关心限速、缓存、退避等细节。
    """

    source_platform: str = ""  # 子类覆盖，如 "bytedance_official"
    source_type: str = ""  # "official" / "third_party" / "campus" / "social"
    rate_limit_per_min: int = 20  # 每分钟请求上限，子类可调整
    needs_browser: bool = False  # 是否需要 Playwright（SPA 站点）
    max_retries: int = 3  # 失败重试次数

    def __init__(
        self,
        company_cfg: dict,
        cache: ScraperCache,
        output_dir: str | Path = "data/raw",
    ):
        self.cfg = company_cfg
        self.cache = cache
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._client: httpx.AsyncClient | None = None

    # ====== 子类必须实现的方法 ======

    @abstractmethod
    async def fetch_list(self) -> list[dict]:
        """抓取岗位列表，返回原始 job dict 列表（每条至少含 title / location / source_url）。"""
        ...

    @abstractmethod
    def parse_item(self, raw: dict) -> dict:
        """把单条原始数据解析为统一 schema（不含 id/source_platform/source_type/scraped_at，由 run() 统一填充）。"""
        ...

    # ====== 子类可选覆盖 ======

    async def fetch_detail(self, raw: dict) -> dict:
        """抓取详情页。默认无详情页，子类按需覆盖。"""
        return {}

    def _has_detail(self) -> bool:
        """子类若覆盖了 fetch_detail 返回非空数据，应返回 True。默认 False。"""
        return False

    # ====== HTTP 客户端管理 ======

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=ua_pool.headers(),
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
                http2=False,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ====== 失败退避 ======

    async def _request_with_retry(
        self,
        url: str,
        method: str = "GET",
        **kwargs,
    ) -> httpx.Response:
        """带指数退避的 HTTP 请求。"""
        backoffs = [2, 8, 30]  # 3 次退避间隔
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                await rate_limiter.acquire(url, self.rate_limit_per_min)
                # 每次请求刷新 UA
                headers = kwargs.pop("headers", None) or {}
                headers.setdefault("User-Agent", ua_pool.random())
                resp = await self.client.request(method, url, headers=headers, **kwargs)
                if resp.status_code in (429, 403):
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                return resp
            except Exception as e:
                last_exc = e
                if attempt < self.max_retries:
                    wait = backoffs[attempt] + random.uniform(0, 2)
                    print(f"  [退避] {url[:60]}... 第{attempt+1}次失败({type(e).__name__})，等待 {wait:.1f}s")
                    await asyncio.sleep(wait)
                else:
                    raise
        raise last_exc  # type: ignore

    # ====== 指纹计算 ======

    def _fingerprint(self, raw: dict) -> str:
        """计算岗位指纹（用于增量抓取）。

        尝试多种常见字段名，兼容不同 API 返回格式。
        """
        # 尝试多种标题字段名
        title = (raw.get("title") or raw.get("name") or raw.get("RecruitPostName") or
                 raw.get("position_name") or raw.get("job_title") or raw.get("post_name") or
                 raw.get("zwmc") or "")
        # 尝试多种地点字段名
        location = (raw.get("location") or raw.get("city") or raw.get("LocationName") or
                    raw.get("work_place") or raw.get("workplace") or raw.get("CityName") or "")
        if isinstance(location, list):
            location = "|".join(str(l) for l in location)
        return ScraperCache.fingerprint(self.cfg["id"], str(title), str(location))

    # ====== 主流程 ======

    async def run(self) -> list[dict]:
        """统一抓取流程：限速 → 抓列表 → 增量去重 → 抓详情 → 标准化 → 输出。"""
        company_name = self.cfg.get("name", self.cfg["id"])
        print(f"\n▶ 开始抓取 [{self.source_platform}] {company_name}")
        try:
            raw_list = await self.fetch_list()
        except Exception as e:
            print(f"  ✗ 抓取列表失败: {type(e).__name__}: {e}")
            return []
        print(f"  列表获取: {len(raw_list)} 条原始记录")

        results: list[dict] = []
        skipped = 0
        for i, raw in enumerate(raw_list, 1):
            fp = self._fingerprint(raw)
            if self.cache.seen(fp):
                skipped += 1
                continue
            try:
                # 抓详情（如有）
                detail = await self.fetch_detail(raw)
                merged = {**raw, **detail}
                # 解析为统一 schema
                job = self.parse_item(merged)
                # 统一填充元数据
                job["id"] = fp
                job["company"] = self.cfg.get("name", "")
                job["company_id"] = self.cfg["id"]
                job["company_category"] = self.cfg.get("category", "")
                job["source_platform"] = self.source_platform
                job["source_type"] = self.source_type
                job["scraped_at"] = datetime.now().astimezone().isoformat()
                self.cache.mark(fp)
                results.append(job)
                if i % 50 == 0:
                    print(f"  进度: {i}/{len(raw_list)}（新增 {len(results)}）")
                # 随机延迟（仅当抓取详情时才需要较长延迟；纯列表抓取用短延迟）
                if self._has_detail():
                    await asyncio.sleep(random.uniform(1.0, 2.5))
                else:
                    await asyncio.sleep(random.uniform(0.05, 0.15))
            except Exception as e:
                print(f"  ✗ 第 {i} 条解析失败: {type(e).__name__}: {e}")
                continue

        print(f"  完成: 新增 {len(results)} 条，跳过 {skipped} 条（已抓过）")

        # 输出 jsonl 文件
        if results:
            await self._save(results)

        await self.close()
        return results

    async def _save(self, results: list[dict]) -> None:
        """保存到 data/raw/{platform}_{company_id}_{date}.jsonl。"""
        today = datetime.now().strftime("%Y%m%d")
        filename = f"{self.source_platform}_{self.cfg['id']}_{today}.jsonl"
        path = self.output_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            for job in results:
                f.write(json.dumps(job, ensure_ascii=False) + "\n")
        print(f"  已保存: {path}")


class PlaywrightScraper(BaseScraper):
    """需要 Playwright 浏览器渲染的抓取器基类。

    子类覆盖 fetch_list() 时可通过 self.page 访问 Playwright Page 对象。
    """

    needs_browser = True

    def __init__(
        self,
        company_cfg: dict,
        cache: ScraperCache,
        output_dir: str | Path = "data/raw",
    ):
        super().__init__(company_cfg, cache, output_dir)
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def _ensure_browser(self) -> None:
        """懒加载 Playwright 浏览器。"""
        if self._page is not None:
            return
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        self._context = await self._browser.new_context(
            user_agent=ua_pool.chrome_only(),
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        # 注入反检测脚本
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self._page = await self._context.new_page()

    @property
    async def page(self):
        """获取 Playwright Page 对象（懒加载）。"""
        await self._ensure_browser()
        return self._page

    async def close(self) -> None:
        """关闭浏览器和 HTTP 客户端。"""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        await super().close()
