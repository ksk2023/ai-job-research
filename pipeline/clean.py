"""
数据清洗——字段标准化、公司别名归一、地点归一、学历枚举。

从 data/raw/*.jsonl 读取，输出到 data/cleaned/cleaned_jobs.jsonl。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# 公司别名表——把各种写法归一到标准名
COMPANY_ALIASES = {
    "字节": "字节跳动", "ByteDance": "字节跳动", "bytedance": "字节跳动", "字节跳动集团": "字节跳动",
    "腾讯": "腾讯", "Tencent": "腾讯", "tencent": "腾讯",
    "阿里": "阿里巴巴", "Alibaba": "阿里巴巴", "alibaba": "阿里巴巴", "阿里集团": "阿里巴巴",
    "百度": "百度", "Baidu": "百度", "baidu": "百度",
    "美团": "美团", "Meituan": "美团",
    "京东": "京东", "JD": "京东", "JD.com": "京东",
    "拼多多": "拼多多", "PDD": "拼多多", "Pinduoduo": "拼多多",
    "网易": "网易", "NetEase": "网易",
    "小红书": "小红书", "Xiaohongshu": "小红书",
    "华为": "华为", "Huawei": "华为",
    "米哈游": "米哈游", "miHoYo": "米哈游",
    "快手": "快手", "Kuaishou": "快手",
    "智谱": "智谱AI", "Zhipu": "智谱AI", "Zhipu AI": "智谱AI", "智谱清言": "智谱AI",
    "月之暗面": "月之暗面", "Moonshot": "月之暗面", "Moonshot AI": "月之暗面", "Kimi": "月之暗面",
    "百川": "百川智能", "Baichuan": "百川智能", "百川大模型": "百川智能",
    "MiniMax": "MiniMax", "minimax": "MiniMax",
    "阶跃星辰": "阶跃星辰", "StepFun": "阶跃星辰", "Step": "阶跃星辰",
    "DeepSeek": "深度求索", "deepseek": "深度求索", "深度求索": "深度求索",
    "商汤": "商汤科技", "SenseTime": "商汤科技", "sensetime": "商汤科技",
    "旷视": "旷视科技", "Megvii": "旷视科技", "旷视": "旷视科技",
    "海康": "海康威视", "Hikvision": "海康威视", "海康威视": "海康威视",
    "第四范式": "第四范式", "4Paradigm": "第四范式",
    "科大讯飞": "科大讯飞", "iFlytek": "科大讯飞", "讯飞": "科大讯飞",
    "OpenAI": "OpenAI", "openai": "OpenAI",
    "Anthropic": "Anthropic", "anthropic": "Anthropic",
    "Google": "Google", "google": "Google", "谷歌": "Google",
    "Microsoft": "微软", "微软": "微软", "microsoft": "微软",
    "Meta": "Meta", "meta": "Meta", "Facebook": "Meta",
    "NVIDIA": "英伟达", "nvidia": "英伟达", "英伟达": "英伟达",
}

# 地点归一化（去掉"市""区"后缀，统一常见别名）
LOCATION_NORMALIZE = {
    "北京市": "北京", "上海市": "上海", "深圳市": "深圳", "广州市": "广州", "杭州市": "杭州",
    "成都市": "成都", "南京市": "南京", "武汉市": "武汉", "西安市": "西安", "苏州市": "苏州",
    "厦门市": "厦门", "长沙市": "长沙", "重庆市": "重庆", "青岛市": "青岛", "大连市": "大连",
    "宁波市": "宁波", "天津市": "天津", "济南市": "济南", "合肥市": "合肥", "福州市": "福州",
    "东莞市": "东莞", "佛山市": "佛山", "常州市": "常州", "无锡市": "无锡", "珠海市": "珠海",
    "杭州市西湖区": "杭州", "北京市海淀区": "北京", "北京市朝阳区": "北京", "上海市浦东新区": "上海",
    "深圳南山": "深圳", "北京海淀": "北京", "上海浦东": "上海", "杭州余杭": "杭州",
    "远程": "远程", "Remote": "远程", "remote": "远程",
    "Singapore": "新加坡", "新加坡": "新加坡", "硅谷": "硅谷", "Silicon Valley": "硅谷",
    "Seattle": "西雅图", "San Francisco": "旧金山", "New York": "纽约",
}

# 学历归一化
EDUCATION_NORMALIZE = {
    "博士": "博士及以上", "博士及以上": "博士及以上",
    "硕士": "硕士及以上", "硕士及以上": "硕士及以上",
    "本科": "本科及以上", "本科及以上": "本科及以上",
    "大专": "大专及以上", "大专及以上": "大专及以上",
    "不限": "不限", "无要求": "不限",
}


def normalize_company(name: str) -> str:
    """公司名归一化。"""
    if not name:
        return ""
    name = name.strip()
    return COMPANY_ALIASES.get(name, name)


def normalize_location(loc: str | list) -> list[str]:
    """地点归一化，返回标准地点列表。"""
    if not loc:
        return []
    if isinstance(loc, str):
        locs = [loc]
    else:
        locs = loc

    result = []
    for l in locs:
        if not l:
            continue
        l = str(l).strip()
        # 处理"北京/上海"这种分隔
        for part in re.split(r"[/、,，\|]+", l):
            part = part.strip()
            if not part:
                continue
            # 归一化
            normalized = LOCATION_NORMALIZE.get(part, part)
            # 去掉"市""区"后缀
            normalized = re.sub(r"[市区县]$", "", normalized) if len(normalized) > 2 else normalized
            if normalized and normalized not in result:
                result.append(normalized)
    return result


def normalize_education(edu: str) -> str:
    """学历要求归一化。"""
    if not edu:
        return ""
    edu = str(edu).strip()
    # 尝试匹配
    for key, val in EDUCATION_NORMALIZE.items():
        if key in edu:
            return val
    return edu


def clean_job(job: dict) -> dict:
    """清洗单条岗位记录。"""
    cleaned = job.copy()

    # 公司名归一
    cleaned["company"] = normalize_company(job.get("company", ""))
    if job.get("company_raw"):
        cleaned["company_raw"] = job["company_raw"]
        cleaned["company_raw_normalized"] = normalize_company(job["company_raw"])

    # 地点归一
    cleaned["location"] = normalize_location(job.get("location", []))
    cleaned["location_raw"] = job.get("location_raw", "")

    # 学历归一
    cleaned["education"] = normalize_education(job.get("education", ""))

    # 标题清理
    title = job.get("title", "").strip()
    cleaned["title"] = title
    cleaned["title_raw"] = job.get("title_raw", title)

    # 职责描述清理（去除多余空白）
    resp = job.get("responsibilities", "")
    if resp:
        cleaned["responsibilities"] = re.sub(r"\n{3,}", "\n\n", resp).strip()

    # source_url 清理
    url = job.get("source_url", "")
    if url and not url.startswith("http") and not url.startswith("job_id:"):
        cleaned["source_url"] = ""  # 无效URL清空
    else:
        cleaned["source_url"] = url

    return cleaned


def clean_all(input_dir: str = "data/raw", output_file: str = "data/cleaned/cleaned_jobs.jsonl") -> int:
    """清洗所有 raw 数据，输出到 cleaned_jobs.jsonl。返回清洗后的岗位数。"""
    input_path = Path(input_dir)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_jobs = []
    for jsonl_file in sorted(input_path.glob("*.jsonl")):
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    job = json.loads(line)
                    cleaned = clean_job(job)
                    all_jobs.append(cleaned)
                except Exception as e:
                    print(f"  解析失败 {jsonl_file.name}: {e}")

    # 同源内去重（按 company + title + location）
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        key = f"{job.get('company','')}|{job.get('title','')}|{','.join(job.get('location',[]))}"
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)

    with open(output_path, "w", encoding="utf-8") as f:
        for job in unique_jobs:
            f.write(json.dumps(job, ensure_ascii=False) + "\n")

    print(f"清洗完成: {len(all_jobs)} -> {len(unique_jobs)} 条（去重 {len(all_jobs) - len(unique_jobs)} 条）")
    print(f"输出: {output_path}")
    return len(unique_jobs)


if __name__ == "__main__":
    clean_all()
