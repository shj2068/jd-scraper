"""分析京东各子站页面 - 短超时版本"""
import httpx
import json
import re

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TIMEOUT = 8

def analyze(name, url):
    print(f"\n=== {name} ===")
    try:
        r = httpx.get(url, headers=headers, timeout=TIMEOUT, follow_redirects=True)
        print(f"URL: {r.url}")
        title = re.search(r"<title>(.*?)</title>", r.text, re.DOTALL)
        print(f"标题: {title.group(1).strip()[:100] if title else 'N/A'}")
        items = re.findall(r'//item\.jd\.com/(\d+)\.html', r.text)
        print(f"商品链接: {len(items)}")
        apis = re.findall(r'https?://[^\s"\'<>]+api[^\s"\'<>]*', r.text)
        print(f"API端点: {len(set(apis))}")
        for a in list(set(apis))[:5]:
            print(f"  {a[:120]}")
        jsons = re.findall(r'window\.__\w+__\s*=\s*(\{.*?\});', r.text, re.DOTALL)
        print(f"内嵌JSON: {len(jsons)}")
        for j in jsons[:2]:
            print(f"  {j[:200]}")
        return r.text
    except Exception as e:
        print(f"错误: {e}")
        return None

# 分类 API
print("=== 分类 API ===")
r3 = httpx.get("https://dc.3.cn/category/get", headers=headers, timeout=TIMEOUT)
j = json.loads(r3.text)
print(f"键: {list(j.keys())}")
if "data" in j:
    d = j["data"]
    if isinstance(d, list):
        print(f"列表: {len(d)} 项")
        for item in d[:2]:
            print(f"  {str(item)[:200]}")
    elif isinstance(d, dict):
        print(f"字典键: {list(d.keys())[:10]}")

# 各子站
analyze("京东工业招商", "https://zhaoshang.jd.com/")
analyze("京东企业购", "https://b.jd.com/")
analyze("京东全球购", "https://global.jd.com/")
analyze("京东到家", "https://daojia.jd.com/")
