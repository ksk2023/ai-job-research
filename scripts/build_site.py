"""把 verified 数据打包进 site/data/，并生成网站所需的所有静态数据文件。"""
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

VERIFIED_DIR = PROJECT_ROOT / "data" / "verified"
SITE_DATA_DIR = PROJECT_ROOT / "site" / "data"


def build():
    """打包数据到 site/data/。"""
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    files_copied = []
    for fname in ["jobs.json", "jobs.csv", "stats.json"]:
        src = VERIFIED_DIR / fname
        if src.exists():
            shutil.copy2(src, SITE_DATA_DIR / fname)
            files_copied.append(fname)
            print(f"  ✓ {fname} ({src.stat().st_size} bytes)")
        else:
            print(f"  ✗ {fname} 不存在，请先运行 run_pipeline.py")

    # 生成公司列表（供前端筛选用）
    jobs_path = VERIFIED_DIR / "jobs.json"
    if jobs_path.exists():
        jobs = json.load(open(jobs_path, "r", encoding="utf-8"))
        companies = sorted(set(j["company"] for j in jobs if j.get("company")))
        locations = sorted(set(loc for j in jobs for loc in (j.get("location") or [])))
        meta = {
            "company_count": len(companies),
            "job_count": len(jobs),
            "companies": companies,
            "locations": locations,
        }
        with open(SITE_DATA_DIR / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f"  ✓ meta.json (公司{len(companies)}家, 地点{len(locations)}个)")

    print(f"\n打包完成: {len(files_copied)} 个文件已复制到 {SITE_DATA_DIR}")


if __name__ == "__main__":
    print("打包网站数据...")
    build()
