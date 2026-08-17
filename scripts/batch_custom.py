"""批量抓取所有 custom 平台的公司，每家超时 90 秒。"""
import asyncio
import json
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scrapers.cache import ScraperCache
from run_scrape import run_one

CACHE_FILE = PROJECT_ROOT / "data" / "cache" / "seen_hashes.txt"
COMPANIES_FILE = PROJECT_ROOT / "companies.json"
SUMMARY_FILE = PROJECT_ROOT / "data" / "raw" / "batch_summary.json"


async def scrape_one(company_cfg, cache, timeout_sec=90):
    """抓取单家公司，带超时。"""
    try:
        result = await asyncio.wait_for(run_one(company_cfg, cache), timeout=timeout_sec)
        return {"id": company_cfg["id"], "name": company_cfg["name"],
                "status": "ok", "count": len(result)}
    except asyncio.TimeoutError:
        return {"id": company_cfg["id"], "name": company_cfg["name"],
                "status": "timeout", "count": 0}
    except Exception as e:
        return {"id": company_cfg["id"], "name": company_cfg["name"],
                "status": "error", "count": 0,
                "error": f"{type(e).__name__}: {str(e)[:150]}"}


async def main():
    with open(COMPANIES_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # 只抓 custom 平台的公司
    targets = [c for c in cfg["companies"] if c["platform"] == "custom"]
    print(f"将抓取 {len(targets)} 家 custom 平台公司", flush=True)

    cache = ScraperCache(CACHE_FILE)
    print(f"缓存已有 {len(cache)} 条", flush=True)

    details = []
    for i, company_cfg in enumerate(targets, 1):
        cid = company_cfg["id"]
        cname = company_cfg["name"]
        print(f"\n[{i}/{len(targets)}] {cid} ({cname})", flush=True)

        result = await scrape_one(company_cfg, cache, timeout_sec=90)
        details.append(result)

        status_icon = "✓" if result["status"] == "ok" else "✗"
        print(f"  {status_icon} {result['status']}: {result['count']} 条", flush=True)

        # 实时保存进度
        summary = {
            "total": len(targets),
            "done": i,
            "ok_count": sum(1 for d in details if d["status"] == "ok"),
            "total_jobs": sum(d["count"] for d in details),
            "details": details,
        }
        with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    # 最终总结
    ok = [d for d in details if d["status"] == "ok"]
    fail = [d for d in details if d["status"] != "ok"]
    total_jobs = sum(d["count"] for d in details)

    print(f"\n========== 批量抓取完成 ==========", flush=True)
    print(f"成功: {len(ok)} / {len(details)}", flush=True)
    print(f"失败: {len(fail)}", flush=True)
    print(f"总岗位数: {total_jobs}", flush=True)

    if ok:
        print(f"\n成功的公司:", flush=True)
        for d in sorted(ok, key=lambda x: -x["count"]):
            print(f"  ✓ {d['name']:12s} {d['count']:5d} 条", flush=True)

    if fail:
        print(f"\n失败的公司:", flush=True)
        for d in fail:
            err = d.get("error", d["status"])
            print(f"  ✗ {d['name']:12s} {err}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
