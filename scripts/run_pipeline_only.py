"""Run pipeline steps 2-5 only (skip scraping), using existing raw data."""
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
print(f"{'='*60}")
print(f"  管道续跑（跳过抓取） — {now}")
print(f"{'='*60}")

# Step 2: 数据清洗
print(f"\n▶ Step 2: 数据清洗...")
from pipeline.clean import clean_all

cleaned_count = clean_all(
    input_dir=str(PROJECT_ROOT / "data" / "raw"),
    output_file=str(PROJECT_ROOT / "data" / "cleaned" / "cleaned_jobs.jsonl"),
)
print(f"  清洗后: {cleaned_count} 条")

# Step 3: 三重筛选
print(f"\n▶ Step 3: 三重筛选（国内公司 + 中国大陆 + 研究生及以上）...")
from daily_update import filter_graduate_jobs

filter_stats = filter_graduate_jobs(
    input_file=str(PROJECT_ROOT / "data" / "cleaned" / "cleaned_jobs.jsonl"),
    output_file=str(PROJECT_ROOT / "data" / "cleaned" / "graduate_jobs.jsonl"),
)
print(f"  总岗位: {filter_stats['total']}")
print(f"  保留: {filter_stats['kept']}")
print(f"  筛除-学历不符: {filter_stats['filtered_out_edu']}")
print(f"  筛除-非中国大陆: {filter_stats['filtered_out_location']}")
print(f"  筛除-外企: {filter_stats['filtered_out_foreign']}")

# Step 4: 交叉验证
print(f"\n▶ Step 4: 交叉验证 + 统计...")
from pipeline.verify import verify_all

stats = verify_all(
    input_file=str(PROJECT_ROOT / "data" / "cleaned" / "graduate_jobs.jsonl"),
    output_dir=str(PROJECT_ROOT / "data" / "verified"),
)
print(f"  验证后: {stats.get('total', 0)} 条岗位")
print(f"  已验证: {stats.get('verified_count', 0)} ({stats.get('verified_ratio', 0)*100:.1f}%)")

# Step 5: 重建网站数据
print(f"\n▶ Step 5: 重建网站数据...")
import build_site

build_site.build()
print(f"  网站数据已更新")

# 汇总
print(f"\n{'='*60}")
print(f"  ✅ 管道续跑完成 — {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  清洗后: {cleaned_count} 条")
print(f"  筛选后(研究生+中国大陆+国内公司): {filter_stats['kept']} 条")
print(f"    筛除: 学历{filter_stats['filtered_out_edu']} + 地点{filter_stats['filtered_out_location']} + 外企{filter_stats['filtered_out_foreign']}")
print(f"  验证后: {stats.get('total', 0)} 条")
print(f"{'='*60}")

# Save log
# Count scraped from raw files
raw_dir = PROJECT_ROOT / "data" / "raw"
scraped_count = 0
for f in raw_dir.glob("*_20260806.jsonl"):
    with open(f, "r", encoding="utf-8") as rf:
        for line in rf:
            if line.strip():
                scraped_count += 1

log = {
    "timestamp": now,
    "scraped": scraped_count,
    "cleaned": cleaned_count,
    "graduate_filtered": filter_stats,
    "verified": stats,
    "note": "月之暗面(careers.kimi.com)页面加载卡死导致抓取中断，已用已抓数据续跑管道",
}
log_file = PROJECT_ROOT / "data" / "daily_update_log.json"
with open(log_file, "w", encoding="utf-8") as f:
    json.dump(log, f, ensure_ascii=False, indent=2)
print(f"\n日志已保存: {log_file}")
