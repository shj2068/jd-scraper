#!/usr/bin/env python3
"""
京东电动工具数据合并与综合报告生成
Merge all raw data files + previous session data, deduplicate by SKU, generate report.

Data sources:
  1. raw_page1.json            - 60 products (keyword: 电动工具, from batch_collect)
  2. raw_page_电钻.json        - 60 products (keyword: 电钻, from browser scrape)
  3. jd_power_tools_final_20261021_220622.json - 34 products (previous browser session)
  4. all_pages_电动工具_latest.json - already-processed multi-page products
"""
import json
import os
import re
import sys
import io
from datetime import datetime
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DATA_DIR = Path(__file__).parent / "data"

# ── Brand & classification logic (same as batch_collect.py) ──

BRAND_MAP = {
    "东成": ["东成"],
    "博世": ["博世", "BOSCH"],
    "德力西电气": ["德力西电气", "德力西"],
    "得力": ["得力", "deli"],
    "欧莱德": ["欧莱德", "OULAIDE"],
    "绿林": ["绿林", "GREENER"],
    "大有": ["大有", "Devon"],
    "威克士": ["威克士", "WORX"],
    "小米": ["小米", "米家"],
    "苏泊尔": ["苏泊尔", "SUPOR"],
    "飞科": ["飞科", "FLYCO"],
    "志高": ["志高", "CHIGO"],
    "小熊": ["小熊", "Bear"],
    "荣事达": ["荣事达", "Royalstar"],
    "奥克斯": ["奥克斯", "AUX"],
    "康佳": ["康佳", "KONKA"],
    "班帝森": ["班帝森"],
    "爱瑞德": ["爱瑞德"],
    "双枪": ["双枪", "Suncha"],
    "名创优品": ["名创优品"],
    "京造": ["京东京造", "京造"],
    "林也": ["林也"],
    "五羊本田王": ["五羊本田王"],
    "三个小厨": ["三个小厨"],
    "炊大皇": ["炊大皇"],
    "FACE MINI": ["FACE MINI"],
    "YOOKO": ["YOOKO"],
    "Seemagic": ["Seemagic", "醒刻"],
    "LOROLI": ["LOROLI"],
    "BABYSIR": ["BABYSIR"],
    "牧田": ["牧田", "Makita"],
    "百得": ["百得", "Black+Decker"],
    "史丹利": ["史丹利", "Stanley"],
    "日立": ["日立", "HITACHI"],
    "锐壹": ["锐壹"],
    "芝浦": ["芝浦"],
    "龙韵": ["龙韵"],
    "科麦斯": ["科麦斯"],
    "老A": ["老A"],
    "赛特": ["赛特"],
    "宝时德": ["宝时德"],
    "大艺": ["大艺"],
    "HOTO小猴": ["HOTO小猴", "HOTO"],
    "西默德": ["西默德"],
    "皇恩": ["皇恩"],
    "千禧红": ["千禧红"],
    "优力特": ["优力特"],
    "上海人民": ["上海人民"],
    "亚特": ["亚特", "YAT"],
    "星固": ["星固"],
    "光宸": ["光宸"],
    "拜杰": ["拜杰"],
}

TOOL_KW = [
    "电钻", "手电钻", "冲击钻", "电锤", "角磨机", "磨光机", "切割机",
    "电动螺丝刀", "螺丝批", "起子机", "起子", "电链锯", "电锯",
    "打泡器", "打蛋器", "绞肉机", "捣蒜", "拉蒜", "刮鱼鳞",
    "工具箱套装", "电动工具", "锂电钻", "无刷",
    "打磨机", "修枝", "伐木", "砍树", "电磨", "雕刻",
    "热风枪", "电刨", "砂纸机", "砂轮机",
]

HOME_KW = [
    "理发器", "电推剪", "电推子", "剃头", "剪发",
    "抽水器", "上水器", "压水器", "饮水机", "取水器",
    "指甲刀", "磨甲器", "鼻毛", "烫睫毛",
    "灰指甲", "打磨器",
    "奶泡", "打奶",
]


def detect_brand(title: str, shop: str) -> str:
    text = title + " " + shop
    for brand, keywords in BRAND_MAP.items():
        for kw in keywords:
            if kw in text:
                return brand
    return "其他"


