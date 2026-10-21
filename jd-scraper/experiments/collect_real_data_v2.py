#!/usr/bin/env python3
"""京东真实数据采集 - 修复编码问题"""
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
print(f"  京东真实数据采集 v2 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

client = httpx.Client(timeout=15.0, headers=HEADERS, follow_redirects=True)

# ── 阶段 1: 获取并解析京东完整分类树 ──────────────────────────────
print("\n[阶段 1] 获取京东完整分类树 (dc.3.cn)")
try:
    r = client.get("https://dc.3.cn/category/get")
    print(f"  status={r.status_code}, size={len(r.content)} bytes")
    
    # 检测编码
    content_type = r.headers.get("content-type", "")
    print(f"  content-type: {content_type}")
    
    # 尝试不同编码
    text = None
    for enc in ["gbk", "gb2312", "gb18030", "utf-8"]:
        try:
            text = r.content.decode(enc)
            # 验证是否是有效 JSON
            json.loads(text)
            print(f"  成功解码: {enc}")
            break
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    
    if text is None:
        # 强制用 errors='replace'
        text = r.content.decode("gbk", errors="replace")
        print(f"  强制 GBK 解码 (有替换)")
    
    data = json.loads(text)
    
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
            p_info = item.get("p", [])
            b_info = item.get("b", [])
            
            for p in p_info:
                parts = p.split("|")
                if len(parts) >= 2:
                    cat_id = parts[0]
                    cat_name = parts[1]
                    cat_url = parts[2] if len(parts) > 2 else ""
                    all_categories.append({
                        "id": cat_id,
                        "name": cat_name,
                        "url": cat_url,
                        "type": "parent"
                    })
            
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
        
        # 输出所有分类
        print("\n  所有分类:")
        for cat in all_categories[:50]:
            print(f"    [{cat['id']}] {cat['name']}")
        if len(all_categories) > 50:
            print(f"    ... 共 {len(all_categories)} 个")
        
        # 输出品牌
        print(f"\n  前 30 个品牌:")
        for brand in all_brands[:30]:
            print(f"    {brand['name']}")
        
        results["categories"] = all_categories
        results["brands"] = all_brands
        
        # 统计信息
        print(f"\n  分类统计:")
        print(f"    一级分类数: {len(set(c['id'].split(',')[0] for c in all_categories))}")
        
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

time.sleep(0.5)

# ── 阶段 2: 获取子分类详情 ──────────────────────────────────────
print("\n[阶段 2] 获取子分类详情")

# 从阶段1获取的分类 ID 中选取
cat_ids_to_test = []
if results["categories"]:
    # 取前 10 个不同的分类 ID
    seen = set()
    for cat in results["categories"]:
        cid = cat["id"]
        if cid not in seen and len(cat_ids_to_test) < 10:
            cat_ids_to_test.append(cid)
            seen.add(cid)

for cat_id in cat_ids_to_test[:5]:
    try:
        r = client.get("https://dc.3.cn/category/get", params={"cat": cat_id})
        text = r.content.decode("gbk", errors="replace")
        data = json.loads(text)
        print(f"  cat={cat_id}: {len(r.content)} bytes, {len(data.get('data', []))} items")
        if data.get("data"):
            # 显示子分类
            for item in data["data"][:2]:
                p_info = item.get("p", [])
                for p in p_info[:3]:
                    parts = p.split("|")
                    if len(parts) >= 2:
                        print(f"    [{parts[0]}] {parts[1]}")
    except Exception as e:
        print(f"  cat={cat_id}: ERROR {e}")
    time.sleep(0.2)

# ── 阶段 3: 搜索建议（尝试更多参数组合）─────────────────────────
print("\n[阶段 3] 搜索建议接口测试")

# 尝试不同的参数格式
SEARCH_TESTS = [
    {"functionId": "searchAutoComplete", "appid": "item.jd.com", "keyword": "轴承"},
    {"functionId": "searchAutoComplete", "appid": "search.jd.com", "keyword": "轴承"},
    {"functionId": "searchAutoComplete", "appid": "pc", "keyword": "轴承"},
    {"functionId": "searchAutoComplete", "client": "pc", "keyword": "轴承"},
    {"functionId": "searchAutoComplete", "keyword": "轴承"},
]

for params in SEARCH_TESTS:
    try:
        r = client.get("https://api.m.jd.com/api", params=params)
        data = r.json()
        code = data.get("code", "?")
        echo = data.get("echo", "")
        has_data = bool(data.get("data") or data.get("result") or data.get("suggestions"))
        marker = "✓" if has_data else "✗"
        print(f"  {marker} {params}: code={code} echo={str(echo)[:40]}")
        if has_data:
            print(f"    DATA: {json.dumps(data, ensure_ascii=False)[:200]}")
            results["search_suggestions"].append({"params": params, "data": data})
    except Exception as e:
        print(f"  ERROR: {e}")
    time.sleep(0.15)

# ── 阶段 4: 尝试其他已知公开接口 ──────────────────────────────────
print("\n[阶段 4] 其他公开接口")

OTHER_APIS = [
    ("京东首页推荐", "https://dc.3.cn/recommend/get"),
    ("京东分类内容", "https://dc.3.cn/category/getContent"),
    ("京东品牌墙", "https://brand.jd.com/brandList"),
]

for name, url in OTHER_APIS:
    try:
        r = client.get(url)
        print(f"  {name}: status={r.status_code}, size={len(r.content)}")
        if r.status_code == 200 and len(r.content) > 100:
            # 尝试解码
            for enc in ["utf-8", "gbk", "gb2312"]:
                try:
                    text = r.content.decode(enc)
                    if text.startswith("{") or text.startswith("["):
                        data = json.loads(text)
                        print(f"    JSON ({enc}): {json.dumps(data, ensure_ascii=False)[:200]}")
                    else:
                        print(f"    HTML ({enc}): {text[:100]}")
                    break
                except:
                    continue
    except Exception as e:
        print(f"  {name}: ERROR {e}")
    time.sleep(0.2)

client.close()

# ── 保存结果 ──────────────────────────────────────────────────────
output = Path(__file__).parent / "data" / f"real_data_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
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
