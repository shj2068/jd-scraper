#!/usr/bin/env python3
"""
基于真实 REST API 端点的数据采集
从 JS 分析发现的真实端点:
  - /rest/navigation
  - /register/v1
  - /api/dsm
  - passport.jd.com (认证)
  - newapply.jd.com (入驻申请)
  - morder.shop.jd.com/api/dsm
"""
import httpx, json, sys, time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from python.anti_detect import AntiDetect
from python.fingerprint import FingerprintGenerator

anti = AntiDetect(random_delay_range=(0.5, 1.5))
fp = FingerprintGenerator(platform="desktop")
headers = anti.build_stealth_headers()
headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"

# 真实发现的 REST 端点
REST_TARGETS = [
    ("招商网首页", "https://zhaoshang.jd.com/"),
    ("导航 REST API", "https://zhaoshang.jd.com/rest/navigation"),
    ("注册入口", "https://zhaoshang.jd.com/register/v1"),
    ("登录组件", "https://zhaoshang.jd.com/login/component"),
    ("服务页", "https://zhaoshang.jd.com/service/mobile"),
    ("入驻申请", "https://newapply.jd.com/"),
    ("入驻申请-POP", "https://newapply.jd.com/site/pop/create-apply"),
    ("企业注册", "https://zhaoshang.jd.com/register/enterprise"),
    ("商家帮助", "https://helpcenter.jd.com/vender/issue/42981.html"),
    ("京东工业品", "https://gong.jd.com"),
    ("商家数据", "https://morder.shop.jd.com/api/dsm"),
]

results = []

print("=" * 70)
print("  京东招商网 REST API 探测")
print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

with httpx.Client(
    timeout=10.0,
    follow_redirects=True,
    headers=headers,
) as client:
    for name, url in REST_TARGETS:
        print(f"\n{'─' * 60}")
        print(f"  {name}: {url}")
        try:
            t0 = time.time()
            resp = client.get(url)
            elapsed = time.time() - t0

            ct = resp.headers.get("content-type", "")
            final_url = str(resp.url)
            redirected = final_url != url

            print(f"  状态码: {resp.status_code}  耗时: {elapsed:.2f}s  CT: {ct[:50]}")
            if redirected:
                print(f"  重定向: {final_url[:100]}")

            # 内容预览
            if "json" in ct or "javascript" in ct:
                try:
                    data = resp.json()
                    pretty = json.dumps(data, ensure_ascii=False, indent=2)
                    print(f"  JSON ({len(pretty)} chars):")
                    print(f"  {pretty[:500]}")
                    results.append({"name": name, "url": url, "status": resp.status_code, "type": "json", "data": data})
                except:
                    print(f"  文本前 300 字符: {resp.text[:300]}")
                    results.append({"name": name, "url": url, "status": resp.status_code, "type": "text"})
            elif "html" in ct:
                # 提取 title
                import re
                title = re.search(r'<title>(.*?)</title>', resp.text)
                title_text = title.group(1) if title else "(无标题)"
                print(f"  HTML: {len(resp.text)} bytes, title={title_text}")
                # 提取内联 API 调用
                api_calls = re.findall(r'(?:url|api|endpoint|fetch)\s*[:=]\s*["\']([^"\']+)["\']', resp.text[:5000])
                if api_calls:
                    print(f"  内联 API: {api_calls[:5]}")
                results.append({"name": name, "url": url, "status": resp.status_code, "type": "html", "title": title_text})
            else:
                print(f"  内容前 200 字符: {resp.text[:200]}")
                results.append({"name": name, "url": url, "status": resp.status_code, "type": "other"})

        except Exception as e:
            print(f"  错误: {e}")
            results.append({"name": name, "url": url, "status": 0, "error": str(e)})

        time.sleep(0.5)

# 汇总
print("\n\n" + "=" * 70)
print("  汇总")
print("=" * 70)
for r in results:
    status = r.get("status", 0)
    icon = "✓" if 200 <= status < 400 else "✗"
    extra = r.get("title", r.get("type", ""))
    print(f"  {icon} {r['name']:<20} {status}  {extra}")

# 保存
output = Path(__file__).parent / "data" / f"rest_probe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
output.parent.mkdir(parents=True, exist_ok=True)
with open(output, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f"\n  结果已保存: {output}")
