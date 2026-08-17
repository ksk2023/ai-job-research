"""每日定时更新脚本——抓取最新岗位 + 学历筛选 + 重建网站数据。

流程：
1. 清空缓存，重新抓取所有已配置的公司
2. 运行数据清洗管道
3. 筛选学历要求为"硕士及以上"和"博士及以上"的岗位（研究生及以上）
4. 运行交叉验证
5. 重建网站数据文件

学历筛选规则：
- 保留 education 字段包含"硕士"/"硕士及以上"的岗位
- 保留 education 字段包含"博士"/"博士及以上"的岗位
- 保留 education 字段为空或不限的岗位（未明确要求的不排除）
- 排除明确要求"本科"或"大专"且不含"硕士"/"博士"的岗位
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scrapers.cache import ScraperCache


def is_graduate_or_above(education: str) -> bool:
    """判断学历要求是否为研究生及以上。

    判定逻辑：
    - 含"博士" → True
    - 含"硕士" → True
    - 含"研究生" → True
    - 空或不限 → True（未明确要求，保留）
    - 仅"本科"/"大专"且不含研究生 → False
    """
    if not education or not education.strip():
        return True  # 未明确要求，保留

    edu = str(education).strip()

    # 明确要求研究生及以上
    if any(k in edu for k in ["博士", "硕士", "研究生", "Master", "PhD", "master", "phd"]):
        return True

    # 明确要求本科/大专且不含研究生关键词
    if any(k in edu for k in ["本科", "大专", "专科", "Bachelor", "bachelor"]):
        # 检查是否同时提到研究生（如"本科/硕士"）
        if not any(k in edu for k in ["硕士", "博士", "研究生", "Master", "PhD"]):
            return False

    # 不限
    if any(k in edu for k in ["不限", "无要求", "any", "Any"]):
        return True

    # 其他情况保留
    return True


# 中国大陆城市/省份关键词
CHINA_MAINLAND_KEYWORDS = [
    "北京", "上海", "深圳", "广州", "天津", "重庆",
    "杭州", "成都", "南京", "武汉", "西安", "苏州", "厦门", "长沙", "青岛",
    "大连", "宁波", "济南", "合肥", "福州", "东莞", "佛山", "常州", "无锡",
    "珠海", "中山", "惠州", "汕头", "湛江", "肇庆", "江门", "茂名", "揭阳",
    "南宁", "海口", "三亚", "昆明", "贵阳", "南昌", "太原", "石家庄",
    "沈阳", "长春", "哈尔滨", "兰州", "银川", "西宁", "乌鲁木齐", "拉萨",
    "呼和浩特", "温州", "绍兴", "嘉兴", "金华", "台州", "烟台", "潍坊",
    "保定", "廊坊", "洛阳", "徐州", "芜湖", "株洲", "绵阳", "遵义",
    "广东", "浙江", "江苏", "山东", "河南", "四川", "湖北", "湖南", "福建",
    "安徽", "河北", "陕西", "辽宁", "吉林", "黑龙江", "江西", "山西",
    "云南", "贵州", "广西", "海南", "甘肃", "青海", "宁夏", "新疆",
    "西藏", "内蒙",
]

# 明确非中国大陆的关键词
NON_MAINLAND_KEYWORDS = [
    "香港", "澳门", "台湾", "台北", "高雄", "Hong Kong", "Taiwan", "Macao", "Macau",
    "United States", "USA", "America", "美国", "San Francisco", "旧金山",
    "New York", "纽约", "Seattle", "西雅图", "London", "伦敦", "UK", "英国",
    "Tokyo", "东京", "Japan", "日本", "Singapore", "新加坡", "Sydney", "悉尼",
    "Australia", "澳大利亚", "Canada", "加拿大", "Toronto", "多伦多",
    "Germany", "德国", "France", "法国", "Paris", "巴黎", "Berlin", "柏林",
    "Ireland", "爱尔兰", "Dublin", "都柏林", "India", "印度",
    "Netherlands", "荷兰", "Amsterdam", "阿姆斯特丹",
    "Remote-Friendly", "Remote,", "远程",
    "CA", "WA", "DC", "NY", "MA", "TX", "IL",
    "San Jose", "Mountain View", "Sunnyvale", "Palo Alto",
    "California", "Washington", "Oregon", "Massachusetts",
    "Europe", "EMEA", "APAC",
]

FOREIGN_COMPANY_CATEGORIES = {"foreign"}
FOREIGN_COMPANY_IDS = {
    "openai", "anthropic", "google", "microsoft", "meta",
    "nvidia", "amazon", "apple", "perplexity", "stability",
}


def is_china_mainland_location(job: dict) -> bool:
    """判断岗位地点是否在中国大陆。"""
    locations = job.get("location", [])
    location_raw = job.get("location_raw", "")

    all_loc_text = ""
    if isinstance(locations, list):
        all_loc_text = " ".join(str(l) for l in locations if l)
    elif isinstance(locations, str):
        all_loc_text = locations
    all_loc_text += " " + str(location_raw or "")

    if not all_loc_text.strip():
        return True  # 空地点保留

    if any(k in all_loc_text for k in CHINA_MAINLAND_KEYWORDS):
        return True
    if any(k in all_loc_text for k in NON_MAINLAND_KEYWORDS):
        return False
    return True  # 无法判断的保留


def is_domestic_company(job: dict) -> bool:
    """判断是否为国内公司（排除外企）。"""
    if job.get("company_category", "") in FOREIGN_COMPANY_CATEGORIES:
        return False
    if job.get("company_id", "") in FOREIGN_COMPANY_IDS:
        return False
    return True


def filter_graduate_jobs(input_file: str, output_file: str) -> dict:
    """筛选研究生及以上 + 中国大陆 + 国内公司的岗位。返回统计信息。"""
    input_path = Path(input_file)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    kept = 0
    filtered_out_edu = 0
    filtered_out_location = 0
    filtered_out_foreign = 0
    by_edu = {}

    with open(input_path, "r", encoding="utf-8") as f_in:
        jobs = []
        for line in f_in:
            line = line.strip()
            if not line:
                continue
            try:
                job = json.loads(line)
                total += 1
                edu = job.get("education", "")
                by_edu[edu or "未标注"] = by_edu.get(edu or "未标注", 0) + 1

                # 筛选1: 国内公司
                if not is_domestic_company(job):
                    filtered_out_foreign += 1
                    continue

                # 筛选2: 中国大陆地点
                if not is_china_mainland_location(job):
                    filtered_out_location += 1
                    continue

                # 筛选3: 研究生及以上
                if not is_graduate_or_above(edu):
                    filtered_out_edu += 1
                    continue

                jobs.append(job)
                kept += 1
            except Exception:
                continue

    with open(output_path, "w", encoding="utf-8") as f_out:
        for job in jobs:
            f_out.write(json.dumps(job, ensure_ascii=False) + "\n")

    return {
        "total": total,
        "kept": kept,
        "filtered_out_edu": filtered_out_edu,
        "filtered_out_location": filtered_out_location,
        "filtered_out_foreign": filtered_out_foreign,
        "by_education": by_edu,
    }


async def run_daily_update():
    """每日更新主流程。"""
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{'='*60}")
    print(f"  每日定时更新 — {now}")
    print(f"{'='*60}")

    # ====== Step 1: 重新抓取 ======
    print(f"\n▶ Step 1: 抓取最新岗位数据...")

    # 清空缓存（全量重抓）
    cache = ScraperCache(PROJECT_ROOT / "data" / "cache" / "seen_hashes.txt")
    cache.clear()
    print(f"  缓存已清空")

    # 加载公司配置
    with open(PROJECT_ROOT / "companies.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)

    from run_scrape import run_one

    total_scraped = 0
    scrape_results = []

    # 按优先级排序：先抓有公开 API 的（腾讯/智谱），再抓其他
    # 排除外企公司（仅国内公司）
    priority_order = {"tencent": 0, "zhipu": 1, "meituan": 2, "pinduoduo": 3}
    companies = [
        c for c in cfg["companies"]
        if c.get("category") != "foreign" and c["id"] not in FOREIGN_COMPANY_IDS
    ]
    companies = sorted(companies, key=lambda c: priority_order.get(c["id"], 99))

    for i, company_cfg in enumerate(companies, 1):
        cid = company_cfg["id"]
        cname = company_cfg["name"]
        try:
            result = await asyncio.wait_for(run_one(company_cfg, cache), timeout=90)
            count = len(result)
            total_scraped += count
            scrape_results.append({"id": cid, "name": cname, "count": count, "status": "ok"})
            if count > 0:
                print(f"  [{i:2d}/{len(companies)}] ✓ {cname}: {count} 条")
        except asyncio.TimeoutError:
            scrape_results.append({"id": cid, "name": cname, "count": 0, "status": "timeout"})
            print(f"  [{i:2d}/{len(companies)}] ⏱ {cname}: 超时")
        except Exception as e:
            scrape_results.append({"id": cid, "name": cname, "count": 0, "status": "error", "error": str(e)[:100]})
            print(f"  [{i:2d}/{len(companies)}] ✗ {cname}: {type(e).__name__}")

    print(f"\n  抓取完成: {total_scraped} 条岗位")

    # ====== Step 2: 数据清洗 ======
    print(f"\n▶ Step 2: 数据清洗...")
    from pipeline.clean import clean_all

    cleaned_count = clean_all(
        input_dir=str(PROJECT_ROOT / "data" / "raw"),
        output_file=str(PROJECT_ROOT / "data" / "cleaned" / "cleaned_jobs.jsonl"),
    )
    print(f"  清洗后: {cleaned_count} 条")

    # ====== Step 3: 学历筛选（研究生及以上）======
    print(f"\n▶ Step 3: 学历筛选（研究生及以上）+ 地点筛选（中国大陆）+ 公司筛选（国内）...")
    filter_stats = filter_graduate_jobs(
        input_file=str(PROJECT_ROOT / "data" / "cleaned" / "cleaned_jobs.jsonl"),
        output_file=str(PROJECT_ROOT / "data" / "cleaned" / "graduate_jobs.jsonl"),
    )
    print(f"  总岗位: {filter_stats['total']}")
    print(f"  保留: {filter_stats['kept']}")
    print(f"  筛除-学历不符: {filter_stats['filtered_out_edu']}")
    print(f"  筛除-非中国大陆: {filter_stats['filtered_out_location']}")
    print(f"  筛除-外企: {filter_stats['filtered_out_foreign']}")
    print(f"  学历分布: {filter_stats['by_education']}")

    # ====== Step 4: 交叉验证 ======
    print(f"\n▶ Step 4: 交叉验证 + 统计...")
    from pipeline.verify import verify_all

    stats = verify_all(
        input_file=str(PROJECT_ROOT / "data" / "cleaned" / "graduate_jobs.jsonl"),
        output_dir=str(PROJECT_ROOT / "data" / "verified"),
    )
    print(f"  验证后: {stats.get('total', 0)} 条岗位")
    print(f"  已验证: {stats.get('verified_count', 0)} ({stats.get('verified_ratio', 0)*100:.1f}%)")

    # ====== Step 5: 重建网站数据 ======
    print(f"\n▶ Step 5: 重建网站数据...")
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    import build_site

    build_site.build()
    print(f"  网站数据已更新")

    # ====== 汇总 ======
    print(f"\n{'='*60}")
    print(f"  ✅ 每日更新完成 — {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  抓取: {total_scraped} 条")
    print(f"  清洗后: {cleaned_count} 条")
    print(f"  筛选后(研究生+中国大陆+国内公司): {filter_stats['kept']} 条")
    print(f"    筛除: 学历{filter_stats['filtered_out_edu']} + 地点{filter_stats['filtered_out_location']} + 外企{filter_stats['filtered_out_foreign']}")
    print(f"  验证后: {stats.get('total', 0)} 条")
    print(f"{'='*60}")

    # 保存更新日志
    log = {
        "timestamp": now,
        "scraped": total_scraped,
        "cleaned": cleaned_count,
        "graduate_filtered": filter_stats,
        "verified": stats,
        "scrape_details": scrape_results,
    }
    log_file = PROJECT_ROOT / "data" / "daily_update_log.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"\n日志已保存: {log_file}")


if __name__ == "__main__":
    asyncio.run(run_daily_update())