def classify_product(title: str) -> str:
    for kw in TOOL_KW:
        if kw in title:
            return "power_tool"
    for kw in HOME_KW:
        if kw in title:
            return "home_appliance"
    return "unknown"


def clean_shop_name(raw_shop: str) -> str:
    if not raw_shop:
        return ""
    m = re.search(
        r'([\u4e00-\u9fa5A-Za-z（）()]+(?:旗舰店|自营店|专卖店|官方店|旺铺|自营旗舰店))',
        raw_shop,
    )
    if m:
        return m.group(1)
    m = re.search(r'([\u4e00-\u9fa5A-Za-z（）()]{2,30}店)', raw_shop)
    if m:
        return m.group(1)
    return raw_shop.strip()[:40]


def normalize_review(raw: str) -> str:
    if not raw:
        return ""
    m = re.search(r'(\d+[万]?\+?条评价)', raw)
    return m.group(1) if m else raw


def normalize_product(p: dict, source_keyword: str = "") -> dict:
    """Normalize a product dict from any source into a unified schema."""
    title = (p.get("title") or "").strip()
    shop = clean_shop_name(p.get("shop", ""))
    brand = p.get("brand", "") or detect_brand(title, shop)
    category = p.get("category", "") or classify_product(title)

    price = p.get("price", 0)
    if isinstance(price, str):
        try:
            price = float(price)
        except ValueError:
            price = 0

    review = normalize_review(p.get("review", "") or p.get("review_count", ""))

    return {
        "sku": str(p.get("sku", "")),
        "title": title[:150],
        "brand": brand,
        "category": category,
        "price": round(price, 2),
        "shop": shop,
        "review_count": review,
        "sales": p.get("sales", ""),
        "url": p.get("url", ""),
        "keyword": p.get("keyword", "") or source_keyword,
        "approval": p.get("approval", ""),
        "collected_at": p.get("collected_at", datetime.now().isoformat()),
    }


# ── Data loading ──

def load_raw_page(filepath: Path, keyword: str) -> list:
    """Load raw_page*.json files (format: {count, products: [...]})"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data if isinstance(data, list) else data.get("products", [])
        products = [normalize_product(p, keyword) for p in raw]
        return [p for p in products if p["sku"] and p["title"]]
    except Exception as e:
        print(f"  [WARN] Error reading {filepath.name}: {e}")
        return []


def load_final_report(filepath: Path) -> list:
    """Load jd_power_tools_final_*.json (report format with products array)."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("products", [])
        products = [normalize_product(p, "") for p in raw]
        return [p for p in products if p["sku"] and p["title"]]
    except Exception as e:
        print(f"  [WARN] Error reading {filepath.name}: {e}")
        return []


