#!/usr/bin/env python3
"""
京东电动工具电商数据采集
采集目标: 品牌、价格、销量前十店铺
仅用于技术学习与研究
"""

import httpx
import json
import re
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.jd.com/",
}

KEYWORD = "电动工具"
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def extract_products_from_search(html: str) -> list[dict]:
    """从搜索结果 HTML 提取商品数据"""
    products = []

    # 提取 SKU
    skus = re.findall(r'data-sku=["\'](\d+)["\']', html)

    # 提取商品名称
    names = re.findall(
        r'<div class="p-name[^"]*">\s*<a[^>]*>(.*?)</a>', html, re.DOTALL
    )
    if not names:
        names = re.findall(
            r'class="p-name[^"]*"[^>]*>\s*<em>(.*?)</em>', html, re.DOTALL
        )

    # 提取价格
    prices = re.findall(
        r'<strong class="p-price"[^>]*>\s*<i>([\d.]+)</i>', html
    )

    # 提取店铺
    shops = re.findall(
        r'<a class="p-shop[^"]*"[^>]*data-shop_name=["\']([^"\']+)["\']', html
    )
    if not shops:
        shops = re.findall(
            r'<a class="p-shop[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL
        )
        shops = [re.sub(r"<[^>]+>", "", s).strip() for s in shops]

    # 提取评论数/销量线索
    comments = re.findall(
        r'<strong class="p-commit"[^>]*>\s*<a[^>]*>([\d.]+[万]?)</a>', html
    )

    # 提取品牌 (从标题或店铺名推断)
    brands = re.findall(
        r'<div class="p-name[^"]*">\s*<a[^>]*>.*?<em>([^<]{2,10})</em>',
        html,
        re.DOTALL,
    )

    count = max(len(skus), len(names), len(prices))
    for i in range(count):
        product = {}
        if i < len(skus):
            product["sku"] = skus[i]
        if i < len(names):
            product["name"] = re.sub(r"<[^>]+>", "", names[i]).strip()
        if i < len(prices):
            product["price"] = float(prices[i])
        if i < len(shops):
            product["shop"] = shops[i] if shops[i] else "京东自营"
        if i < len(comments):
            product["comments"] = comments[i]
        if i < len(brands):
            product["brand_hint"] = brands[i].strip()
        if product:
            products.append(product)

    return products


def extract_brands_from_search(html: str) -> list[str]:
    """从搜索结果页提取品牌筛选栏"""
    brands = []
    # 品牌筛选区域
    brand_section = re.search(
        r'id="J_brand"[^>]*>(.*?)(?=<div class="p-wrap")', html, re.DOTALL
    )
    if brand_section:
        brand_links = re.findall(
            r'<a[^>]*data-value=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            brand_section.group(1),
            re.DOTALL,
        )
        for val, name in brand_links:
            clean = re.sub(r"<[^>]+>", "", name).strip()
            if clean and len(clean) <= 20:
                brands.append(clean)
    return brands


def collect_search_pages(keyword: str, max_pages: int = 5) -> list[dict]:
    """采集多页搜索结果"""
    all_products = []
    all_brands = set()
    client = httpx.Client(timeout=20.0, headers=HEADERS, follow_redirects=True)

    for page in range(1, max_pages + 1):
        offset = (page - 1) * 30
        print(f"  [搜索] 第 {page}/{max_pages} 页 (offset={offset})...", end=" ")

        try:
            r = client.get(
                "https://search.jd.com/Search",
                params={
                    "keyword": keyword,
                    "enc": "utf-8",
                    "page": page,
                    "s": offset + 1,
                    "scrolling": "y",
                },
            )
            print(f"status={r.status_code}, size={len(r.text)}", end="")

            if r.status_code == 200 and len(r.text) > 1000:
                products = extract_products_from_search(r.text)
                brands = extract_brands_from_search(r.text)
                all_products.extend(products)
                all_brands.update(brands)
                print(f", 商品={len(products)}, 品牌={len(brands)}")
            else:
                print(" (无有效数据)")

        except Exception as e:
            print(f"ERROR: {e}")

        time.sleep(1.5)

    client.close()
    return all_products, list(all_brands)


