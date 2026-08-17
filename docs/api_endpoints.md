# 15 家公司招聘 API 逆向清单

> 调研时间：2026-07-16
> 调研方法：WebFetch 抓取页面 + GitHub/CSDN/牛客网搜索交叉验证
> 重要说明：WebFetch 不执行 JS，无法捕获 SPA 运行时 XHR。下表中"明文 JSON API"为社区已公开验证的可直接调用接口；"需 Playwright"表示前端接口有签名/加密/SSR 渲染，必须用浏览器执行 JS 才能拿到数据。

## 一、按平台归类（重要）

15 家公司实际只用了 **6 套招聘系统**，优先按平台复用爬虫：

| 平台 | 适用公司 | 项目内爬虫 |
|------|---------|-----------|
| 自研原生 API | 百度、网易、京东（部分） | `scrapers/official/` |
| Moka（app.mokahr.com） | 快手、旷视、寒武纪 | `scrapers/platforms/moka.py` |
| 飞书招聘（jobs.feishu.cn） | MiniMax | `scrapers/platforms/feishu.py` |
| 北森（italent.cn / zhiye.com） | 商汤 | 需新增 `scrapers/platforms/beisen.py` |
|重度 SPA（需 Playwright）| 阿里、华为、滴滴、360、月之暗面 | `scrapers/official/browser_api.py` |
| 无公开入口 | 新浪微博、第四范式 | — |

## 二、JSON 配置清单

