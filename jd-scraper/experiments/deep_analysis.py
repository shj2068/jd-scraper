#!/usr/bin/env python3
"""
深度分析招商网 app.js 和微前端子应用
寻找真实 API 网关和 functionId
"""
import httpx, re, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"

print("=" * 70)
print("  深度 JS 分析 - 寻找真实 API 网关")
print("=" * 70)

# 1. 下载 app.js（主入口）
print("\n[1] 下载 app.js 主入口...")
app_js_url = "https://storage.360buyimg.com/shop-pageframe/sell-micro-app/zhaoshang/prod/1.0.8-master.3511c97/js/app.2e2b3f07.js"
resp = httpx.get(app_js_url, headers={"User-Agent": UA}, timeout=15)
app_js = resp.text
print(f"  大小: {len(app_js)} bytes")

# 搜索微前端子应用注册
sub_apps = re.findall(r'(?:activeRule|name|entry)\s*[:]\s*["\']([^"\']+)["\']', app_js)
print(f"  微前端配置: {sub_apps[:20]}")

# 搜索 entry / 子应用 URL
entries = re.findall(r'entry\s*[:]\s*["\']([^"\']+)["\']', app_js)
print(f"  子应用 entry: {entries[:10]}")

# 搜索所有 URL
urls_in_app = set(re.findall(r'["\']((?:https?:)?//[^\s"\']{5,})["\']', app_js))
print(f"  所有 URL ({len(urls_in_app)}):")
for u in sorted(urls_in_app):
    print(f"    {u[:120]}")

# 搜索 request / fetch / ajax 调用
req_patterns = re.findall(r'(?:\.get|\.post|\.put|\.delete|fetch|axios|request)\s*\(\s*["\']([^"\']+)["\']', app_js)
print(f"\n  HTTP 调用 ({len(req_patterns)}):")
for r in sorted(set(req_patterns)):
    print(f"    {r[:120]}")

# 2. 下载最大 chunk (142KB) 并分析
print("\n[2] 分析最大 chunk (chunk-132f110b)...")
chunk_url = "https://storage.360buyimg.com/shop-pageframe/sell-micro-app/zhaoshang/prod/1.0.8-master.3511c97/js/chunk-132f110b.3f05309d.js"
resp2 = httpx.get(chunk_url, headers={"User-Agent": UA}, timeout=15)
chunk_js = resp2.text
print(f"  大小: {len(chunk_js)} bytes")

# 搜索 API 相关
api_urls_chunk = set(re.findall(r'["\']((?:https?:)?//[^\s"\']{5,})["\']', chunk_js))
api_related = [u for u in api_urls_chunk if any(k in u.lower() for k in ["api", "gateway", "router", "m.jd", "shop", "sell", "trade"])]
print(f"  API 相关 URL ({len(api_related)}):")
for u in sorted(api_related):
    print(f"    {u[:120]}")

# 搜索 functionId 或 sign
for kw in ["functionId", "h5st", "sign", "appid", "clientVersion", "body=", "api.m.jd"]:
    count = chunk_js.count(kw)
    if count > 0:
        idx = chunk_js.index(kw)
        context = chunk_js[max(0,idx-50):idx+80]
        print(f"  '{kw}' 出现 {count} 次, 上下文: ...{context}...")

# 3. 分析 shop-passport-components（认证组件）
print("\n[3] 分析 passport 组件...")
passport_url = "https://storage.360buyimg.com/shop-pageframe/sell-micro-app/zhaoshang/prod/1.0.8-master.3511c97/js/chunk-36c1de00.37af7c97.js"
resp3 = httpx.get(passport_url, headers={"User-Agent": UA}, timeout=15)
passport_js = resp3.text
print(f"  大小: {len(passport_js)} bytes")

passport_urls = set(re.findall(r'["\']((?:https?:)?//[^\s"\']{5,})["\']', passport_js))
passport_api = [u for u in passport_urls if any(k in u.lower() for k in ["api", "passport", "login", "auth", "token"])]
print(f"  认证相关 URL ({len(passport_api)}):")
for u in sorted(passport_api):
    print(f"    {u[:120]}")

# 4. 尝试工业品专属 API 域名
print("\n[4] 探测工业品专属域名...")
INDUSTRIAL_DOMAINS = [
    "https://api-industrial.jd.com/",
    "https://api.gong.jd.com/",
    "https://sell-api.jd.com/",
    "https://api.sell.jd.com/",
    "https://api.zhaoshang.jd.com/",
    "https://zhaoshang-api.jd.com/",
    "https://gong-api.jd.com/",
    "https://industry-api.jd.com/",
    "https://api.m.gong.jd.com/",
]

with httpx.Client(timeout=5.0, headers={"User-Agent": UA}, follow_redirects=True) as client:
    for domain in INDUSTRIAL_DOMAINS:
        try:
            r = client.get(domain)
            print(f"  ✓ {domain} -> {r.status_code} ({len(r.text)} bytes) {r.headers.get('content-type','')[:30]}")
        except Exception as e:
            err = str(e)[:60]
            print(f"  ✗ {domain} -> {err}")

# 5. 搜索 chunk 中的完整 API 路径模式
print("\n[5] 在所有 chunk 中搜索 API 路径...")
all_chunks_text = app_js + chunk_js + passport_js

# 搜索 /rest/ 路径
rest_paths = set(re.findall(r'["\'](/[a-z]+/[a-z][a-zA-Z0-9/_-]+)["\']', all_chunks_text))
rest_api_paths = [p for p in rest_paths if any(k in p.lower() for k in ["api", "rest", "query", "list", "search", "category", "vendor", "supplier"])]
print(f"  REST API 路径 ({len(rest_api_paths)}):")
for p in sorted(rest_api_paths):
    print(f"    {p}")

# 搜索 mtop 调用
mtop_calls = set(re.findall(r'["\']([a-z]+\.[a-z]+\.[a-z]+[a-z.]*)["\']', all_chunks_text))
mtop_api = [m for m in mtop_calls if len(m) > 10 and "." in m and not m.endswith(".js") and not m.endswith(".com")]
print(f"\n  类 mtop 调用 ({len(mtop_api)}):")
for m in sorted(mtop_api)[:20]:
    print(f"    {m}")
