#!/usr/bin/env python3
"""真实 API 采集 v2 - 修复 client 生命周期问题"""
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

all_results = []

def safe_get(client, url, **kwargs):
    try:
        return client.get(url, **kwargs)
    except Exception as e:
        print(f"    ERROR: {e}")
        return None

print("=" * 70)
print(f"  真实 API 采集 v2 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  UUID: {uuid}")
print("=" * 70)

client = httpx.Client(timeout=10.0, headers={"User-Agent": UA}, follow_redirects=True)

# ── 阶段 1: mtop 风格 API ──────────────────────────────────────────
print("\n[阶段 1] mtop 风格 API 调用 api.m.jd.com")
MTOP_FIDS = [
    ("dsm.base.service.ducc.query", {"bizType": "zhaoshang"}),
    ("pop.vender.cooperation", {"pageNo": 1, "pageSize": 10}),
]

for fid, body in MTOP_FIDS:
    body_str = json.dumps(body, separators=(",", ":"))
    sign, t = generate_sign(function_id=fid, body=body_str, uuid=uuid)
    params = {
        "functionId": fid, "appid": "ebf5a3c8", "client": "h5",
        "clientVersion": "1.0.0", "t": t, "uuid": uuid, "sign": sign, "body": body_str,
    }
    headers = anti.build_stealth_headers()
    r = safe_get(client, "https://api.m.jd.com/", params=params, headers=headers)
    if r:
        try:
            data = r.json()
            code = data.get("code", "?")
            echo = data.get("echo", data.get("message", ""))
            has_data = bool(data.get("data") or data.get("result"))
            print(f"  {fid}: code={code} echo={str(echo)[:60]} data={has_data}")
            if has_data:
                print(f"    {json.dumps(data, ensure_ascii=False)[:400]}")
            all_results.append({"fid": fid, "code": str(code), "echo": str(echo)[:80], "has_data": has_data, "raw": json.dumps(data, ensure_ascii=False)[:500]})
        except:
            print(f"  {fid}: non-JSON {r.text[:200]}")
    time.sleep(0.3)

# ── 阶段 2: category-h5 子应用 ─────────────────────────────────────
print("\n[阶段 2] category-h5 子应用")
r = safe_get(client, "https://zhaoshang.jd.com/category-h5/")
if r:
    print(f"  status={r.status_code}, size={len(r.text)}")
    # 提取 JS URL
    js_urls = re.findall(r'(https?:[^\s"<>]+\.js|//[^\s"<>]+\.js)', r.text)
    print(f"  JS chunks: {len(js_urls)}")
    # 下载第一个非 CDN JS 搜索 API
    for js_url in js_urls[:5]:
        full = js_url if js_url.startswith("http") else "https:" + js_url
        try:
            js_r = client.get(full, timeout=10)
            js_text = js_r.text
            # 搜索 API 调用
            for kw in ["functionId", "api.m.jd", "fetch(", "axios", "/api/", "/rest/", "baseURL"]:
                if kw in js_text:
                    idx = js_text.index(kw)
                    ctx = js_text[max(0,idx-40):idx+80]
                    print(f"  [{full.split('/')[-1][:30]}] '{kw}': ...{ctx}...")
        except:
            pass

# ── 阶段 3: SFF 网关 ──────────────────────────────────────────────
print("\n[阶段 3] SFF (Shop Front Framework) 网关")
for url in ["https://sff.jd.com/", "https://sff.jd.com/api/", "https://sff.jd.com/api/navigation", "https://sff.jd.com/api/category/list"]:
    r = safe_get(client, url)
    if r:
        ct = r.headers.get("content-type", "")
        title = re.search(r'<title>(.*?)</title>', r.text)
        title_text = title.group(1) if title else "(无)"
        print(f"  {url} -> {r.status_code} ({len(r.text)}b) {title_text}")
        if "json" in ct:
            print(f"    {r.text[:300]}")

