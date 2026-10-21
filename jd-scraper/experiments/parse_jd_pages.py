#!/usr/bin/env python3
"""解析京东分类页面和商品列表页，提取结构化数据"""
import httpx, re, json, sys, time
from pathlib import Path
from datetime import datetime

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.jd.com/",
}

results = {"categories": [], "products": [], "raw_pages": {}}

print("=" * 70)
print(f"  京东页面数据解析 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

client = httpx.Client(timeout=15.0, headers=HEADERS, follow_redirects=True)

# ── 阶段 1: 解析 allSort.aspx 分类数据 ─────────────────────────────
print("\n[阶段 1] 解析京东全分类页面 allSort.aspx")
try:
    r = client.get("https://www.jd.com/allSort.aspx")
    print(f"  status={r.status_code}, size={len(r.text)}")
    html = r.text
    results["raw_pages"]["allSort"] = {"size": len(html)}
    
    # 提取分类链接和名称
    # 常见模式: <a href="//list.jd.com/list.html?cat=xxx,yyy,zzz">分类名</a>
    cat_links = re.findall(r'<a[^>]*href=["\'](?://)?list\.jd\.com/list\.html\?cat=(\d+(?:,\d+)*)["\'][^>]*>(.*?)</a>', html, re.DOTALL)
    print(f"  分类链接数量: {len(cat_links)}")
    
    categories = []
    for cat_id, cat_name_raw in cat_links:
        cat_name = re.sub(r'<[^>]+>', '', cat_name_raw).strip()
        if cat_name and len(cat_name) > 0:
            categories.append({"id": cat_id, "name": cat_name, "url": f"https://list.jd.com/list.html?cat={cat_id}"})
    
    print(f"  有效分类: {len(categories)} 个")
    for cat in categories[:20]:
        print(f"    [{cat['id']}] {cat['name']}")
    
    results["categories"] = categories
    
    # 也提取更广泛的分类结构
    # 搜索所有 cat= 参数
    all_cats = set(re.findall(r'cat=(\d+(?:,\d+)*)', html))
    print(f"\n  所有 cat 参数: {len(all_cats)} 个")
    for c in sorted(all_cats)[:30]:
        print(f"    {c}")
    
except Exception as e:
    print(f"  ERROR: {e}")

time.sleep(0.5)

# ── 阶段 2: 解析商品列表页（多个类目）─────────────────────────────
print("\n[阶段 2] 解析商品列表页 list.jd.com")

# 工业相关类目
CAT_IDS = [
    ("6233,6257,6264", "轴承"),
    ("6233,6257,6265", "润滑油"),
    ("6233,6257,6266", "五金工具"),
    ("6233,6257,6267", "电动工具"),
    ("6233,6257,6268", "手动工具"),
    ("6728,6734,6740", "电子元器件"),
    ("6728,6734,6741", "连接器"),
    ("6233,6237,6240", "电动机"),
]

all_products = []

for cat_id, cat_name in CAT_IDS:
    try:
        url = f"https://list.jd.com/list.html?cat={cat_id}"
        r = client.get(url)
        print(f"\n  [{cat_id}] {cat_name}: status={r.status_code}, size={len(r.text)}")
        
        if len(r.text) < 1000:
            print(f"    页面太小，跳过")
            continue
            
        title = re.search(r'<title>(.*?)</title>', r.text)
        print(f"    title: {title.group(1)[:60] if title else '(无)'}")
        
        html = r.text
        
        # 提取商品 SKU
        skus = re.findall(r'data-sku=["\'](\d+)["\']', html)
        print(f"    SKU 数量: {len(skus)}")
        
        # 提取商品信息块
        # JD 列表页商品通常在 <li class="gl-item" data-sku="xxx"> 中
        items = re.findall(r'<li\s+class="gl-item"[^>]*data-sku="(\d+)"[^>]*>(.*?)</li>', html, re.DOTALL)
        print(f"    商品项数量: {len(items)}")
        
        for sku, item_html in items[:10]:
            product = {"sku": sku, "category": cat_name, "cat_id": cat_id}
            
            # 名称
            name_match = re.search(r'class="p-name[^"]*"[^>]*>\s*<a[^>]*>(.*?)</a>', item_html, re.DOTALL)
            if name_match:
                product["name"] = re.sub(r'<[^>]+>', '', name_match.group(1)).strip()
            
            # 价格
            price_match = re.search(r'<i>([\d.]+)</i>', item_html)
            if price_match:
                product["price"] = price_match.group(1)
            
            # 店铺
            shop_match = re.search(r'class="p-shop[^"]*"[^>]*>(.*?)</a>', item_html, re.DOTALL)
            if shop_match:
                product["shop"] = re.sub(r'<[^>]+>', '', shop_match.group(1)).strip()
            
            # 评价数
            review_match = re.search(r'(\d+)\s*条评价', item_html)
            if review_match:
                product["reviews"] = review_match.group(1)
            
            if product.get("name"):
                all_products.append(product)
                print(f"      [{sku}] {product.get('name', '')[:50]} ¥{product.get('price', '?')}")
        
        # 如果 li 模式失败，尝试其他模式
        if not items:
            # 尝试 data-sku 配合 div
            div_items = re.findall(r'<div[^>]*data-sku="(\d+)"[^>]*>', html)
            print(f"    div data-sku: {len(div_items)} 个")
            
            # 尝试提取所有商品名
            names = re.findall(r'<a[^>]*title="([^"]{10,})"[^>]*>', html)
            print(f"    商品标题: {len(names)} 个")
            for n in names[:5]:
                print(f"      - {n[:60]}")
                all_products.append({"sku": "", "name": n, "category": cat_name, "cat_id": cat_id})
        
        results["raw_pages"][f"list_{cat_id.replace(',', '_')}"] = {
            "size": len(html), "skus": len(skus), "items": len(items)
        }
        
    except Exception as e:
        print(f"    ERROR: {e}")
    time.sleep(0.5)

results["products"] = all_products

# ── 阶段 3: 尝试京东工业品专属列表 ──────────────────────────────
print("\n[阶段 3] 京东工业品频道页")
try:
    r = client.get("https://gong.jd.com")
    print(f"  status={r.status_code}, size={len(r.text)}")
    # 提取页面中的所有 list.jd.com 链接
    list_links = re.findall(r'href=["\']([^"\']*list\.jd\.com[^"\']*)["\']', r.text)
    print(f"  list.jd.com 链接: {len(list_links)} 个")
    for link in list_links[:10]:
        print(f"    {link}")
    
    # 提取所有分类/导航链接
    nav_links = re.findall(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r.text, re.DOTALL)
    clean_nav = [(url, re.sub(r'<[^>]+>', '', text).strip()) for url, text in nav_links if re.sub(r'<[^>]+>', '', text).strip()]
    print(f"  导航链接: {len(clean_nav)} 个")
    for url, text in clean_nav[:15]:
        print(f"    {text} -> {url[:80]}")
except Exception as e:
    print(f"  ERROR: {e}")

client.close()

# ── 保存结果 ──────────────────────────────────────────────────────
output = Path(__file__).parent / "data" / f"parsed_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
output.parent.mkdir(parents=True, exist_ok=True)
with open(output, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n" + "=" * 70)
print("  解析汇总")
print("=" * 70)
print(f"  分类: {len(results['categories'])} 个")
print(f"  商品: {len(results['products'])} 个")
print(f"  结果: {output}")
print("=" * 70)
