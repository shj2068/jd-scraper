#!/usr/bin/env python3
"""从招商网 JS 资源中提取真实 API 端点"""
import httpx, re, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

resp = httpx.get(
    "https://zhaoshang.jd.com/",
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/118.0.0.0 Safari/537.36"},
    follow_redirects=True, timeout=10,
)
html = resp.text

# 提取 JS URL
js_urls = re.findall(r'(https?:[^\s"<>]+\.js|//[^\s"<>]+\.js)', html)
print(f"找到 {len(js_urls)} 个 JS 链接")
for u in js_urls[:3]:
    print(f"  {u[:120]}")

# 下载主 JS chunk 搜索 functionId / api 关键词
# 选取第一个主 JS（通常是 app 入口）
main_js_urls = [u for u in js_urls if "app" in u or "chunk-libs" in u or "runtime" in u]
if not main_js_urls and js_urls:
    main_js_urls = js_urls[:3]

print(f"\n关键 JS: {len(main_js_urls)} 个")

all_api_patterns = set()

for js_url in main_js_urls[:5]:
    full_url = js_url if js_url.startswith("http") else "https:" + js_url
    print(f"\n下载: {full_url[:100]}...")
    try:
        js_resp = httpx.get(full_url, timeout=15)
        js_content = js_resp.text
        print(f"  大小: {len(js_content)} bytes")

        # 搜索 functionId 相关
        patterns = [
            r'functionId["\s:=]+["\'](\w+)["\']',
            r'["\']functionId["\']\s*:\s*["\'](\w+)["\']',
            r'api\.m\.jd\.com[^\s"\']*',
            r'["\'](/api/\w+)',
            r'["\'](https?://[^\s"\']*api[^\s"\']*)',
            r'baseURL\s*[:=]\s*["\']([^"\']+)',
            r'["\'](\w+List|\w+Query|\w+Search|\w+Detail)["\']',
        ]

        for pat in patterns:
            matches = re.findall(pat, js_content)
            for m in matches:
                all_api_patterns.add(m)
                if len(all_api_patterns) < 30:
                    print(f"  匹配: {m[:80]}")

    except Exception as e:
        print(f"  失败: {e}")

print(f"\n\n=== 所有发现的 API 模式 ({len(all_api_patterns)} 个) ===")
for p in sorted(all_api_patterns):
    print(f"  {p[:120]}")