```json
{
  "baidu": {
    "platform": "self",
    "api_url": "https://talent.baidu.com/httservice/getPostListNew",
    "method": "POST",
    "content_type": "application/x-www-form-urlencoded",
    "headers": {
      "Referer": "https://talent.baidu.com/jobs/social-list?search=",
      "User-Agent": "Mozilla/5.0"
    },
    "params": {
      "recruitType": "SOCIAL",
      "pageSize": 10,
      "curPage": 1,
      "keyWord": "AI",
      "projectType": ""
    },
    "param_notes": "recruitType 可选 SOCIAL(社招) / CAMPUS(校招); curPage 从 1 开始",
    "response_path": "data.list",
    "fields": {
      "id": "postId",
      "title": "name",
      "description": "serviceCondition",
      "responsibility": "workContent",
      "location": "workPlace",
      "publish_date": "publishDate",
      "category": "postType"
    },
    "legacy_api": "https://talent.baidu.com/baidu/web/httpservice/getPostList?workPlace=&recruitType=2&pageSize=10&curPage=1",
    "notes": "可直接 requests 调用,无需 cookie. 社区有多份验证代码"
  },

  "netease": {
    "platform": "self",
    "api_url": "https://hr.163.com/api/hr163/position/queryPage",
    "method": "POST",
    "content_type": "application/json",
    "headers": {
      "User-Agent": "Mozilla/5.0",
      "Referer": "https://hr.163.com/"
    },
    "params": {
      "pageNumber": 1,
      "pageSize": 10,
      "categoryStr": "",
      "typeStr": "技术类",
      "cityStr": "",
      "searchStr": "AI"
    },
    "response_path": "data.list",
    "fields": {
      "id": "id",
      "title": "productName",
      "department": "firstDepName",
      "education": "reqEducationName",
      "work_years": "reqWorkYearsName",
      "locations": "workPlaceNameList",
      "update_time": "updateTime"
    },
    "notes": "返回体含 lastPage 字段可判断分页. 互娱事业群另有 hr.game.163.com"
  },

  "jd": {
    "platform": "self_partial",
    "api_url": "https://campus.jd.com/api/wx/position/index",
    "method": "GET",
    "params": {
      "pageNum": 1,
      "pageSize": 10,
      "keyword": "AI",
      "emplErp": ""
    },
    "response_path": "data",
    "fields": {
      "title": "name",
      "category": "jobType",
      "location": "workPlace",
      "publish_date": "publishDate"
    },
    "encrypted_endpoints": {
      "url": "https://campus.jd.com/api/wx/delivery/officialInfo/list",
      "field": "body",
      "encryption": "AES-128-CBC",
      "key_utf8": "63ca0d3f90f844928d236e132a1fee45",
      "iv_hex": "0000000000000000",
      "padding": "Pkcs7",
      "note": "仅投递进度查询接口加密,岗位列表接口通常明文"
    },
    "new_site": "https://zhaopin.jd.com/",
    "notes": "京东已有新版招聘主站 zhaopin.jd.com,实际抓取建议用 Playwright 兜底"
  },

  "alibaba": {
    "platform": "playwright",
    "reason": "talent.alibaba.com 为纯 CSR 的 SPA,岗位数据由前端 JS 动态拉取,未在内联 HTML 中暴露 API 路径",
    "portal_url": "https://talent.alibaba.com/campus",
    "subsites": [
      "淘天集团", "阿里国际", "阿里云", "通义实验室", "钉钉",
      "千问C端", "平头哥", "高德", "菜鸟", "虎鲸文娱", "盒马", "阿里健康", "灵犀互娱"
    ],
    "official_open_api": {
      "url": "https://open.taobao.com/api.htm?apiId=61394",
      "api_list": [
        "alibaba.recruit.campus.notice.getlist (校招公告)",
        "alibaba.recruit.campus.apply.validate (校招投递验证)",
        "alibaba.recruit.social.position.related (社招关联职位)"
      ],
      "note": "需淘宝开放平台 appkey/secret,仅供合作方,不适合公开爬虫"
    },
    "fallback": "scrapers/official/alibaba.py + browser_api.py"
  },

  "huawei": {
    "platform": "playwright",
    "reason": "career.huawei.com 为高度 SPA,含反爬机制,Fetch/XHR 接口路径未在社区公开",
    "campus_url": "https://career.huawei.com/cn/campus-recruitment",
    "job_list_url": "https://career.huawei.com/cn/campus-recruitment-job-list",
    "social_url": "https://career.huawei.com/reccampportal/portal5/social-recruitment.html",
    "notes": "CSDN 已有多个 Playwright/Selenium 抓取示例验证可行,接口藏在 /reccampportal/ 下且参数签名",
    "fallback": "scrapers/official/huawei.py + browser_api.py"
  },

  "didi": {
    "platform": "playwright",
    "reason": "talent.didiglobal.com 为纯 CSR 的 SPA,首页 HTML 只有标题文本",
    "campus_url": "https://talent.didiglobal.com/campus/list",
    "mobile_url": "https://talent.didiglobal.com/m?jobType=1",
    "mobile_hint": "mobile 版本返回 SSR 渲染后的岗位列表(可看到 JR20260327004 这样的 job id),可作为降级方案",
    "fallback": "scrapers/official/didi.py + browser_api.py"
  },

  "kuaishou": {
    "platform": "moka",
    "reason": "campus.kuaishou.cn 使用 Moka 招聘系统,hash 路由 #/campus/jobs,数据由前端从 mokahr 后端拉取",
    "portal_url": "https://campus.kuaishou.cn/#/campus/jobs",
    "moka_apply_url": "https://app.mokahr.com/m/campus_apply/kuaishou",
    "fallback": "scrapers/platforms/moka.py"
  },

  "qihoo360": {
    "platform": "playwright",
    "reason": "hr.360.cn 为静态落地页,校招实际跳转 campus.360.cn,后者为重度 SPA",
    "campus_url": "https://campus.360.cn/",
    "social_url": "https://hr.360.cn/hr/list",
    "fallback": "scrapers/official/qihoo360.py + browser_api.py"
  },

  "moonshot_kimi": {
    "platform": "playwright",
    "reason": "careers.kimi.com 为纯 CSR 的 SPA,首屏只有 logo,数据完全由 JS 拉取",
    "portal_url": "https://careers.kimi.com/",
    "fallback": "scrapers/official/moonshot.py + browser_api.py"
  },

  "minimax": {
    "platform": "feishu",
    "reason": "MiniMax 招聘已完全托管给飞书招聘 vrfi1sk8a0.jobs.feishu.cn",
    "feishu_channels": {
      "top_talent": "https://vrfi1sk8a0.jobs.feishu.cn/379481/?project=7496820276634634537",
      "campus_2027": "https://vrfi1sk8a0.jobs.feishu.cn/379481/?project=7495675705720965415",
      "intern_2028": "https://vrfi1sk8a0.jobs.feishu.cn/379481/?project=7352753013591755047",
      "social": "https://vrfi1sk8a0.jobs.feishu.cn/index/"
    },
    "feishu_api_params": {
      "keywords": "AI",
      "category": "",
      "location": "",
      "project": "<上述 project id>",
      "current": 1,
      "limit": 10
    },
    "fallback": "scrapers/platforms/feishu.py"
  },

  "sensetime": {
    "platform": "beisen",
    "reason": "商汤使用北森招聘系统,原 URL hr.sensetime.com/SU.../pb/school.html 已 404,新地址需重新定位",
    "beisen_pattern": "北森招聘站点形如 https://{tenant}.italent.cn 或 https://{tenant}.zhiye.com",
    "beisen_open_api": {
      "url": "https://openapi.italent.cn/RecruitV6/api/v1/Job/GetJobList",
      "method": "POST",
      "note": "OpenAPI 需企业 tenant 授权,外部爬虫不可用. 前端页面爬取需 Playwright"
    },
    "action": "需在浏览器访问 sensetime 官网找到新的招聘子域名后再配置",
    "fallback": "新增 scrapers/platforms/beisen.py"
  },

  "megvii": {
    "platform": "moka",
    "reason": "旷视校招已托管给 Moka",
    "campus_url": "https://app.mokahr.com/m/campus_apply/megviihr/38642",
    "legacy_social_url": "http://zhaopin.megvii.com/search",
    "note": "老站点 zhaopin.megvii.com 可能已弃用,以 mokahr 为准",
    "fallback": "scrapers/platforms/moka.py"
  },

  "cambricon": {
    "platform": "moka",
    "reason": "寒武纪招聘官网 joinus.cambricon.com 的 URL 结构 /apply/cambricon 为典型 Moka 模板",
    "portal_url": "https://joinus.cambricon.com/apply/cambricon",
    "fallback": "scrapers/platforms/moka.py"
  },

  "sina_weibo": {
    "platform": "none",
    "reason": "career.sina.com.cn/campus 已 404(openresty 1.19.9.1). 新浪&微博 2026 校招完全走微信公众号「新浪招聘」+ 邮箱 sinacampus@sina.com,无公开网页 API",
    "alternative": "只能通过 BOSS 直聘/牛客网/高校就业网间接抓取",
    "status": "无法逆向"
  },

  "4paradigm": {
    "platform": "none",
    "reason": "4paradigm.com 官网「焕新升级中」暂停服务,/careers/campus 返回 404 图片. 当前无公开招聘页面",
    "alternative": "BOSS 直聘有岗位,或关注官方公众号",
    "status": "无法逆向(临时)"
  }
}
```

