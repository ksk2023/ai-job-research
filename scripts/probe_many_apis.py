"""批量探测各大厂招聘 API 的可用性。
对每个公司尝试多种已知 API 格式，找出可用的。
"""
import asyncio
import json
import time
import sys

import httpx

# 已知的招聘 API 端点（按平台类型分组）
API_CANDIDATES = [
    # 腾讯（已验证）
    {
        "id": "tencent",
        "name": "腾讯",
        "url": "https://careers.tencent.com/tencentcareer/api/post/Query",
        "method": "GET",
        "params": {"timestamp": "{ts}", "pageIndex": "0", "pageSize": "10", "keyword": "AI"},
        "data_path": ["Data", "Posts"],
    },
    # 阿里巴巴
    {
        "id": "alibaba",
        "name": "阿里巴巴",
        "url": "https://talent.alibaba.com/off-campus/position-list",
        "method": "POST",
        "json_body": {"pageNumber": 1, "pageSize": 10, "keyword": "AI"},
        "data_path": ["data", "data", "list"],
    },
    {
        "id": "alibaba",
        "name": "阿里巴巴2",
        "url": "https://talent.alibaba.com/api/v2/position/list",
        "method": "GET",
        "params": {"keyword": "AI", "pageNum": "1", "pageSize": "10"},
        "data_path": ["data", "list"],
    },
    # 美团
    {
        "id": "meituan",
        "name": "美团",
        "url": "https://zhaopin.meituan.com/api/web/job/position/list",
        "method": "POST",
        "json_body": {"pageNum": 1, "pageSize": 10, "jobKeyword": "AI"},
        "data_path": ["data", "list"],
    },
    # 京东
    {
        "id": "jd",
        "name": "京东",
        "url": "https://campus.jd.com/officialWebsite/list",
        "method": "POST",
        "json_body": {"pageNo": 1, "pageSize": 10, "keyword": "AI"},
        "data_path": ["data", "list"],
    },
    # 网易
    {
        "id": "netease",
        "name": "网易",
        "url": "https://hr.163.com/api/hr163/position/search",
        "method": "POST",
        "json_body": {"keyword": "AI", "pageNum": 1, "pageSize": 10},
        "data_path": ["data", "list"],
    },
    # 拼多多
    {
        "id": "pdd",
        "name": "拼多多",
        "url": "https://careers.pinduoduo.com/api/position/list",
        "method": "POST",
        "json_body": {"keyword": "AI", "pageNo": 1, "pageSize": 10},
        "data_path": ["data", "list"],
    },
    # 滴滴
    {
        "id": "didi",
        "name": "滴滴",
        "url": "https://talent.didiglobal.com/api/job/list",
        "method": "POST",
        "json_body": {"keyword": "AI", "page": 1, "size": 10},
        "data_path": ["data", "list"],
    },
    # 小米
    {
        "id": "xiaomi",
        "name": "小米",
        "url": "https://hr.xiaomi.com/api/position/list",
        "method": "POST",
        "json_body": {"keyword": "AI", "pageNo": 1, "pageSize": 10},
        "data_path": ["data", "list"],
    },
    # 华为
    {
        "id": "huawei",
        "name": "华为",
        "url": "https://career.huawei.com/reccampportal/services/portal/portaluser/getJobList",
        "method": "POST",
        "json_body": {"keyword": "AI", "pageNum": 1, "pageSize": 10},
        "data_path": ["data", "list"],
    },
    # OPPO
    {
        "id": "oppo",
        "name": "OPPO",
        "url": "https://careers.oppo.com/api/position/list",
        "method": "POST",
        "json_body": {"keyword": "AI", "pageNo": 1, "pageSize": 10},
        "data_path": ["data", "list"],
    },
    # vivo
    {
        "id": "vivo",
        "name": "vivo",
        "url": "https://hr.vivo.com/api/position/list",
        "method": "POST",
        "json_body": {"keyword": "AI", "pageNo": 1, "pageSize": 10},
        "data_path": ["data", "list"],
    },
    # 快手
    {
        "id": "kuaishou",
        "name": "快手",
        "url": "https://campus.kuaishou.cn/api/position/list",
        "method": "POST",
        "json_body": {"keyword": "AI", "page": 1, "size": 10},
        "data_path": ["data", "list"],
    },
    # B站
    {
        "id": "bilibili",
        "name": "B站",
        "url": "https://jobs.bilibili.com/api/position/list",
        "method": "POST",
        "json_body": {"keyword": "AI", "pageNo": 1, "pageSize": 10},
        "data_path": ["data", "list"],
    },
    # 蚂蚁集团
    {
        "id": "ant",
        "name": "蚂蚁集团",
        "url": "https://talent.antgroup.com/api/position/list",
        "method": "POST",
        "json_body": {"keyword": "AI", "pageNo": 1, "pageSize": 10},
        "data_path": ["data", "list"],
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Content-Type": "application/json",
    "Referer": "https://www.google.com/",
    "Origin": "https://www.google.com",
}


async def probe(client: httpx.AsyncClient, api: dict) -> dict:
    """探测单个 API。"""
    ts = str(int(time.time() * 1000))
    url = api["url"]
    method = api.get("method", "GET")

    try:
        if method == "GET":
            params = api.get("params", {}).copy()
            for k, v in params.items():
                if v == "{ts}":
                    params[k] = ts
            resp = await client.get(url, params=params, headers=HEADERS, timeout=12)
        else:
            body = api.get("json_body", {})
            resp = await client.post(url, json=body, headers=HEADERS, timeout=12)

        ct = resp.headers.get("content-type", "")
        is_json = "json" in ct.lower()
        result = {
            "id": api["id"],
            "name": api["name"],
            "url": url,
            "status": resp.status_code,
            "len": len(resp.text),
            "is_json": is_json,
            "preview": resp.text[:200].replace("\n", " "),
        }

        if resp.status_code == 200 and is_json and len(resp.text) > 100:
            try:
                data = resp.json()
                # 按 data_path 找
                obj = data
                for key in api.get("data_path", []):
                    if isinstance(obj, dict) and key in obj:
                        obj = obj[key]
                    else:
                        obj = None
                        break
                if isinstance(obj, list) and obj:
                    result["found_jobs"] = len(obj)
                    result["first_job"] = json.dumps(obj[0], ensure_ascii=False)[:300]
                    result["status_ok"] = True
                else:
                    # 尝试递归找列表
                    lst = _find_job_list(data)
                    if lst:
                        result["found_jobs"] = len(lst)
                        result["first_job"] = json.dumps(lst[0], ensure_ascii=False)[:300]
                        result["status_ok"] = True
                        result["note"] = "递归找到列表"
                    else:
                        result["keys"] = list(data.keys())[:10] if isinstance(data, dict) else "N/A"
            except Exception as e:
                result["parse_error"] = str(e)[:100]
        return result
    except Exception as e:
        return {
            "id": api["id"],
            "name": api["name"],
            "url": url,
            "error": f"{type(e).__name__}: {str(e)[:100]}",
        }


def _find_job_list(obj, depth=0):
    """递归找岗位列表。"""
    if depth > 4:
        return None
    if isinstance(obj, list) and len(obj) > 0 and isinstance(obj[0], dict):
        # 看起来像岗位列表
        first = obj[0]
        if any(k in first for k in ["title", "name", "position", "job", "Post", "recruit"]):
            return obj
    if isinstance(obj, dict):
        for k in ["Posts", "posts", "job_post_list", "data", "result", "list",
                  "rows", "records", "jobs", "positions", "Data", "List"]:
            if k in obj:
                r = _find_job_list(obj[k], depth + 1)
                if r:
                    return r
    return None


async def main():
    print(f"将探测 {len(API_CANDIDATES)} 个 API 端点\n")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [probe(client, api) for api in API_CANDIDATES]
        results = await asyncio.gather(*tasks)

    ok = []
    fail = []
    for r in results:
        if r.get("status_ok"):
            ok.append(r)
            print(f"✓ [{r['id']:12s}] {r['name']:10s}  岗位数={r.get('found_jobs', 0)}")
            print(f"  URL: {r['url']}")
            print(f"  首条: {r.get('first_job', '')[:200]}")
            print()
        else:
            fail.append(r)
            err = r.get("error") or f"status={r.get('status')} len={r.get('len')} json={r.get('is_json')}"
            print(f"✗ [{r['id']:12s}] {r['name']:10s}  {err}")
            if r.get("preview"):
                print(f"  preview: {r['preview'][:120]}")

    print(f"\n========== 总结 ==========")
    print(f"可用 API: {len(ok)} / {len(results)}")
    print(f"失败: {len(fail)} / {len(results)}")
    print(f"\n可用公司:")
    for r in ok:
        print(f"  - {r['id']}: {r['url']}")

    # 保存结果
    with open("data/raw/_api_probe_result.json", "w", encoding="utf-8") as f:
        json.dump({"ok": ok, "fail": fail}, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存到 data/raw/_api_probe_result.json")


if __name__ == "__main__":
    asyncio.run(main())