def collect_category_brands() -> list[str]:
    """从分类 API 获取电动工具相关品牌"""
    brands = []
    client = httpx.Client(timeout=15.0, headers=HEADERS, follow_redirects=True)

    print("  [分类] 获取电动工具分类品牌...", end=" ")
    try:
        r = client.get("https://dc.3.cn/category/get")
        text = r.content.decode("gbk", errors="replace")
        data = json.loads(text)

        if "data" in data:
            for item in data["data"]:
                b_info = item.get("b", [])
                for b in b_info:
                    parts = b.split("|")
                    if len(parts) >= 2:
                        brands.append(parts[1])
        print(f"品牌数={len(brands)}")
    except Exception as e:
        print(f"ERROR: {e}")

    client.close()
    return brands


def collect_top_stores(keyword: str, max_pages: int = 5) -> dict[str, dict]:
    """统计店铺销量排名"""
    shop_stats = defaultdict(lambda: {"count": 0, "total_price": 0.0, "products": []})

    products, _ = collect_search_pages(keyword, max_pages)

    for p in products:
        shop = p.get("shop", "未知店铺")
        if not shop or shop == "未知店铺":
            continue
        shop_stats[shop]["count"] += 1
        if "price" in p:
            shop_stats[shop]["total_price"] += p["price"]
            shop_stats[shop]["products"].append(p)

    # 按商品数量排序 (代理销量)
    ranked = sorted(shop_stats.items(), key=lambda x: x[1]["count"], reverse=True)
    return {shop: stats for shop, stats in ranked}