def load_all_pages(filepath: Path) -> list:
    """Load all_pages_*.json (already-normalized array)."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data if isinstance(data, list) else data.get("products", [])
        products = [normalize_product(p, "") for p in raw]
        return [p for p in products if p["sku"] and p["title"]]
    except Exception as e:
        print(f"  [WARN] Error reading {filepath.name}: {e}")
        return []


def merge_and_dedup(all_products: list) -> list:
    """Deduplicate by SKU, keeping the record with the richest data."""
    seen = {}
    for p in all_products:
        sku = p["sku"]
        if sku not in seen:
            seen[sku] = p
        else:
            existing = seen[sku]
            # Merge: fill in missing fields from the newer record
            for key in ("shop", "review_count", "brand", "category", "keyword", "approval", "url"):
                if not existing.get(key) and p.get(key):
                    existing[key] = p[key]
            # Keep the longer title
            if len(p.get("title", "")) > len(existing.get("title", "")):
                existing["title"] = p["title"]
    return list(seen.values())


# ── Report generation ──

def generate_report(products: list, source_stats: dict):
    brands = defaultdict(int)
    shops = defaultdict(int)
    categories = defaultdict(int)
    keywords = defaultdict(int)
    prices = []
    power_tool_prices = []
    home_appliance_prices = []

    for p in products:
        brands[p["brand"]] += 1
        if p["shop"]:
            shops[p["shop"]] += 1
        categories[p["category"]] += 1
        kw = p.get("keyword", "")
        if kw:
            keywords[kw] += 1
        if p["price"] > 0:
            prices.append(p["price"])
            if p["category"] == "power_tool":
                power_tool_prices.append(p["price"])
            elif p["category"] == "home_appliance":
                home_appliance_prices.append(p["price"])

    print(f"\n{'='*72}")
    print(f"  京东电动工具 - 全量数据合并报告")
    print(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*72}")

    # Source stats
    print(f"\n  [数据来源]")
    for src, cnt in source_stats.items():
        print(f"    {src}: {cnt} 条")
    total_raw = sum(source_stats.values())
    print(f"    {'─'*40}")
    print(f"    原始合计: {total_raw} 条 -> 去重后: {len(products)} 条")
    print(f"    重复剔除: {total_raw - len(products)} 条")

    # Category breakdown
    print(f"\n  [商品分类]")
    cat_labels = {"power_tool": "电动工具", "home_appliance": "家用电器", "unknown": "未分类"}
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        label = cat_labels.get(cat, cat)
        pct = count / len(products) * 100
        bar = "█" * min(count, 35)
        print(f"    {label:10s}: {count:3d} ({pct:5.1f}%) {bar}")

    # Keyword coverage
    if keywords:
        print(f"\n  [关键词覆盖] ({len(keywords)} 个)")
        for kw, cnt in sorted(keywords.items(), key=lambda x: -x[1]):
            if kw:
                print(f"    {kw:15s}: {cnt:3d} 件")

    # Brand distribution
    print(f"\n  [品牌分布] (共 {len(brands)} 个品牌)")
    for i, (brand, count) in enumerate(sorted(brands.items(), key=lambda x: -x[1])):
        if i >= 25:
            remaining = len(brands) - 25
            if remaining > 0:
                print(f"    ... 及其他 {remaining} 个品牌")
            break
        bar = "█" * min(count, 30)
        print(f"    {brand:12s}: {count:3d} {bar}")

    # Price statistics
    if prices:
        print(f"\n  [整体价格统计] ({len(prices)} 件有价格)")
        print(f"    最低: ¥{min(prices):.2f}")
        print(f"    最高: ¥{max(prices):.2f}")
        print(f"    均价: ¥{sum(prices)/len(prices):.2f}")
        sorted_prices = sorted(prices)
        print(f"    中位: ¥{sorted_prices[len(sorted_prices)//2]:.2f}")

    if power_tool_prices:
        print(f"\n  [电动工具价格统计] ({len(power_tool_prices)} 件)")
        print(f"    最低: ¥{min(power_tool_prices):.2f}")
        print(f"    最高: ¥{max(power_tool_prices):.2f}")
        print(f"    均价: ¥{sum(power_tool_prices)/len(power_tool_prices):.2f}")

        ranges = [(0, 50), (50, 100), (100, 200), (200, 300), (300, 500), (500, 99999)]
        print(f"    价格区间分布:")
        for lo, hi in ranges:
            cnt = sum(1 for p in power_tool_prices if lo <= p < hi)
            label = f"¥{lo}-{hi}" if hi < 99999 else f"¥{lo}+"
            bar = "█" * min(cnt, 25)
            print(f"      {label:12s}: {cnt:3d} {bar}")

    if home_appliance_prices:
        print(f"\n  [家用电器价格统计] ({len(home_appliance_prices)} 件)")
        print(f"    最低: ¥{min(home_appliance_prices):.2f}")
        print(f"    最高: ¥{max(home_appliance_prices):.2f}")
        print(f"    均价: ¥{sum(home_appliance_prices)/len(home_appliance_prices):.2f}")

    # Top shops
    print(f"\n  [店铺排名 TOP 20]")
    for i, (shop, count) in enumerate(sorted(shops.items(), key=lambda x: -x[1])):
        if i >= 20:
            break
        bar = "█" * min(count, 20)
        print(f"    {i+1:2d}. {shop}: {count} 件 {bar}")

    # Brand detail for power tools
    tool_brands = defaultdict(lambda: {"count": 0, "prices": []})
    for p in products:
        if p["category"] == "power_tool":
            tool_brands[p["brand"]]["count"] += 1
            if p["price"] > 0:
                tool_brands[p["brand"]]["prices"].append(p["price"])

    print(f"\n  [电动工具品牌详情]")
    for brand, info in sorted(tool_brands.items(), key=lambda x: -x[1]["count"]):
        avg = sum(info["prices"]) / len(info["prices"]) if info["prices"] else 0
        print(f"    {brand:12s}: {info['count']:3d} 件, 均价 ¥{avg:.2f}")

    # Top products by review count
    print(f"\n  [高评价商品 TOP 10]")
    def review_sort_key(p):
        r = p.get("review_count", "")
        m = re.search(r'(\d+)(万)?', r)
        if m:
            val = int(m.group(1))
            if m.group(2):
                val *= 10000
            return val
        return 0

    top_reviewed = sorted(products, key=review_sort_key, reverse=True)[:10]
    for i, p in enumerate(top_reviewed):
        print(f"    {i+1:2d}. [{p['review_count']:>10s}] ¥{p['price']:>8.2f}  {p['title'][:50]}")

    return {
        "total": len(products),
        "brands": len(brands),
        "shops": len(shops),
        "categories": dict(categories),
        "keywords": dict(keywords),
    }


# ── Main ──

def main():
    print("=" * 72)
    print("  京东电动工具数据合并工具")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)

    all_products = []
    source_stats = {}

    # 1. Load raw_page1.json (电动工具 keyword)
    f = DATA_DIR / "raw_page1.json"
    if f.exists():
        prods = load_raw_page(f, "电动工具")
        source_stats["raw_page1.json (电动工具)"] = len(prods)
        all_products.extend(prods)
        print(f"  [OK] {f.name}: {len(prods)} products loaded")
    else:
        print(f"  [SKIP] {f.name}: not found")

    # 2. Load raw_page_电钻.json
    f = DATA_DIR / "raw_page_电钻.json"
    if f.exists():
        prods = load_raw_page(f, "电钻")
        source_stats["raw_page_电钻.json (电钻)"] = len(prods)
        all_products.extend(prods)
        print(f"  [OK] {f.name}: {len(prods)} products loaded")
    else:
        print(f"  [SKIP] {f.name}: not found")

    # 3. Load jd_power_tools_final_20261021_220622.json
    f = DATA_DIR / "jd_power_tools_final_20261021_220622.json"
    if f.exists():
        prods = load_final_report(f)
        source_stats["jd_power_tools_final (previous session)"] = len(prods)
        all_products.extend(prods)
        print(f"  [OK] {f.name}: {len(prods)} products loaded")
    else:
        print(f"  [SKIP] {f.name}: not found")

    # 4. Load all_pages_电动工具_latest.json
    f = DATA_DIR / "all_pages_电动工具_latest.json"
    if f.exists():
        prods = load_all_pages(f)
        source_stats["all_pages_电动工具_latest.json"] = len(prods)
        all_products.extend(prods)
        print(f"  [OK] {f.name}: {len(prods)} products loaded")
    else:
        print(f"  [SKIP] {f.name}: not found")

    # 5. Scan for any other raw_page_*.json files not yet loaded
    loaded_names = {"raw_page1.json", "raw_page_电钻.json"}
    for f in sorted(DATA_DIR.glob("raw_page_*.json")):
        if f.name in loaded_names:
            continue
        kw = f.stem.replace("raw_page_", "")
        prods = load_raw_page(f, kw)
        source_stats[f"{f.name} ({kw})"] = len(prods)
        all_products.extend(prods)
        print(f"  [OK] {f.name}: {len(prods)} products loaded")

    print(f"\n  原始总计: {len(all_products)} 条")

    # Merge & dedup
    merged = merge_and_dedup(all_products)
    print(f"  去重后:   {len(merged)} 条")

    # Sort by SKU for consistent output
    merged.sort(key=lambda p: p["sku"])

    # Save merged data
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = DATA_DIR / f"merged_all_data_{ts}.json"
    output_data = {
        "report_title": "京东电动工具全量合并数据",
        "generated_at": datetime.now().isoformat(),
        "total_products": len(merged),
        "sources": source_stats,
        "products": merged,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"\n  合并数据已保存: {out_path}")

    # Also save as latest
    latest_path = DATA_DIR / "merged_all_data_latest.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"  最新副本已保存: {latest_path}")

    # Generate report
    stats = generate_report(merged, source_stats)

    print(f"\n{'='*72}")
    print(f"  合并完成!")
    print(f"  总商品: {stats['total']} | 品牌: {stats['brands']} | 店铺: {stats['shops']}")
    print(f"{'='*72}")


if __name__ == "__main__":
    main()
