#!/usr/bin/env python3
"""解析京东真实公开接口数据"""
import httpx, re, json, sys, time
from pathlib import Path
from datetime import datetime

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
HEADERS = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Referer": "https://www.jd.com/",
}

results = {"categories": [], "brands": [], "search_suggestions": [], "products": []}

print("=" * 70)
print(f"  京东真实数据采集 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

client = httpx.Client(timeout=15.0, headers=HEADERS, follow_redirects=True)

# ── 阶段 1: 获取并解析京东完整分类树 ──────────────────────────────
print("\n[阶段 1] 获取京东完整分类树 (dc.3.cn)")
try:
    r = client.get("https://dc.3.cn/category/get")
    print(f"  status={r.status_code}, size={len(r.text)}")
    
    data = r.json()
    
    # 保存原始数据
    raw_path = Path(__file__).parent / "data" / "jd_categories_raw.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  原始数据已保存: {raw_path}")
    
    # 解析分类树
    if "data" in data:
        cat_data = data["data"]
        print(f"  分类数据条数: {len(cat_data)}")
        
        all_categories = []
        all_brands = []
        
        for item in cat_data:
            # 每个 item 包含 p(父分类信息) 和 b(品牌信息)
            p_info = item.get("p", [])
            b_info = item.get("b", [])
            
            # 解析父分类
            for p in p_info:
                parts = p.split("|")
                if len(parts) >= 3:
                    cat_id = parts[0]
                    cat_name = parts[1]
                    cat_url = parts[2] if len(parts) > 2 else ""
                    all_categories.append({
                        "id": cat_id,
                        "name": cat_name,
                        "url": cat_url,
                        "type": "parent"
                    })
            
            # 解析品牌
            for b in b_info:
                parts = b.split("|")
                if len(parts) >= 2:
                    brand_url = parts[0]
                    brand_name = parts[1]
                    all_brands.append({
                        "name": brand_name,
                        "url": brand_url
                    })
        
        print(f"\n  解析到分类: {len(all_categories)} 个")
        print(f"  解析到品牌: {len(all_brands)} 个")
        
        # 输出前 30 个分类
        print("\n  前 30 个分类:")
        for cat in all_categories[:30]:
            print(f"    [{cat['id']}] {cat['name']}")
        
        # 输出前 20 个品牌
        print(f"\n  前 20 个品牌:")
        for brand in all_brands[:20]:
            print(f"    {brand['name']}")
        
        results["categories"] = all_categories
        results["brands"] = all_brands
        
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

time.sleep(0.5)

# ── 阶段 2: 搜索建议接口 (带 appid) ──────────────────────────────
print("\n[阶段 2] 搜索建议接口 (带 appid)")
try:
    r = client.get("https://api.m.jd.com/api", params={
        "functionId": "searchAutoComplete",
        "appid": "wh5",
        "keyword": "轴承",
    })
    print(f"  status={r.status_code}, size={len(r.text)}")
    print(f"  body: {r.text[:300]}")
    try:
        data = r.json()
        results["search_suggestions"].append({"keyword": "轴承", "data": data})
    except:
        pass
except Exception as e:
    print(f"  ERROR: {e}")

# 测试更多关键词
for kw in ["电动机", "润滑油", "传感器", "PLC", "变频器"]:
    try:
        r = client.get("https://api.m.jd.com/api", params={
            "functionId": "searchAutoComplete",
            "appid": "wh5",
            "keyword": kw,
        })
        if r.status_code == 200:
            data = r.json()
            code = data.get("code", "?")
            has_data = bool(data.get("data") or data.get("result") or data.get("suggestions"))
            print(f"  '{kw}': code={code} has_data={has_data}")
            if has_data:
                print(f"    {json.dumps(data, ensure_ascii=False)[:200]}")
                results["search_suggestions"].append({"keyword": kw, "data": data})
    except Exception as e:
        pass
    time.sleep(0.2)

# ── 阶段 3: 获取分类下的子分类和商品 ──────────────────────────────
print("\n[阶段 3] 获取具体分类下的内容")

# 使用发现的真实分类 ID
REAL_CATS = [
    ("737,738", "图书/音像"),
    ("1315,1342", "手机/通讯"),
    ("1620", "电脑/办公"),
    ("6728", "车载"),
    ("12379", "家装"),
    ("37462", "其他"),
]

for cat_id, cat_name in REAL_CATS:
    try:
        # 尝试获取分类下的内容
        r = client.get(f"https://dc.3.cn/category/get", params={"cat": cat_id})
        if r.status_code == 200 and len(r.text) > 100:
            data = r.json()
            print(f"  [{cat_id}] {cat_name}: {len(r.text)} bytes")
            if "data" in data and data["data"]:
                print(f"    子分类: {json.dumps(data['data'], ensure_ascii=False)[:200]}")
    except Exception as e:
        print(f"  [{cat_id}] ERROR: {e}")
    time.sleep(0.2)

# ── 阶段 4: 尝试 list.jd.com 真实分类 ─────────────────────────────
print("\n[阶段 4] 用真实分类 ID 访问 list.jd.com")
for cat_id, cat_name in [("737,738", "图书"), ("1315,1342", "手机"), ("1620", "电脑")]:
    try:
        r = client.get(f"https://list.jd.com/list.html?cat={cat_id}")
        title = re.search(r'<title>(.*?)</title>', r.text)
        title_text = title.group(1)[:60] if title else "(无)"
        print(f"  [{cat_id}] {cat_name}: status={r.status_code}, size={len(r.text)}, title={title_text}")
        
        # 提取 SKU
        skus = re.findall(r'data-sku=["\'](\d+)["\']', r.text)
        # 提取商品标题
        titles = re.findall(r'<a[^>]*title="([^"]{10,})"[^>]*>', r.text)
        print(f"    SKU: {len(skus)}, 标题: {len(titles)}")
        if titles:
            for t in titles[:3]:
                print(f"      - {t[:60]}")
    except Exception as e:
        print(f"  ERROR: {e}")
    time.sleep(0.3)

client.close()

# ── 保存结果 ──────────────────────────────────────────────────────
output = Path(__file__).parent / "data" / f"real_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
output.parent.mkdir(parents=True, exist_ok=True)
with open(output, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n" + "=" * 70)
print("  采集汇总")
print("=" * 70)
print(f"  分类: {len(results['categories'])} 个")
print(f"  品牌: {len(results['brands'])} 个")
print(f"  搜索建议: {len(results['search_suggestions'])} 条")
print(f"  结果: {output}")
print("=" * 70)
