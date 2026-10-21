#!/usr/bin/env python3
"""下载招商网全部 JS 并搜索 API 端点"""
import httpx, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

resp = httpx.get(
    "https://zhaoshang.jd.com/",
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/118.0.0.0 Safari/537.36"},
    follow_redirects=True, timeout=10,
)
html = resp.text

# 提取所有 JS URL
js_urls = re.findall(r'(https?:[^\s"<>]+\.js|//[^\s"<>]+\.js)', html)
print(f"共 {len(js_urls)} 个 JS 文件")

all_text = ""
for i, js_url in enumerate(js_urls):
    full_url = js_url if js_url.startswith("http") else "https:" + js_url
    fname = full_url.split("/")[-1]
    try:
        js_resp = httpx.get(full_url, timeout=15)
        content = js_resp.text
        all_text += content
        print(f"  [{i+1}/{len(js_urls)}] {fname}: {len(content)} bytes")
    except Exception as e:
        print(f"  [{i+1}/{len(js_urls)}] {fname}: FAILED {e}")

print(f"\n合并 JS 总大小: {len(all_text)} bytes ({len(all_text)//1024} KB)")

# 广泛搜索
print("\n=== 搜索 API 端点 ===")

# 1. functionId
fids = set(re.findall(r'functionId[=:]["\']?(\w+)', all_text))
print(f"\nfunctionId ({len(fids)}):")
for f in sorted(fids):
    print(f"  {f}")

# 2. api.m.jd.com 或类似域名
apis = set(re.findall(r'https?://[a-z0-9.-]*jd\.com[^\s"\')]*', all_text))
print(f"\nJD API URLs ({len(apis)}):")
for a in sorted(apis)[:30]:
    print(f"  {a[:120]}")

# 3. baseURL / apiUrl
base_urls = set(re.findall(r'baseURL[=:]["\']([^"\']+)', all_text))
print(f"\nbaseURL ({len(base_urls)}):")
for b in sorted(base_urls):
    print(f"  {b}")

# 4. /api/ 路径
api_paths = set(re.findall(r'["\'](/[a-z][a-z0-9]+/[a-z][a-zA-Z0-9]+)', all_text))
print(f"\n/api/ paths ({len(api_paths)}):")
for p in sorted(api_paths)[:30]:
    print(f"  {p}")

# 5. 搜索 mtop / m / router 等关键词
mtop = set(re.findall(r'["\']((?:mtop|router|gateway)[^"\']*)', all_text))
print(f"\nmtop/router ({len(mtop)}):")
for m in sorted(mtop)[:20]:
    print(f"  {m[:100]}")

# 6. 搜索 fetch / axios / request 调用
reqs = set(re.findall(r'(?:fetch|axios|request)\s*\(\s*["\']([^"\']+)', all_text))
print(f"\nfetch/axios calls ({len(reqs)}):")
for r in sorted(reqs)[:20]:
    print(f"  {r[:100]}")

# 7. 搜索所有 URL 模式
url_patterns = set(re.findall(r'["\']((?:https?:)?//[^\s"\']+)["\']', all_text))
api_urls = [u for u in url_patterns if "api" in u.lower() or "gateway" in u.lower() or "router" in u.lower()]
print(f"\n含 api/gateway 的 URL ({len(api_urls)}):")
for u in sorted(api_urls)[:30]:
    print(f"  {u[:120]}")
