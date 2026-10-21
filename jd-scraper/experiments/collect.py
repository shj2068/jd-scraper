#!/usr/bin/env python3
"""
京东工业招商网 - 实际数据采集脚本

直接对 https://api.m.jd.com/ 发起真实 HTTP 请求。
降级策略: JSRPC(无) -> 本地 sign -> 直接请求
"""

import json
import sys
import time
import traceback
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from python.sign import generate_sign
from python.fingerprint import FingerprintGenerator
from python.anti_detect import AntiDetect
from python.cookie_manager import CookieManager
from python.utils import setup_logger

logger = setup_logger("collect")

# ── 采集目标 ──────────────────────────────────────────────────────────
# 按加密等级从低到高排列，便于观察不同接口的返回差异
TARGETS = [
    {
        "name": "行业资讯（低加密）",
        "functionId": "jd_industry_news_list",
        "body": {"pageNo": 1, "pageSize": 10},
        "method": "GET",
    },
    {
        "name": "分类列表（中加密）",
        "functionId": "bizSearchCategoryList",
        "body": {"cid": "0"},
        "method": "GET",
    },
    {
        "name": "供应商列表（中加密）",
        "functionId": "supplierServiceProviderList",
        "body": {"pageNo": 1, "pageSize": 10},
        "method": "GET",
    },
]

JD_API = "https://api.m.jd.com/"
APPID = "ebf5a3c8"
CLIENT = "h5"
CLIENT_VERSION = "1.0.0"


def build_full_url(function_id: str, body: dict, uuid: str) -> tuple:
    """构建带 sign 的完整请求 URL 参数"""
    body_str = json.dumps(body, separators=(",", ":"))
    sign, t = generate_sign(
        function_id=function_id,
        body=body_str,
        uuid=uuid,
        appid=APPID,
        client=CLIENT,
        client_version=CLIENT_VERSION,
    )
    params = {
        "functionId": function_id,
        "appid": APPID,
        "client": CLIENT,
        "clientVersion": CLIENT_VERSION,
        "t": t,
        "uuid": uuid,
        "sign": sign,
        "body": body_str,
    }
    return params, t, sign


def collect_one(http_client, target: dict, fp_gen, anti: AntiDetect, results: list):
    """采集单个接口"""
    name = target["name"]
    fid = target["functionId"]
    body = target["body"]
    uuid = fp_gen.get_or_create_uuid()

    print(f"\n{'─' * 60}")
    print(f"  [{fid}] {name}")
    print(f"{'─' * 60}")

    params, t, sign = build_full_url(fid, body, uuid)
    print(f"  uuid:      {uuid}")
    print(f"  timestamp: {t}")
    print(f"  sign:      {sign}")
    print(f"  body:      {json.dumps(body)}")

    # 构建反检测请求头
    headers = anti.build_stealth_headers()

    t0 = time.time()
    try:
        if target["method"].upper() == "GET":
            resp = http_client.get(JD_API, params=params, headers=headers, timeout=15.0)
        else:
            resp = http_client.post(JD_API, data=params, headers=headers, timeout=15.0)

        elapsed = time.time() - t0
        status_code = resp.status_code
        content_type = resp.headers.get("content-type", "")
        text = resp.text

        print(f"\n  [响应] 状态码={status_code}  耗时={elapsed:.2f}s  CT={content_type}")
        print(f"  [响应头关键字段]")
        for h in ["server", "x-request-id", "set-cookie", "content-length"]:
            v = resp.headers.get(h)
            if v:
                print(f"    {h}: {v[:80]}")

        # 尝试解析 JSON
        try:
            data = resp.json()
            # 京东常见返回字段
            code = data.get("code", data.get("resultCode", "?"))
            msg = data.get("message", data.get("resultMsg", ""))
            print(f"\n  [业务] code={code}  message={msg}")

            # 打印完整 JSON（截断）
            pretty = json.dumps(data, ensure_ascii=False, indent=2)
            if len(pretty) > 2000:
                print(f"  [JSON 前 2000 字符]")
                print(f"  {pretty[:2000]}...")
            else:
                print(f"  [完整 JSON]")
                for line in pretty.splitlines():
                    print(f"  {line}")

            result = {
                "functionId": fid,
                "name": name,
                "status_code": status_code,
                "elapsed": round(elapsed, 2),
                "code": code,
                "message": msg,
                "has_data": bool(data.get("data") or data.get("result")),
                "raw_keys": list(data.keys()) if isinstance(data, dict) else [],
            }

        except json.JSONDecodeError:
            print(f"  [非 JSON 响应 前 500 字符]")
            print(f"  {text[:500]}")
            result = {
                "functionId": fid,
                "name": name,
                "status_code": status_code,
                "elapsed": round(elapsed, 2),
                "code": "parse_error",
                "raw_snippet": text[:200],
            }

        results.append(result)

    except Exception as e:
        elapsed = time.time() - t0
        print(f"\n  [异常] {type(e).__name__}: {e}")
        traceback.print_exc()
        results.append({
            "functionId": fid,
            "name": name,
            "status_code": 0,
            "elapsed": round(elapsed, 2),
            "error": str(e),
        })


def main():
    print("=" * 60)
    print("  京东工业招商网 - 实际数据采集")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 初始化组件
    fp_gen = FingerprintGenerator(platform="mobile")
    anti = AntiDetect(random_delay_range=(0.5, 1.5))  # 缩短延迟用于测试
    cookie_mgr = CookieManager(auto_save=False)

    # 初始化基础 Cookie（模拟首次访问）
    uuid = fp_gen.get_or_create_uuid()
    cookie_mgr.set_cookies({
        "jd-uuid": uuid,
        "__jda": f"12222222.{uuid}.1700000000.1700000000.1700000000.1",
    })

    print(f"\n[初始化]")
    print(f"  UUID: {uuid}")
    print(f"  TLS 后端: httpx (curl_cffi 未安装)")
    print(f"  签名模式: 本地 sign（无 h5st）")
    print(f"  采集接口: {len(TARGETS)} 个")

    # 使用 httpx 直接请求
    import httpx

    with httpx.Client(
        timeout=15.0,
        follow_redirects=True,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
        },
    ) as client:
        results = []
        for i, target in enumerate(TARGETS):
            collect_one(client, target, fp_gen, anti, results)
            # 请求间延迟（模拟人类操作）
            if i < len(TARGETS) - 1:
                delay = anti.random_delay()
                print(f"\n  ... 等待 {delay:.1f}s ...")

    # ── 汇总 ──────────────────────────────────────────────────────
    print("\n\n" + "=" * 60)
    print("  采集结果汇总")
    print("=" * 60)
    print(f"  {'接口':<35} {'状态码':>6} {'耗时':>6} {'业务码':<15} {'有数据':<6}")
    print(f"  {'-' * 70}")
    for r in results:
        has_data = "✓" if r.get("has_data") else "✗"
        code = str(r.get("code", r.get("error", "?")))
        print(f"  {r['name']:<35} {r['status_code']:>6} {r['elapsed']:>5.1f}s {code:<15} {has_data:<6}")

    # 保存原始结果
    output_path = PROJECT_ROOT / "data" / f"collect_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "mode": "local_sign_no_h5st",
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  原始结果已保存: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
