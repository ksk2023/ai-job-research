"""一键流水线：清洗 → 分类 → 验证 → 导出。

用法: python scripts/run_pipeline.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.clean import clean_all
from pipeline.classify import classify_all
from pipeline.verify import verify_all

import json
import tempfile


def main():
    print("=" * 60)
    print("AI 岗位调研 - 数据处理流水线")
    print("=" * 60)

    # Step 1: 清洗
    print("\n▶ Step 1: 数据清洗...")
    count = clean_all(
        input_dir=str(PROJECT_ROOT / "data" / "raw"),
        output_file=str(PROJECT_ROOT / "data" / "cleaned" / "cleaned_jobs.jsonl"),
    )
    print(f"  清洗后: {count} 条")

    # Step 2: 分类
    print("\n▶ Step 2: 岗位分类（技术/非技术 + AI相关度）...")
    from pipeline.classify import classify_job
    cleaned_file = PROJECT_ROOT / "data" / "cleaned" / "cleaned_jobs.jsonl"
    jobs = []
    with open(cleaned_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                jobs.append(json.loads(line))
    classified = [classify_job(j) for j in jobs]
    with open(cleaned_file, "w", encoding="utf-8") as f:
        for j in classified:
            f.write(json.dumps(j, ensure_ascii=False) + "\n")
    tech_count = sum(1 for j in classified if j.get("category") == "tech")
    ai_high = sum(1 for j in classified if j.get("ai_relevance") in ("core", "high"))
    print(f"  技术岗: {tech_count} / 非技术岗: {len(classified) - tech_count}")
    print(f"  AI 高相关: {ai_high}")

    # Step 3: 验证
    print("\n▶ Step 3: 交叉验证 + 统计导出...")
    stats = verify_all(
        input_file=str(cleaned_file),
        output_dir=str(PROJECT_ROOT / "data" / "verified"),
    )

    print("\n" + "=" * 60)
    print("✓ 流水线完成!")
    print(f"  总岗位: {stats['total']}")
    print(f"  公司数: {stats['company_count']}")
    print(f"  已验证: {stats['verified_count']} ({stats['verified_ratio']*100:.1f}%)")
    print(f"  平均置信度: {stats['avg_confidence']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
