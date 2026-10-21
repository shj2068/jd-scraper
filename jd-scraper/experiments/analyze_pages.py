"""分析京东工业招商页面和分类 API 数据"""
import httpx
import json
import re

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 1. 京东工业招商页面
print("=== 京东工业招商页面 ===")
r = httpx.get("https://zhaoshang.jd.com/", headers=headers, timeout=15, follow_redirects=True)
print(f"URL: {r.url}")
title = re.search(r"<title>(.*?)</title>", r.text, re.DOTALL)
print(f"标题: {title.group(1).strip() if title else 'N/A'}")
# 找 API 端点
apis = re.findall(r'https?://[^\s"\'<>]+api[^\s"\'<>]*', r.text)
print(f"API 端点: {len(apis)}")
for a in list(set(apis))[:10]:
    print(f"  {a[:150]}")
# 找内嵌 JSON 数据
jsons = re.findall(r'window\.__\w+__\s*=\s*(\{.*?\});', r.text, re.DOTALL)
print(f"内嵌 JSON: {len(jsons)}")
for j in jsons[:3]:
    print(f"  {j[:200]}")
# 找商品链接
items = re.findall(r'//item\.jd\.com/(\d+)\.html', r.text)
print(f"商品链接: {len(items)}")
# 找搜索/列表链接
search_links = re.findall(r'https?://[^\s"\'<>]*(?:search|list|goods)[^\s"\'<>]*', r.text)
print(f"搜索/列表链接: {len(search_links)}")
for s in list(set(search_links))[:5]:
    print(f"  {s[:150]}")

# 2. 京东企业购
print("\n=== 京东企业购 ===")
r2 = httpx.get("https://b.jd.com/", headers=headers, timeout=15, follow_redirects=True)
print(f"URL: {r2.url}")
title2 = re.search(r"<title>(.*?)</title>", r2.text, re.DOTALL)
print(f"标题: {title2.group(1).strip() if title2 else 'N/A'}")
items2 = re.findall(r'//item\.jd\.com/(\d+)\.html', r2.text)
print(f"商品链接: {len(items2)}")

# 3. 分类 API 数据
print("\n=== 分类 API 数据 ===")
r3 = httpx.get("https://dc.3.cn/category/get", headers=headers, timeout=15)
j = json.loads(r3.text)
print(f"顶层键: {list(j.keys())}")
if "data" in j:
    d = j["data"]
    if isinstance(d, list):
        print(f"data 列表: {len(d)} 项")
        for item in d[:3]:
            print(f"  {str(item)[:200]}")
    elif isinstance(d, dict):
        print(f"data 字典键: {list(d.keys())[:10]}")
        for k, v in list(d.items())[:3]:
            print(f"  {k}: {str(v)[:200]}")

# 4. 京东工业品搜索 (gy.jd.com)
print("\n=== 京东工业品搜索 ===")
r4 = httpx.get("https://gy.jd.com/", headers=headers, timeout=15, follow_redirects=True)
print(f"URL: {r4.url}")
title4 = re.search(r"<title>(.*?)</title>", r4.text, re.DOTALL)
print(f"标题: {title4.group(1).strip() if title4 else 'N/A'}")
items4 = re.findall(r'//item\.jd\.com/(\d+)\.html', r4.text)
print(f"商品链接: {len(items4)}")

# 5. 京东五金
print("\n=== 京东五金 ===")
r5 = httpx.get("https://wujin.jd.com/", headers=headers, timeout=15, follow_redirects=True)
print(f"URL: {r5.url}")
title5 = re.search(r"<title>(.*?)</title>", r5.text, re.DOTALL)
print(f"标题: {title5.group(1).strip() if title5 else 'N/A'}")
items5 = re.findall(r'//item\.jd\.com/(\d+)\.html', r5.text)
print(f"商品链接: {len(items5)}")