# ── 阶段 4: newapply.jd.com ────────────────────────────────────────
print("\n[阶段 4] newapply.jd.com API")
for url in [
    "https://newapply.jd.com/site/pop/create-apply",
    "https://newapply.jd.com/api/pop/category/list",
    "https://newapply.jd.com/api/common/navigation",
]:
    r = safe_get(client, url, headers={"Accept": "application/json, text/html"})
    if r:
        ct = r.headers.get("content-type", "")
        print(f"  {url} -> {r.status_code} ({len(r.text)}b) {ct[:30]}")
        if "json" in ct:
            try:
                data = r.json()
                print(f"    {json.dumps(data, ensure_ascii=False)[:300]}")
            except:
                pass
        elif "html" in ct:
            title = re.search(r'<title>(.*?)</title>', r.text)
            print(f"    title: {title.group(1) if title else '(无)'}")

# ── 阶段 5: 京东工业品 gong.jd.com 深层分析 ────────────────────────
print("\n[阶段 5] 京东工业品 gong.jd.com 深层分析")
r = safe_get(client, "https://gong.jd.com")
if r:
    print(f"  status={r.status_code}, size={len(r.text)}")
    title = re.search(r'<title>(.*?)</title>', r.text)
    print(f"  title: {title.group(1) if title else '(无)'}")
    # 提取所有链接
    links = set(re.findall(r'href=["\']([^"\']+)["\']', r.text))
    api_links = [l for l in links if "api" in l.lower() or "rest" in l.lower()]
    print(f"  API 相关链接: {api_links[:10]}")
    # 提取所有 JS
    js_urls = re.findall(r'(https?:[^\s"<>]+\.js|//[^\s"<>]+\.js)', r.text)
    print(f"  JS: {len(js_urls)} 个")
    # 下载并搜索
    for js_url in js_urls[:3]:
        full = js_url if js_url.startswith("http") else "https:" + js_url
        try:
            js_r = client.get(full, timeout=10)
            js_text = js_r.text
            for kw in ["functionId", "api.m.jd", "/api/", "/rest/", "baseURL", "axios", "fetch("]:
                if kw in js_text:
                    idx = js_text.index(kw)
                    ctx = js_text[max(0,idx-40):idx+80]
                    print(f"  [{full.split('/')[-1][:30]}] '{kw}': ...{ctx}...")
        except:
            pass

# ── 阶段 6: 用京东通用搜索接口测试 ─────────────────────────────────
print("\n[阶段 6] 京东通用搜索接口")
COMMON_FIDS = [
    ("searchAutoComplete", {"keyword": "轴承"}),
    ("getSearchResult", {"keyword": "工业", "page": "1", "pagesize": "5", "area": "1_72_0_0"}),
    ("queryMaterialProducts", {"keyword": "轴承"}),
    ("getShelfGoodsList", {"page": "1", "pagesize": "5"}),
    ("getRecommend", {"platform": "2", "page": "1"}),
]

for fid, body in COMMON_FIDS:
    body_str = json.dumps(body, separators=(",", ":"))
    sign, t = generate_sign(function_id=fid, body=body_str, uuid=uuid)
    params = {
        "functionId": fid, "appid": "ebf5a3c8", "client": "h5",
        "clientVersion": "1.0.0", "t": t, "uuid": uuid, "sign": sign, "body": body_str,
    }
    headers = anti.build_stealth_headers()
    r = safe_get(client, "https://api.m.jd.com/", params=params, headers=headers)
    if r:
        try:
            data = r.json()
            code = data.get("code", "?")
            echo = data.get("echo", data.get("message", ""))
            has_data = bool(data.get("data") or data.get("result") or data.get("items"))
            print(f"  {fid}: code={code} echo={str(echo)[:50]} data={has_data}")
            if has_data:
                print(f"    {json.dumps(data, ensure_ascii=False)[:400]}")
                all_results.append({"fid": fid, "code": str(code), "has_data": True, "raw": json.dumps(data, ensure_ascii=False)[:500]})
        except:
            print(f"  {fid}: non-JSON")
    time.sleep(0.3)

client.close()

# ── 汇总 ────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("  采集汇总")
print("=" * 70)
found = [r for r in all_results if r.get("has_data")]
print(f"  有数据的接口: {len(found)} 个")
for r in found:
    print(f"    {r['fid']}: {r.get('raw','')[:200]}")

output = Path(__file__).parent / "data" / f"real_api_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(output, "w", encoding="utf-8") as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)
print(f"\n  结果: {output}")
print("=" * 70)
