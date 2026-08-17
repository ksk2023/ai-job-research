"""批量抓取所有公司——带超时和错误处理，结果汇总到 data/raw/batch_summary.json。"""
import asyncio
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scrapers.cache import ScraperCache
from run_scrape import run_one

CACHE_FILE = PROJECT_ROOT / "data" / "cache" / "seen_hashes.txt"
COMPANIES_FILE = PROJECT_ROOT / "companies.json"
SUMMARY_FILE = PROJECT_ROOT / "data" / "raw" / "batch_summary.json"


async def scrape_with_timeout(company_cfg, cache, timeout_sec=90):
    """带超时的抓取。"""
    try:
        result = await asyncio.wait_for(run_one(company_cfg, cache), timeout=timeout_sec)
        return {"id": company_cfg["id"], "name": company_cfg["name"], "status": "ok", "count": len(result)}
    except asyncio.TimeoutError:
        return {"id": company_cfg["id"], "name": company_cfg["name"], "status": "timeout", "count": 0}
    except Exception as e:
        return {"id": company_cfg["id"], "name": company_cfg["name"], "status": "error", "count": 0, "error": f"{type(e).__name__}: {e}"}


async def main():
    cfg = json.load(open(COMPANIES_FILE, "r", encoding="utf-8"))
    cache = ScraperCache(CACHE_FILE)

    # 只抓 custom/feishu/moka/beisen/website_email 平台的公司（外企单独处理）
    targets = [c for c in cfg["companies"] if c["platform"] in ("custom", "feishu", "moka", "beisen", "website_email")]
    print(f"将批量抓取 {len(targets)} 家公司（不含外企）")
    print(f"缓存已有 {len(cache)} 条记录")

    summary = []
    for i, company in enumerate(targets, 1):
        print(f"\n[{i}/{len(targets)}] {company['name']} ({company['id']})")
        result = await scrape_with_timeout(company, cache, timeout_sec=90)
        summary.append(result)
        print(f"  -> {result['status']}: {result['count']} 条")

    # 保存汇总
    total_ok = sum(1 for s in summary if s["status"] == "ok")
    total_jobs = sum(s["count"] for s in summary)
    print(f"\n========== 批量抓取完成 ==========")
    print(f"成功: {total_ok}/{len(targets)} 家")
    print(f"总岗位数: {total_jobs}")

    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_companies": len(targets),
            "success_count": total_ok,
            "total_jobs": total_jobs,
            "details": summary,
        }, f, ensure_ascii=False, indent=2)
    print(f"汇总已保存: {SUMMARY_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
