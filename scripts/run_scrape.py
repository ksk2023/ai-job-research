"""
抓取入口脚本——按源/公司参数化运行抓取器。

用法:
  python scripts/run_scrape.py --source official --company bytedance
  python scripts/run_scrape.py --source official --all
  python scripts/run_scrape.py --source campus --company seu
  python scripts/run_scrape.py --source foreign --company openai
  python scripts/run_scrape.py --list-companies
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# 项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scrapers.cache import ScraperCache

CACHE_FILE = PROJECT_ROOT / "data" / "cache" / "seen_hashes.txt"
COMPANIES_FILE = PROJECT_ROOT / "companies.json"


def load_companies() -> dict:
    with open(COMPANIES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def list_companies(cfg: dict) -> None:
    """列出所有配置的公司。"""
    print(f"\n共 {len(cfg['companies'])} 家公司：\n")
    by_cat: dict[str, list] = {}
    for c in cfg["companies"]:
        by_cat.setdefault(c["category"], []).append(c)
    for cat, companies in by_cat.items():
        print(f"【{cfg['categories'].get(cat, cat)}】({len(companies)} 家)")
        for c in companies:
            print(f"  - {c['id']:20s} {c['name']:12s} [{c['platform']}]")
        print()


async def run_one(company_cfg: dict, cache: ScraperCache) -> list[dict]:
    """运行单个公司的抓取器。根据 platform 字段路由到对应抓取器。"""
    platform = company_cfg["platform"]
    company_id = company_cfg["id"]

    try:
        if platform == "feishu":
            from scrapers.platforms.feishu import FeishuScraper

            scraper = FeishuScraper(company_cfg, cache)
        elif platform == "beisen":
            from scrapers.platforms.beisen import BeisenScraper

            scraper = BeisenScraper(company_cfg, cache)
        elif platform == "moka":
            # 优先使用 httpx 直连，失败回退到 Playwright
            from scrapers.platforms.moka_direct import MokaDirectScraper

            scraper = MokaDirectScraper(company_cfg, cache)
        elif platform == "job91":
            from scrapers.platforms.job91 import Job91Scraper

            scraper = Job91Scraper(company_cfg, cache)
        elif platform == "website_email":
            from scrapers.official.deepseek import DeepSeekScraper

            scraper = DeepSeekScraper(company_cfg, cache)
        elif platform == "foreign":
            # 按 company_id 路由到对应外企抓取器
            foreign_module = f"scrapers.foreign.{company_id}"
            try:
                module = __import__(foreign_module, fromlist=["Scraper"])
                scraper = module.Scraper(company_cfg, cache)
            except (ImportError, AttributeError):
                from scrapers.foreign.base_foreign import ForeignScraper

                scraper = ForeignScraper(company_cfg, cache)
        elif platform == "custom":
            # 按 company_id 路由到对应自建官网抓取器
            official_module = f"scrapers.official.{company_id}"
            scraper = None
            try:
                module = __import__(official_module, fromlist=True)
                # 优先找名为 Scraper 的类，其次找任意 Scraper 子类
                if hasattr(module, "Scraper"):
                    scraper = module.Scraper(company_cfg, cache)
                else:
                    # 查找模块中以 Scraper 结尾的类
                    from scrapers.base import BaseScraper
                    for attr_name in dir(module):
                        obj = getattr(module, attr_name)
                        if isinstance(obj, type) and issubclass(obj, BaseScraper) and obj is not BaseScraper:
                            scraper = obj(company_cfg, cache)
                            break
            except (ImportError, AttributeError):
                pass

            if scraper is None:
                # 回退到通用浏览器 API 拦截抓取器
                from scrapers.official.browser_api import BrowserAPIScraper

                scraper = BrowserAPIScraper(company_cfg, cache)
                scraper.source_platform = f"{company_id}_official"
        else:
            print(f"  ⚠ 未知 platform: {platform}")
            return []

        return await scraper.run()
    except Exception as e:
        print(f"  ✗ 抓取 {company_id} 失败: {type(e).__name__}: {e}")
        return []


async def main():
    parser = argparse.ArgumentParser(description="AI 岗位调研抓取入口")
    parser.add_argument(
        "--source",
        choices=["official", "campus", "third_party", "social", "foreign", "all"],
        default="all",
        help="抓取来源",
    )
    parser.add_argument("--company", help="指定公司 ID（如 bytedance）")
    parser.add_argument("--all", action="store_true", help="抓取所有公司")
    parser.add_argument("--list-companies", action="store_true", help="列出所有公司")
    parser.add_argument("--clear-cache", action="store_true", help="清空抓取缓存")
    args = parser.parse_args()

    cfg = load_companies()

    if args.list_companies:
        list_companies(cfg)
        return

    cache = ScraperCache(CACHE_FILE)
    if args.clear_cache:
        cache.clear()
        print(f"已清空缓存 ({CACHE_FILE})")
        return

    # 选择目标公司
    if args.company:
        targets = [c for c in cfg["companies"] if c["id"] == args.company]
        if not targets:
            print(f"未找到公司: {args.company}")
            return
    elif args.all or args.source == "all":
        targets = cfg["companies"]
    else:
        # 按 source 筛选
        source_map = {
            "official": ["custom", "feishu", "beisen", "moka", "website_email"],
            "foreign": ["foreign"],
            "campus": ["job91"],
        }
        target_platforms = source_map.get(args.source, [])
        targets = [c for c in cfg["companies"] if c["platform"] in target_platforms]

    if not targets:
        print("没有匹配的公司")
        return

    print(f"\n将抓取 {len(targets)} 家公司")
    print(f"缓存已有 {len(cache)} 条已抓记录")

    # 顺序执行（避免并发太多被反爬）
    all_results: list[dict] = []
    for i, company_cfg in enumerate(targets, 1):
        print(f"\n========== [{i}/{len(targets)}] ==========")
        results = await run_one(company_cfg, cache)
        all_results.extend(results)

    print(f"\n========== 全部完成 ==========")
    print(f"总计新增 {len(all_results)} 条岗位")
    print(f"缓存总记录: {len(cache)}")


if __name__ == "__main__":
    asyncio.run(main())
