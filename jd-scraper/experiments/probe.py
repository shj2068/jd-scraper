#!/usr/bin/env python3
"""
京东 API 探测脚本 - 尝试多种已知 functionId 和不同网关
找出可用的接口
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from python.sign import generate_sign
from python.fingerprint import FingerprintGenerator
from python.anti_detect import AntiDetect

import httpx

APPID = "ebf5a3c8"
CLIENT = "h5"
CLIENT_VERSION = "1.0.0"

# ── 多种已知京东 functionId（含通用 + 工业招商）──────────────────────
FUNCTION_IDS = [
    # 京东通用公开 API（通常在 api.m.jd.com 可用）
    ("getSearchResult", {"keyword": "工业", "page": "1", "pagesize": "10"}, "ebf5a3c8"),
    ("queryMaterialProducts", {"keyword": "轴承"}, "ebf5a3c8"),
    ("getRecommend", {"platform": "2"}, "ebf5a3c8"),
    # 京东工业品相关
    ("searchIndustryGoods", {"keyword": "轴承", "page": "1"}, "ebf5a3c8"),
    ("getIndustryCategoryList", {}, "ebf5a3c8"),
    # 招商网专用（来自技术文档）
    ("bizSearchCategoryList", {"cid": "0"}, "ebf5a3c8"),
    ("vendorQualificationQuery", {}, "ebf5a3c8"),
    ("supplierServiceProviderList", {"pageNo": 1, "pageSize": 10}, "ebf5a3c8"),
    ("jd_industry_news_list", {"pageNo": 1, "pageSize": 10}, "ebf5a3c8"),
]

# ── 多个可能的网关 URL ──────────────────────────────────────────────
GATEWAYS = [
    "https://api.m.jd.com/",
    "https://api.jd.com/routerJSON",
    "https://api.m.jd.com/api",
]


def build_params(function_id, body_dict, uuid, appid):
    body_str = json.dumps(body_dict, separators=(",", ":"))
    sign, t = generate_sign(
        function_id=function_id,
        body=body_str,
        uuid=uuid,
        appid=appid,
        client=CLIENT,
        client_version=CLIENT_VERSION,
    )
    return {
        "functionId": function_id,
        "appid": appid,
        "client": CLIENT,
        "clientVersion": CLIENT_VERSION,
        "t": t,
        "uuid": uuid,
        "sign": sign,
        "body": body_str,
    }


def probe(client, url, fid, body, appid, uuid, anti):
    """探测单个接口"""
    params = build_params(fid, body, uuid, appid)
    headers = anti.build_stealth_headers()

    try:
        resp = client.get(url, params=params, headers=headers, timeout=10.0)
        try:
            data = resp.json()
            code = data.get("code", "?")
            echo = data.get("echo", data.get("message", ""))
            has_data = bool(data.get("data") or data.get("result") or data.get("items"))
            return {
                "fid": fid,
                "url": url,
                "status": resp.status_code,
                "code": str(code),
                "echo": str(echo)[:80],
                "has_data": has_data,
                "keys": list(data.keys())[:8],
                "data_preview": json.dumps(data, ensure_ascii=False)[:300],
            }
        except Exception:
            return {
                "fid": fid,
                "url": url,
                "status": resp.status_code,
                "code": "non_json",
                "echo": resp.text[:100],
                "has_data": False,
            }
    except Exception as e:
        return {
            "fid": fid,
            "url": url,
            "status": 0,
            "code": "error",
            "echo": str(e)[:100],
            "has_data": False,
        }


def main():
    print("=" * 70)
    print("  京东 API 探测 - 寻找可用接口")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    fp_gen = FingerprintGenerator(platform="mobile")
    uuid = fp_gen.get_or_create_uuid()
    anti = AntiDetect(random_delay_range=(0.3, 0.8))

    print(f"  UUID: {uuid}")
    print(f"  待测 functionId: {len(FUNCTION_IDS)} 个")
    print(f"  待测网关: {len(GATEWAYS)} 个")
    print()

    results = []

    with httpx.Client(
        timeout=10.0,
        follow_redirects=True,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        },
    ) as client:
        # 阶段 1: 在主要网关测试所有 functionId
        gateway = GATEWAYS[0]
        print(f"[阶段 1] 在 {gateway} 上探测 {len(FUNCTION_IDS)} 个 functionId")
        print("-" * 70)

        for fid, body, appid in FUNCTION_IDS:
            r = probe(client, gateway, fid, body, appid, uuid, anti)
            results.append(r)
            status_icon = "✓" if r["has_data"] else ("?" if r["code"] not in ("2", "error", "non_json") else "✗")
            print(f"  {status_icon} {fid:<35} code={r['code']:<8} {r['echo'][:50]}")
            time.sleep(0.3)

        # 阶段 2: 对返回非 "API不存在" 的接口，换网关再试
        interesting = [r for r in results if r["code"] not in ("2", "error", "non_json")]
        if interesting:
            print(f"\n[阶段 2] {len(interesting)} 个有趣结果，在其他网关重试")
            for r in interesting:
                for gw in GATEWAYS[1:]:
                    r2 = probe(client, gw, r["fid"], {}, APPID, uuid, anti)
                    print(f"  {gw}: code={r2['code']} {r2['echo'][:50]}")
                    time.sleep(0.2)

        # 阶段 3: 尝试直接访问招商网首页获取 Cookie
        print(f"\n[阶段 3] 访问招商网首页获取初始 Cookie")
        try:
            resp = client.get(
                "https://zhaoshang.jd.com/",
                headers={"User-Agent": anti.get_user_agent()},
                timeout=10.0,
            )
            print(f"  zhaoshang.jd.com: status={resp.status_code}, len={len(resp.text)}")
            # 提取 set-cookie
            for k, v in resp.headers.items():
                if k.lower() == "set-cookie":
                    print(f"  Set-Cookie: {v[:100]}")
        except Exception as e:
            print(f"  访问失败: {e}")

    # ── 汇总 ──────────────────────────────────────────────────────
    print("\n\n" + "=" * 70)
    print("  探测结果汇总")
    print("=" * 70)

    # 分类统计
    found = [r for r in results if r["has_data"]]
    api_exists = [r for r in results if r["code"] not in ("2", "error", "non_json") and not r["has_data"]]
    not_found = [r for r in results if r["code"] == "2"]

    print(f"  有数据返回: {len(found)} 个")
    print(f"  接口存在但无数据: {len(api_exists)} 个")
    print(f"  接口不存在: {len(not_found)} 个")

    if found:
        print(f"\n  [有数据的接口]")
        for r in found:
            print(f"    {r['fid']}: {r['data_preview'][:200]}")

    if api_exists:
        print(f"\n  [接口存在但无数据的]")
        for r in api_exists:
            print(f"    {r['fid']}: code={r['code']} echo={r['echo']}")

    # 保存结果
    output = PROJECT_ROOT / "data" / f"probe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": len(results),
            "found": len(found),
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  结果已保存: {output}")
    print("=" * 70)


if __name__ == "__main__":
    main()
