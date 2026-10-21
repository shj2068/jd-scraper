#!/usr/bin/env python3
"""
基于深度分析发现的真实 API 进行采集
发现:
  - mtop 风格 API: dsm.base.service.ducc.query, pop.vender.cooperation
  - 可用域名: api-industrial.jd.com, sell-api.jd.com, zhaoshang-api.jd.com 等
  - 微前端路由: category-h5/, HomeIndex, Qualificate 等
"""
import httpx, json, sys, time, re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from python.sign import generate_sign
from python.fingerprint import FingerprintGenerator
from python.anti_detect import AntiDetect

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
anti = AntiDetect(random_delay_range=(0.3, 0.8))
fp = FingerprintGenerator(platform="desktop")
uuid = fp.get_or_create_uuid()

results = []

print("=" * 70)
print("  真实 API 采集")
print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  UUID: {uuid}")
print("=" * 70)

# ── 阶段 1: 检查可用域名实际内容 ──────────────────────────────────
print("\n[阶段 1] 检查已发现域名的实际内容")
DISCOVERED_DOMAINS = [
    "https://api-industrial.jd.com/",
    "https://sell-api.jd.com/",
    "https://zhaoshang-api.jd.com/",
    "https://gong-api.jd.com/",
    "https://industry-api.jd.com/",
]

with httpx.Client(timeout=8.0, headers={"User-Agent": UA}, follow_redirects=True) as client:
    for domain in DISCOVERED_DOMAINS:
        try:
            r = client.get(domain)
            # 提取 title 和关键内容
            title = re.search(r'<title>(.*?)</title>', r.text)
            title_text = title.group(1) if title else "(无)"
            # 搜索 JS 中的 API 端点
            apis = set(re.findall(r'["\']((?:https?:)?//[^\s"\']{5,})["\']', r.text[:10000]))
            api_list = [a for a in apis if "api" in a.lower() or "gateway" in a.lower()]
            print(f"  {domain}")
            print(f"    status={r.status_code}, size={len(r.text)}, title={title_text}")
            if api_list:
                print(f"    API URLs: {api_list[:5]}")
            results.append({"domain": domain, "status": r.status_code, "title": title_text, "apis": api_list[:5]})
        except Exception as e:
            print(f"  {domain} -> {e}")

# ── 阶段 2: 用 mtop 风格调用 api.m.jd.com ──────────────────────────
print("\n[阶段 2] 用 mtop 风格 API 调用 api.m.jd.com")

MTOP_FIDS = [
    ("dsm.base.service.ducc.query", {"bizType": "zhaoshang"}),
    ("pop.vender.cooperation", {"pageNo": 1, "pageSize": 10}),
    ("dsm.base.service.ducc.query", {}),
    ("pop.vender.cooperation", {}),
]

for fid, body in MTOP_FIDS:
    body_str = json.dumps(body, separators=(",", ":"))
    sign, t = generate_sign(function_id=fid, body=body_str, uuid=uuid)
    params = {
        "functionId": fid,
        "appid": "ebf5a3c8",
        "client": "h5",
        "clientVersion": "1.0.0",
        "t": t,
        "uuid": uuid,
        "sign": sign,
        "body": body_str,
    }
    headers = anti.build_stealth_headers()
    try:
        r = client.get("https://api.m.jd.com/", params=params, headers=headers, timeout=10)
        data = r.json()
        code = data.get("code", "?")
        echo = data.get("echo", data.get("message", ""))
        has_data = bool(data.get("data") or data.get("result"))
        print(f"  {fid}: code={code} echo={str(echo)[:60]} has_data={has_data}")
        if has_data:
            print(f"    data: {json.dumps(data, ensure_ascii=False)[:300]}")
        results.append({"fid": fid, "body": body, "code": str(code), "echo": str(echo)[:80], "has_data": has_data})
    except Exception as e:
        print(f"  {fid}: ERROR {e}")
    time.sleep(0.3)

# ── 阶段 3: 访问 category-h5 子页面（可能有独立 API）────────────────
print("\n[阶段 3] 访问 category-h5 子应用")
category_urls = [
    "https://zhaoshang.jd.com/category-h5/",
    "https://zhaoshang.jd.com/category-h5/#/meeting?id=",
]

for url in category_urls:
    try:
        r = client.get(url, headers={"User-Agent": UA}, timeout=10)
        title = re.search(r'<title>(.*?)</title>', r.text)
        title_text = title.group(1) if title else "(无)"
        # 提取 JS 中的 API
        js_urls = set(re.findall(r'(https?:[^\s"<>]+\.js|//[^\s"<>]+\.js)', r.text))
        print(f"  {url}")
        print(f"    status={r.status_code}, size={len(r.text)}, title={title_text}")
        print(f"    JS chunks: {len(js_urls)}")
        if js_urls:
            for j in sorted(js_urls)[:3]:
                print(f"      {j[:100]}")
    except Exception as e:
        print(f"  {url}: {e}")

# ── 阶段 4: 尝试 SFF (Shop Front Framework) API ────────────────────
print("\n[阶段 4] 探测 SFF 网关")
SFF_URLS = [
    "https://sff.jd.com/",
    "https://sff.jd.com/api/",
    "https://sff.jd.com/gateway/",
    "https://sff.jd.com/api/navigation",
    "https://sff.jd.com/api/category/list",
]

for url in SFF_URLS:
    try:
        r = client.get(url, headers={"User-Agent": UA}, timeout=8)
        ct = r.headers.get("content-type", "")
        print(f"  {url} -> {r.status_code} ({len(r.text)} bytes) {ct[:30]}")
        if "json" in ct:
            try:
                data = r.json()
                print(f"    JSON: {json.dumps(data, ensure_ascii=False)[:200]}")
            except:
                pass
    except Exception as e:
        print(f"  {url} -> {str(e)[:60]}")

# ── 阶段 5: 尝试 newapply.jd.com API ───────────────────────────────
print("\n[阶段 5] 探测 newapply.jd.com API")
NEWAPPLY_URLS = [
    "https://newapply.jd.com/site/pop/create-apply",
    "https://newapply.jd.com/api/pop/category/list",
    "https://newapply.jd.com/api/common/navigation",
    "https://newapply.jd.com/api/pop/qualification/list",
]

for url in NEWAPPLY_URLS:
    try:
        r = client.get(url, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=8)
        ct = r.headers.get("content-type", "")
        print(f"  {url} -> {r.status_code} ({len(r.text)} bytes) {ct[:30]}")
        if "json" in ct:
            try:
                data = r.json()
                print(f"    JSON: {json.dumps(data, ensure_ascii=False)[:300]}")
            except:
                pass
    except Exception as e:
        print(f"  {url} -> {str(e)[:60]}")

# ── 保存结果 ────────────────────────────────────────────────────────
output = Path(__file__).parent / "data" / f"real_api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
output.parent.mkdir(parents=True, exist_ok=True)
with open(output, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f"\n结果已保存: {output}")
print("=" * 70)
