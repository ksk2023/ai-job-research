"""全量抓取脚本——抓取所有国内公司。"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_scrape import run_one
from scrapers.cache import ScraperCache


async def main():
    cfg = json.load(open(PROJECT_ROOT / "companies.json", encoding="utf-8"))
    cache = ScraperCache(PROJECT_ROOT / "data" / "cache" / "seen_hashes.txt")

    companies = [
        c for c in cfg["companies"]
        if c.get("category") != "foreign"
        and c.get("platform") != "job91"
        and c.get("status") != "unavailable"
    ]

    print(f"将抓取 {len(companies)} 家公司\n")

    total = 0
    results = []
    for i, c in enumerate(companies, 1):
        print(f"[{i}/{len(companies)}] {c['name']}...")
        try:
            result = await asyncio.wait_for(run_one(c, cache), timeout=90)
            total += len(result)
            results.append({"id": c["id"], "name": c["name"], "count": len(result), "status": "ok"})
            print(f"  -> {len(result)} 条\n")
        except asyncio.TimeoutError:
            results.append({"id": c["id"], "name": c["name"], "count": 0, "status": "timeout"})
            print(f"  -> TIMEOUT\n")
        except Exception as e:
            results.append({"id": c["id"], "name": c["name"], "count": 0, "status": "error", "error": str(e)[:100]})
            print(f"  -> ERROR: {type(e).__name__}: {e}\n")

    ok = [r for r in results if r["count"] > 0]
    zero = [r for r in results if r["count"] == 0]

    print(f"\n{'='*60}")
    print(f"抓取完成: {total} 条岗位")
    print(f"有数据: {len(ok)} 家")
    for r in sorted(ok, key=lambda x: -x["count"]):
        print(f"  {r['name']:12s} {r['count']:4d} 条")
    print(f"无数据: {len(zero)} 家")
    for r in zero:
        print(f"  {r['name']:12s} [{r['status']}]")

    # 保存汇总
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_companies": len(companies),
        "ok_count": len(ok),
        "total_jobs": total,
        "details": results,
    }
    with open(PROJECT_ROOT / "data" / "raw" / "batch_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
