# AI 岗位调研网站

> 调研大厂/互联网公司/大模型厂商等 AI 相关岗位（技术岗+非技术岗）的秋招、实习情况，多源交叉验证，以可视化网站形式呈现。

## 快速开始

### 1. 环境准备
```bash
# 创建虚拟环境并安装依赖
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 2. 抓取数据
```bash
# 抓取单家公司
python scripts/run_scrape.py --company zhipu

# 抓取所有公司（批量，带超时）
python scripts/batch_scrape.py

# 列出所有公司
python scripts/run_scrape.py --list-companies
```

### 3. 数据处理流水线
```bash
# 清洗 → 分类 → 验证 → 导出（一键）
python scripts/run_pipeline.py
```

### 4. 打包网站数据
```bash
python scripts/build_site.py
```

### 5. 本地预览
```bash
cd site
python -m http.server 8765
# 浏览器打开 http://127.0.0.1:8765
```

## 项目结构

```
.
├── companies.json              # 45 家公司全量配置
├── scrapers/                   # 抓取器
│   ├── base.py                 # 抓取基类（httpx + Playwright 双模式）
│   ├── rate_limiter.py         # 按域名限速
│   ├── ua_pool.py              # UA 轮换池
│   ├── cache.py                # 增量抓取缓存
│   ├── platforms/              # SaaS 平台适配器
│   │   ├── feishu.py           # 飞书招聘（智谱/百川）
│   │   ├── beisen.py           # 北森招聘云（商汤）
│   │   ├── moka.py             # Moka（阶跃星辰）
│   │   └── job91.py            # 91job（东南大学就业中心）
│   ├── official/               # 自建官网适配器
│   │   └── generic_web.py      # 通用 SPA 抓取器
│   └── foreign/                # 外企抓取器
├── pipeline/                   # 数据处理
│   ├── clean.py                # 清洗（公司别名/地点/学历归一）
│   ├── classify.py             # 分类（技术/非技术 + AI相关度）
│   └── verify.py               # 交叉验证（并查集聚类+置信度）
├── data/                       # 数据存储
│   ├── raw/                    # 原始抓取
│   ├── cleaned/                # 清洗后
│   └── verified/               # 验证后（网站用）
├── site/                       # 静态网站
│   ├── index.html              # 数据看板（6 个 ECharts 图表）
│   ├── jobs.html               # 岗位列表（筛选+分页）
│   ├── detail.html             # 岗位详情（含所有来源）
│   ├── company.html            # 公司维度
│   ├── download.html           # 数据下载
│   └── assets/                 # CSS/JS/ECharts
└── scripts/                    # 脚本
    ├── run_scrape.py           # 抓取入口
    ├── batch_scrape.py         # 批量抓取
    ├── run_pipeline.py         # 一键流水线
    └── build_site.py           # 打包网站数据
```

## 数据来源

| 优先级 | 来源 | 覆盖 |
|--------|------|------|
| P0 | 各公司官方招聘官网 | 45 家全量 |
| P0 | 外企官网（+代理） | OpenAI/Anthropic/Google/MS/Meta/NVIDIA 等 |
| P1 | 校招垂直平台 | 牛客网/海投网/应届生 |
| P1 | 东南大学就业中心 | 91job 平台 |
| P2 | 第三方招聘平台 | BOSS直聘/拉勾/猎聘 |

## 交叉验证规则

- **同一岗位判定**：公司名标准化一致 + 标题相似度≥0.75 + 地点有交集
- **已验证(verified)**：≥2 个独立来源
- **待核实(single_source)**：仅 1 个来源
- **置信度评分**：基础40 + 多源+20/源 + 官方源+10 + 完整度+10 + 新鲜度0~10

## 技术栈

- **抓取**：Python 3.13 + Playwright + httpx + BeautifulSoup4
- **数据处理**：pandas + difflib（并查集聚类）
- **网站**：原生 HTML + ECharts 5.5（本地引用，无构建工具）
- **部署**：静态站，可任意托管（CloudStudio / GitHub Pages）

## 数据声明

- 仅供个人调研使用，不得用于商业用途
- 数据通过自动化抓取收集，可能存在延迟，以官方招聘网站为准
- 不存储任何个人数据
