"""
岗位分类器——判定技术岗/非技术岗 + AI 相关度。

基于关键词表 + 规则匹配，不依赖外部 AI API。
"""
from __future__ import annotations

import re

# 技术岗关键词（岗位名或职责中包含即判定为技术岗）
TECH_KEYWORDS = [
    # 算法类
    "算法", "机器学习", "深度学习", "NLP", "CV", "计算机视觉", "自然语言处理",
    "推荐", "搜索", "语音", "图像", "视觉", "大模型", "LLM", "AIGC", "生成式",
    "强化学习", "RL", "多模态", "VLM", "Agent", "RAG", "Diffusion", "Transformer",
    # 工程类
    "开发", "工程师", "架构", "后端", "前端", "全栈", "客户端", "服务端",
    "iOS", "Android", "前端", "Web", "数据", "DBA", "运维", "DevOps", "SRE",
    "测试", "QA", "安全", "基础架构", "infra", "平台", "framework",
    # 数据类
    "数据科学", "数据分析", "数据挖掘", "数据工程", "ETL", "数仓",
    # 硬件/芯片
    "芯片", "硬件", "FPGA", "GPU", "CUDA", "编译器", "内核",
    # 研究
    "研究", "research", "科学家", "Scientist",
]

# 非技术岗关键词
NON_TECH_KEYWORDS = [
    "产品经理", "产品", "PM", "运营", "市场", "营销", "商务", "销售",
    "HR", "人力资源", "财务", "法务", "行政", "设计", "UI", "UX",
    "交互", "视觉设计", "品牌", "公关", "内容", "编辑", "策划",
    "项目管理", "Project Manager", "顾问", "咨询", "战略",
    "解决方案", "售前", "售后", "客服", "支持", "培训",
]

# AI 核心关键词（用于判定 AI 相关度）
AI_CORE_KEYWORDS = [
    "AI", "人工智能", "大模型", "LLM", "AIGC", "生成式", "ChatGPT",
    "GPT", "BERT", "Transformer", "Diffusion", "深度学习", "机器学习",
    "神经网络", "NLP", "CV", "计算机视觉", "自然语言处理", "强化学习",
    "多模态", "VLM", "Agent", "RAG", "大语言模型", "AGI",
    "智能", "智算", "推理", "训练", "微调", "fine-tune", "对齐",
    "GLM", "GPT", "Claude", "Gemini", "Llama", "Stable Diffusion",
]

# AI 相关行业关键词
AI_INDUSTRY_KEYWORDS = [
    "自动驾驶", "机器人", "智能客服", "智能语音", "智能推荐",
    "计算机视觉", "人脸识别", "语音识别", "语义", "知识图谱",
]


def classify_category(title: str, responsibilities: str = "") -> str:
    """判定岗位类别：tech / non_tech。

    优先级：技术关键词命中数 > 非技术关键词命中数。
    """
    text = f"{title} {responsibilities}".lower()
    title_lower = title.lower()

    tech_score = 0
    non_tech_score = 0

    for kw in TECH_KEYWORDS:
        kw_lower = kw.lower()
        if kw_lower in title_lower:
            tech_score += 3  # 标题命中权重高
        if kw_lower in text:
            tech_score += 1

    for kw in NON_TECH_KEYWORDS:
        kw_lower = kw.lower()
        if kw_lower in title_lower:
            non_tech_score += 3
        if kw_lower in text:
            non_tech_score += 1

    if tech_score > non_tech_score:
        return "tech"
    elif non_tech_score > tech_score:
        return "non_tech"
    else:
        # 平局时，含"工程师"默认技术岗
        if "工程师" in title or "开发" in title:
            return "tech"
        return "non_tech"


def classify_ai_relevance(title: str, responsibilities: str = "", company_category: str = "") -> tuple[str, list[str]]:
    """判定 AI 相关度。

    返回 (ai_relevance, ai_keywords)：
      - core: 核心 AI 公司（company_category 为 llm_startup/ai_dragon/ai_startup）
      - high: 岗位名含 AI 关键词
      - medium: 职责描述含 AI 关键词
      - low: 无直接关系
    """
    text = f"{title} {responsibilities}"
    title_lower = title.lower()
    text_lower = text.lower()

    # 收集命中的 AI 关键词
    hit_keywords = []
    for kw in AI_CORE_KEYWORDS + AI_INDUSTRY_KEYWORDS:
        kw_lower = kw.lower()
        if kw_lower in title_lower or kw_lower in text_lower:
            hit_keywords.append(kw)

    # 核心AI公司默认 high 以上
    if company_category in ("llm_startup", "ai_dragon", "ai_startup"):
        if hit_keywords:
            return "core", hit_keywords
        else:
            return "high", hit_keywords  # 核心AI公司即使岗位名不含AI，也是high

    # 非核心公司，按命中情况判定
    title_hits = [kw for kw in AI_CORE_KEYWORDS + AI_INDUSTRY_KEYWORDS if kw.lower() in title_lower]
    desc_hits = [kw for kw in AI_CORE_KEYWORDS + AI_INDUSTRY_KEYWORDS if kw.lower() in text_lower and kw not in title_hits]

    if title_hits:
        return "high", title_hits
    elif desc_hits:
        return "medium", desc_hits
    else:
        return "low", []


def classify_job(job: dict) -> dict:
    """对单条岗位进行分类，返回更新后的 job dict。"""
    title = job.get("title", "")
    responsibilities = job.get("responsibilities", "")
    company_category = job.get("company_category", "")

    job["category"] = classify_category(title, responsibilities)
    job["ai_relevance"], job["ai_keywords"] = classify_ai_relevance(title, responsibilities, company_category)

    return job


def classify_all(jobs: list[dict]) -> list[dict]:
    """批量分类。"""
    return [classify_job(job) for job in jobs]


if __name__ == "__main__":
    # 测试
    test_cases = [
        {"title": "AI 产品经理", "responsibilities": "负责AI产品规划", "company_category": "big_tech"},
        {"title": "大模型算法工程师", "responsibilities": "LLM训练与微调", "company_category": "llm_startup"},
        {"title": "前端开发工程师", "responsibilities": "React开发", "company_category": "big_tech"},
        {"title": "解决方案架构师-北京", "responsibilities": "AI解决方案", "company_category": "llm_startup"},
        {"title": "市场营销专员", "responsibilities": "品牌推广", "company_category": "big_tech"},
    ]
    for j in test_cases:
        result = classify_job(j.copy())
        print(f"  {j['title']:30s} -> category={result['category']:10s} ai={result['ai_relevance']:8s} kw={result['ai_keywords']}")