def collect_price_distribution(keyword: str, max_pages: int = 5) -> dict:
    """分析价格分布"""
    products, _ = collect_search_pages(keyword, max_pages)

    prices = [p["price"] for p in products if "price" in p]
    if not prices:
        return {"error": "无价格数据"}

    prices_sorted = sorted(prices)
    return {
        "count": len(prices),
        "min": min(prices),
        "max": max(prices),
        "avg": round(sum(prices) / len(prices), 2),
        "median": prices_sorted[len(prices_sorted) // 2],
        "p25": prices_sorted[len(prices_sorted) // 4],
        "p75": prices_sorted[(3 * len(prices_sorted)) // 4],
        "ranges": {
            "0-100": sum(1 for p in prices if p <= 100),
            "100-300": sum(1 for p in prices if 100 < p <= 300),
            "300-500": sum(1 for p in prices if 300 < p <= 500),
            "500-1000": sum(1 for p in prices if 500 < p <= 1000),
            "1000+": sum(1 for p in prices if p > 1000),
        },
    }


def collect_brand_distribution(keyword: str, max_pages: int = 5) -> list[dict]:
    """统计品牌分布"""
    products, page_brands = collect_search_pages(keyword, max_pages)

    brand_count = defaultdict(int)
    for p in products:
        # 从商品名提取品牌线索
        name = p.get("name", "")
        brand_hint = p.get("brand_hint", "")

        # 常见电动工具品牌
        known_brands = [
            "博世", "BOSCH", "得伟", "DEWALT", "牧田", "MAKITA",
            "东成", "大有", "威克士", "WORX", "史丹利", "STANLEY",
            "百得", "BLACK+DECKER", "日立", "HITACHI", "松下",
            "Panasonic", "麦太保", "METABO", "锐奇", "KEN",
            "科麦斯", "奥奔", "芝浦", "龙韵", "威达",
            "京东京造", "得力", "DELIXI", "德力西",
        ]

        detected = None
        for brand in known_brands:
            if brand in name or brand in brand_hint:
                detected = brand
                break

        if detected:
            brand_count[detected] += 1

    # 也统计页面品牌筛选栏
    for b in page_brands:
        brand_count[b] = brand_count.get(b, 0) + 1

    ranked = sorted(brand_count.items(), key=lambda x: x[1], reverse=True)
    return [{"brand": name, "count": count} for name, count in ranked]


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("=" * 70)
    print(f"  京东电动工具电商数据采集 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  关键词: {KEYWORD}")
    print("=" * 70)

    result = {
        "keyword": KEYWORD,
        "fetch_time": datetime.now().isoformat(),
        "brands": [],
        "price_distribution": {},
        "top_stores": [],
        "brand_distribution": [],
        "sample_products": [],
    }

    # ── 1. 分类品牌 ──────────────────────────────────────────────
    print("\n[1/5] 分类品牌数据")
    cat_brands = collect_category_brands()
    result["category_brands"] = cat_brands[:50]
    print(f"  获取到 {len(cat_brands)} 个品牌")

    time.sleep(1)

    # ── 2. 品牌分布 ──────────────────────────────────────────────
    print(f"\n[2/5] 品牌分布统计 (关键词: {KEYWORD})")
    brand_dist = collect_brand_distribution(KEYWORD, max_pages=5)
    result["brand_distribution"] = brand_dist[:30]
    print(f"  检测到 {len(brand_dist)} 个品牌")
    for b in brand_dist[:10]:
        print(f"    {b['brand']}: {b['count']} 次")

    time.sleep(1)

    # ── 3. 价格分布 ──────────────────────────────────────────────
    print(f"\n[3/5] 价格分布分析")
    price_dist = collect_price_distribution(KEYWORD, max_pages=5)
    result["price_distribution"] = price_dist
    if "error" not in price_dist:
        print(f"  样本数: {price_dist['count']}")
        print(f"  价格范围: ¥{price_dist['min']} - ¥{price_dist['max']}")
        print(f"  平均价格: ¥{price_dist['avg']}")
        print(f"  中位数: ¥{price_dist['median']}")
        print(f"  区间分布:")
        for range_name, count in price_dist.get("ranges", {}).items():
            bar = "█" * count
            print(f"    ¥{range_name}: {bar} ({count})")

    time.sleep(1)

    # ── 4. 销量前十店铺 ──────────────────────────────────────────
    print(f"\n[4/5] 销量前十店铺统计")
    top_stores = collect_top_stores(KEYWORD, max_pages=5)
    top_10 = list(top_stores.items())[:10]
    result["top_stores"] = [
        {
            "rank": i + 1,
            "shop": shop,
            "product_count": stats["count"],
            "avg_price": round(stats["total_price"] / stats["count"], 2) if stats["count"] > 0 else 0,
        }
        for i, (shop, stats) in enumerate(top_10)
    ]

    print(f"  共 {len(top_stores)} 个店铺")
    print(f"\n  {'排名':<4} {'店铺':<30} {'商品数':<8} {'均价':<10}")
    print(f"  {'─' * 4} {'─' * 30} {'─' * 8} {'─' * 10}")
    for store in result["top_stores"]:
        print(
            f"  {store['rank']:<4} {store['shop']:<30} "
            f"{store['product_count']:<8} ¥{store['avg_price']:<10}"
        )

    time.sleep(1)

    # ── 5. 采样商品 ──────────────────────────────────────────────
    print(f"\n[5/5] 采样商品详情")
    products, _ = collect_search_pages(KEYWORD, max_pages=3)
    result["sample_products"] = products[:20]
    print(f"  采集 {len(products)} 个商品, 展示前 20 个:")
    for i, p in enumerate(products[:20]):
        price_str = f"¥{p['price']}" if "price" in p else "N/A"
        shop_str = p.get("shop", "N/A")
        name_str = p.get("name", "N/A")[:50]
        print(f"  [{i+1:2d}] {name_str}")
        print(f"       价格: {price_str} | 店铺: {shop_str}")

    # ── 保存结果 ─────────────────────────────────────────────────
    output = DATA_DIR / f"jd_power_tools_{ts}.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # ── 汇总 ─────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  采集汇总")
    print("=" * 70)
    print(f"  关键词: {KEYWORD}")
    print(f"  分类品牌: {len(result.get('category_brands', []))} 个")
    print(f"  检测品牌: {len(result.get('brand_distribution', []))} 个")
    print(f"  价格样本: {result.get('price_distribution', {}).get('count', 0)} 个")
    print(f"  店铺总数: {len(top_stores)} 个")
    print(f"  采样商品: {len(result.get('sample_products', []))} 个")
    print(f"  输出文件: {output}")
    print("=" * 70)


if __name__ == "__main__":
    main()
