"""
交叉验证引擎——多源匹配 + 置信度评分 + 聚类合并。

输入: data/cleaned/cleaned_jobs.jsonl
输出:
  - data/verified/jobs.json  (网站加载用)
  - data/verified/jobs.csv   (下载用)
  - data/verified/stats.json (仪表盘统计用)
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from .clean import normalize_company, normalize_location


def title_similarity(a: str, b: str) -> float:
    """计算两个岗位标题的相似度（去除地点/括号/空白后比较）。"""
    if not a or not b:
        return 0.0
    # 清理：去掉地点、括号、特殊字符
    clean = lambda s: re.sub(r"[\s【】\[\]（）()·/、,，\-_]+", "", s)
    a_clean = clean(a)
    b_clean = clean(b)
    if not a_clean or not b_clean:
        return 0.0
    # 完全包含关系也算高相似度
    if a_clean in b_clean or b_clean in a_clean:
        return 0.9
    return SequenceMatcher(None, a_clean, b_clean).ratio()


def location_overlap(loc_a: list, loc_b: list) -> bool:
    """判断两个地点列表是否有交集。"""
    if not loc_a or not loc_b:
        return True  # 空地点视为匹配（不阻塞）

    def to_str_list(locs):
        """把可能嵌套的 location 统一成字符串列表。"""
        out = []
        if not isinstance(locs, list):
            locs = [locs]
        for l in locs:
            if isinstance(l, list):
                out.extend(to_str_list(l))
            elif isinstance(l, str):
                if l.strip():
                    out.append(l.strip())
            else:
                out.append(str(l))
        return out

    # normalize_location 返回 list[str]，展开后放进 set
    norm_a = set()
    for l in to_str_list(loc_a):
        for n in normalize_location(l):
            norm_a.add(n)
    norm_b = set()
    for l in to_str_list(loc_b):
        for n in normalize_location(l):
            norm_b.add(n)
    return bool(norm_a & norm_b)


def is_same_job(j1: dict, j2: dict) -> bool:
    """判断两条记录是否为同一岗位。"""
    # 公司名标准化后比较
    c1 = normalize_company(j1.get("company", ""))
    c2 = normalize_company(j2.get("company", ""))
    if c1 != c2:
        return False
    # 标题相似度
    sim = title_similarity(j1.get("title", ""), j2.get("title", ""))
    if sim < 0.75:
        return False
    # 地点交集
    if not location_overlap(j1.get("location", []), j2.get("location", [])):
        return False
    return True


def cluster_jobs(all_jobs: list[dict]) -> list[list[dict]]:
    """用并查集聚合同一岗位的多条来源记录。"""
    n = len(all_jobs)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    # O(n²) 匹配（数据量 < 5000 可接受）
    for i in range(n):
        for j in range(i + 1, n):
            if is_same_job(all_jobs[i], all_jobs[j]):
                union(i, j)

    clusters = defaultdict(list)
    for i, job in enumerate(all_jobs):
        clusters[find(i)].append(job)

    return list(clusters.values())


def compute_confidence(cluster: list[dict]) -> int:
    """计算置信度评分 (0-100)。

    基础分 40 + 多源 +20/源(最多+40) + 官方源 +10 + 完整度 +10 + 新鲜度 0~10
    """
    score = 40
    # 多源加分
    source_count = len(cluster)
    score += min(source_count - 1, 2) * 20
    # 官方源加分
    has_official = any(j.get("source_type") == "official" for j in cluster)
    if has_official:
        score += 10
    # 完整度加分
    main = max(cluster, key=lambda j: len(str(j.get("responsibilities", ""))))
    if all(main.get(k) for k in ["education", "responsibilities"]) and main.get("location"):
        score += 10
    # 新鲜度加分（简化：有 post_date 就 +5，30天内 +10）
    post_date = main.get("post_date", "")
    if post_date:
        score += 5
        try:
            # 尝试解析日期
            date_str = str(post_date)[:10]
            post_dt = datetime.fromisoformat(date_str)
            days_ago = (datetime.now() - post_dt).days
            if days_ago <= 30:
                score += 5
        except Exception:
            pass
    return min(score, 100)


def verify_cluster(cluster: list[dict]) -> dict:
    """合并一个簇，输出验证后的单条岗位。"""
    # 选信息最全的一条作为主体
    main = max(cluster, key=lambda j: len(str(j.get("responsibilities", ""))))

    # 收集所有来源
    all_sources = []
    for j in cluster:
        all_sources.append({
            "platform": j.get("source_platform", ""),
            "url": j.get("source_url", ""),
            "scraped_at": j.get("scraped_at", ""),
            "source_type": j.get("source_type", ""),
        })

    # 去重来源（按 url）
    seen_urls = set()
    unique_sources = []
    for s in all_sources:
        key = s.get("url", "") or s.get("platform", "")
        if key not in seen_urls:
            seen_urls.add(key)
            unique_sources.append(s)

    source_count = len(unique_sources)
    has_official = any(s.get("source_type") == "official" for s in unique_sources)

    # 验证状态
    if source_count >= 2:
        status = "verified"
    else:
        status = "single_source"

    confidence = compute_confidence(cluster)

    # 合并字段（主体优先，补充缺失字段）
    merged = main.copy()
    for j in cluster:
        for key in ["education", "responsibilities", "salary_raw", "description_html", "skills"]:
            if not merged.get(key) and j.get(key):
                merged[key] = j[key]

    merged["verification_status"] = status
    merged["confidence_score"] = confidence
    merged["all_sources"] = unique_sources
    merged["source_count"] = source_count
    merged["has_official_source"] = has_official

    return merged


def compute_stats(jobs: list[dict]) -> dict:
    """计算统计数据（首页仪表盘用）。"""
    from collections import Counter

    total = len(jobs)
    if total == 0:
        return {"total": 0}

    # 按公司类别
    by_category = Counter(j.get("company_category", "unknown") for j in jobs)
    # 按岗位类别
    by_job_category = Counter(j.get("category", "unknown") for j in jobs)
    # 按招聘类型
    by_job_type = Counter(j.get("job_type", "unknown") for j in jobs)
    # 按 AI 相关度
    by_ai_relevance = Counter(j.get("ai_relevance", "unknown") for j in jobs)
    # 按验证状态
    by_verification = Counter(j.get("verification_status", "unknown") for j in jobs)
    # 按公司
    by_company = Counter(j.get("company", "") for j in jobs)
    # 按地点
    location_counter = Counter()
    for j in jobs:
        for loc in j.get("location", []):
            location_counter[loc] += 1

    # 平均置信度
    avg_confidence = sum(j.get("confidence_score", 0) for j in jobs) / total

    return {
        "total": total,
        "company_count": len(by_company),
        "verified_count": by_verification.get("verified", 0),
        "verified_ratio": round(by_verification.get("verified", 0) / total, 3),
        "avg_confidence": round(avg_confidence, 1),
        "by_category": dict(by_category),
        "by_job_category": dict(by_job_category),
        "by_job_type": dict(by_job_type),
        "by_ai_relevance": dict(by_ai_relevance),
        "by_verification": dict(by_verification),
        "by_company": dict(by_company.most_common(20)),
        "by_location": dict(location_counter.most_common(15)),
        "generated_at": datetime.now().astimezone().isoformat(),
    }


def verify_all(
    input_file: str = "data/cleaned/cleaned_jobs.jsonl",
    output_dir: str = "data/verified",
) -> dict:
    """完整验证流程。"""
    input_path = Path(input_file)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 读取清洗后的数据
    jobs = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                jobs.append(json.loads(line))

    print(f"读取 {len(jobs)} 条清洗后岗位")

    # 聚类
    clusters = cluster_jobs(jobs)
    print(f"聚类为 {len(clusters)} 个岗位簇")

    # 验证每个簇
    verified_jobs = []
    for cluster in clusters:
        verified = verify_cluster(cluster)
        verified_jobs.append(verified)

    # 统计
    stats = compute_stats(verified_jobs)
    print(f"验证完成: {len(verified_jobs)} 条岗位")
    print(f"  已验证(多源): {stats['verified_count']} ({stats['verified_ratio']*100:.1f}%)")
    print(f"  平均置信度: {stats['avg_confidence']}")

    # 输出 jobs.json
    jobs_json_path = output_path / "jobs.json"
    with open(jobs_json_path, "w", encoding="utf-8") as f:
        json.dump(verified_jobs, f, ensure_ascii=False, indent=2)
    print(f"  已保存: {jobs_json_path}")

    # 输出 jobs.csv
    csv_path = output_path / "jobs.csv"
    import csv
    csv_fields = [
        "id", "company", "title", "category", "ai_relevance", "job_type",
        "location", "education", "verification_status", "confidence_score",
        "source_count", "source_url", "post_date", "scraped_at"
    ]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for job in verified_jobs:
            row = job.copy()
            row["location"] = "/".join(job.get("location", []))
            writer.writerow(row)
    print(f"  已保存: {csv_path}")

    # 输出 stats.json
    stats_path = output_path / "stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"  已保存: {stats_path}")

    return stats


if __name__ == "__main__":
    verify_all()