## 三、关键结论

### 可直接 requests 调用（无需浏览器）
- **百度**：`https://talent.baidu.com/httservice/getPostListNew`（POST，社区验证）
- **网易**：`https://hr.163.com/api/hr163/position/queryPage`（POST，社区验证）
- **京东**：`https://campus.jd.com/api/wx/position/index`（GET，岗位列表明文；投递进度接口 AES 加密）

### 必须用 Playwright（SPA + 无公开 API）
- 阿里巴巴、华为、滴滴、360、月之暗面
- 项目内已有 `scrapers/official/browser_api.py` 兜底

### 第三方招聘平台（优先复用平台爬虫）
- **Moka**：快手、旷视、寒武纪 → `scrapers/platforms/moka.py`
- **飞书招聘**：MiniMax → `scrapers/platforms/feishu.py`
- **北森**：商汤 → 需新增 `scrapers/platforms/beisen.py`

### 无法逆向
- **新浪微博**：官网 404，全部走公众号
- **第四范式**：官网改版中，无招聘页面

## 四、下一步建议

1. **优先级 P0**：把百度/网易/京东改成直接调用 JSON API，绕过 Playwright，速度提升 10x+
2. **优先级 P1**：新增 `scrapers/platforms/beisen.py`，覆盖商汤等北森系公司
3. **优先级 P2**：快手、旷视、寒武纪、MiniMax 全部改走平台爬虫（moka/feishu），移除 official 目录下的重复实现
4. **优先级 P3**：新浪微博、第四范式 从 companies.json 中标记为 `status: "unavailable"`，避免无效重试
