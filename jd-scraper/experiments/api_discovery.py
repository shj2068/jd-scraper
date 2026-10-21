#!/usr/bin/env python3
"""尝试京东已知公开 JSONP/JSON 接口 + 分析 allSort.aspx 真实内容"""
import httpx, re, json, sys, time
from pathlib import Path
from datetime import datetime

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
HEADERS = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.jd.com/",
}

results = {"categories": [], "products": [], "prices": [], "api_tests": []}

print("=" * 70)
print(f"  京东公开接口采集 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

client = httpx.Client(timeout=15.0, headers=HEADERS, follow_redirects=True)

# ── 阶段 1: 分析 allSort.aspx 实际内容 ─────────────────────────────
print("\n[阶段 1] 分析 allSort.aspx 真实 HTML 结构")
r = client.get("https://www.jd.com/allSort.aspx")
html = r.text
print(f"  大小: {len(html)} bytes")

# 保存前 5000 字符供分析
sample_path = Path(__file__).parent / "data" / "allsort_sample.html"
with open(sample_path, "w", encoding="utf-8") as f:
    f.write(html[:10000])
print(f"  前 10KB 已保存: {sample_path}")

# 分析 HTML 结构
# 搜索所有 <a> 标签
all_links = re.findall(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.DOTALL)
print(f"  总链接数: {len(all_links)}")

# 搜索 list.jd.com 链接
list_links = re.findall(r'href=["\']([^"\']*list\.jd\.com[^"\']*)["\']', html)
print(f"  list.jd.com 链接: {len(list_links)}")
for l in list_links[:10]:
    print(f"    {l}")

# 搜索 channel 或分类相关
channel_links = re.findall(r'href=["\']([^"\']+)["\']', html)
jd_links = [l for l in channel_links if 'jd.com' in l or l.startswith('/')]
print(f"  京东域名链接: {len(jd_links)}")

# 搜索 JSON 数据块
json_blocks = re.findall(r'(?:var|let|const)\s+\w+\s*=\s*(\{[^;]{100,}?\});', html, re.DOTALL)
print(f"  JSON 数据块: {len(json_blocks)}")
for i, block in enumerate(json_blocks[:3]):
    print(f"    块 {i}: {len(block)} chars, 前100: {block[:100]}")

# 搜索 script 中的分类数据
script_blocks = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
print(f"  script 块: {len(script_blocks)}")
for i, s in enumerate(script_blocks):
    if len(s) > 100 and ("cat" in s.lower() or "category" in s.lower() or "sort" in s.lower()):
        print(f"    script[{i}]: {len(s)} chars, 含分类关键词")
        print(f"      前200: {s[:200]}")

# ── 阶段 2: 京东已知公开价格接口 ──────────────────────────────────
print("\n[阶段 2] 京东公开价格/评论接口")

# 测试一些已知的工业品 SKU
TEST_SKUS = [
    "100012043978", "100009375439", "100038014896",
    "100008397656", "100007141298", "100003818452",
    "7275636", "5089553", "100015653920",
]

# 价格接口
print("  [价格接口] p.3.cn")
for sku in TEST_SKUS[:5]:
    try:
        r = client.get(f"https://p.3.cn/prices/mgets", params={"skuIds": f"J_{sku}"})
        print(f"    SKU {sku}: status={r.status_code}, size={len(r.text)}")
        if r.status_code == 200 and len(r.text) > 5:
            print(f"      {r.text[:200]}")
            try:
                data = r.json()
                results["prices"].append({"sku": sku, "data": data})
            except:
                results["prices"].append({"sku": sku, "raw": r.text[:200]})
    except Exception as e:
        print(f"    SKU {sku}: ERROR {e}")
    time.sleep(0.2)

# 评论接口
print("\n  [评论接口] club.jd.com")
for sku in TEST_SKUS[:3]:
    try:
        r = client.get(f"https://club.jd.com/comment/productCommentSummaries.action",
                       params={"referenceIds": sku})
        print(f"    SKU {sku}: status={r.status_code}, size={len(r.text)}")
        if r.status_code == 200 and len(r.text) > 10:
            print(f"      {r.text[:200]}")
    except Exception as e:
        print(f"    SKU {sku}: ERROR {e}")
    time.sleep(0.2)

# ── 阶段 3: 京东商品基础信息接口 ──────────────────────────────────
print("\n[阶段 3] 商品基础信息接口")

# 尝试已知的商品详情接口
WAREHOUSE_APIS = [
    f"https://cd.jd.com/ware/detail?skuId={TEST_SKUS[0]}",
    f"https://ware-detail.jd.com/detail/{TEST_SKUS[0]}",
    f"https://item-soa.jd.com/getWareBusiness?skuId={TEST_SKUS[0]}",
]

for url in WAREHOUSE_APIS:
    try:
        r = client.get(url)
        print(f"  {url.split('?')[0].split('/')[-1]}: status={r.status_code}, size={len(r.text)}")
        if len(r.text) > 10 and r.status_code == 200:
            print(f"    {r.text[:200]}")
    except Exception as e:
        print(f"  ERROR: {e}")
    time.sleep(0.2)

# ── 阶段 4: 京东分类 API (已知可用) ──────────────────────────────
print("\n[阶段 4] 京东分类数据接口")

# 尝试已知的分类接口
CATEGORY_APIS = [
    "https://dc.3.cn/category/get?callback=",
    "https://dc.3.cn/category/getContent",
    "https://api.m.jd.com/api?functionId=bizGetCategoryList&appid=wh5",
]

for url in CATEGORY_APIS:
    try:
        r = client.get(url)
        print(f"  {url[:60]}: status={r.status_code}, size={len(r.text)}")
        if r.status_code == 200 and len(r.text) > 10:
            print(f"    {r.text[:300]}")
            try:
                data = r.json()
                results["categories"].append({"url": url[:60], "data": json.dumps(data, ensure_ascii=False)[:500]})
            except:
                results["categories"].append({"url": url[:60], "raw": r.text[:300]})
    except Exception as e:
        print(f"  ERROR: {e}")
    time.sleep(0.2)

# ── 阶段 5: 京东搜索建议接口 ──────────────────────────────────────
print("\n[阶段 5] 搜索建议/联想接口")
suggest_urls = [
    "https://dd.search.jd.com/search?keyword=轴承&enc=utf-8",
    "https://search.jd.com/search?keyword=轴承&enc=utf-8&wq=轴承",
    "https://api.m.jd.com/api?functionId=searchAutoComplete&keyword=轴承",
]
for url in suggest_urls:
    try:
        r = client.get(url)
        print(f"  {url[:60]}: status={r.status_code}, size={len(r.text)}")
        if r.status_code == 200 and len(r.text) > 10:
            ct = r.headers.get("content-type", "")
            print(f"    content-type: {ct[:40]}")
            print(f"    body: {r.text[:200]}")
    except Exception as e:
        print(f"  ERROR: {e}")
    time.sleep(0.2)

client.close()

# ── 保存结果 ──────────────────────────────────────────────────────
output = Path(__file__).parent / "data" / f"api_discovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
output.parent.mkdir(parents=True, exist_ok=True)
with open(output, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n" + "=" * 70)
print("  采集汇总")
print("=" * 70)
print(f"  分类数据: {len(results['categories'])} 条")
print(f"  价格数据: {len(results['prices'])} 条")
print(f"  商品数据: {len(results['products'])} 条")
print(f"  结果: {output}")
print("=" * 70)
