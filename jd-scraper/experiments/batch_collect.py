#!/usr/bin/env python3
"""
京东电动工具多关键词批量数据采集
通过不同细分关键词采集更多样化的商品数据
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
DATA_DIR.mkdir(parents=True, exist_ok=True)

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
    m = re.search(r'([\u4e00-\u9fa5A-Za-z（）()]+(?:旗舰店|自营店|专卖店|官方店|旺铺|自营旗舰店))', raw_shop)
    if m:
        return m.group(1)
    m = re.search(r'([\u4e00-\u9fa5A-Za-z（）()]{2,30}店)', raw_shop)
    if m:
        return m.group(1)
    return raw_shop.strip()[:40]


def process_raw_products(raw_products: list, keyword: str) -> list:
    cleaned = []
    for p in raw_products:
        title = p.get("title", "").strip()
        if not title or len(title) < 5:
            continue

        shop = clean_shop_name(p.get("shop", ""))
        brand = detect_brand(title, shop)
        category = classify_product(title)
        price = p.get("price", 0)
        if isinstance(price, str):
            try:
                price = float(price)
            except ValueError:
                price = 0

        review_raw = p.get("review", "")
        review = ""
        m = re.search(r'(\d+[万]?\+?条评价)', review_raw)
        if m:
            review = m.group(1)

        cleaned.append({
            "sku": p.get("sku", ""),
            "title": title[:120],
            "brand": brand,
            "category": category,
            "price": round(price, 2),
            "shop": shop,
            "review_count": review,
            "sales": p.get("sales", ""),
            "url": p.get("url", ""),
            "keyword": keyword,
            "collected_at": datetime.now().isoformat(),
        })
    return cleaned


def merge_and_dedup(all_products: list) -> list:
    seen = {}
    for p in all_products:
        sku = p["sku"]
        if sku not in seen:
            seen[sku] = p
        else:
            existing = seen[sku]
            if not existing.get("shop") and p.get("shop"):
                existing["shop"] = p["shop"]
            if not existing.get("review_count") and p.get("review_count"):
                existing["review_count"] = p["review_count"]
    return list(seen.values())


def print_full_report(products: list):
    brands = defaultdict(int)
    shops = defaultdict(int)
    categories = defaultdict(int)
    keywords = defaultdict(int)
    prices = []
    power_tool_prices = []

    for p in products:
        brands[p["brand"]] += 1
        if p["shop"]:
            shops[p["shop"]] += 1
        categories[p["category"]] += 1
        keywords[p.get("keyword", "")] += 1
        if p["price"] > 0:
            prices.append(p["price"])
            if p["category"] == "power_tool":
                power_tool_prices.append(p["price"])

    print(f"\n{'='*70}")
    print(f"  京东电动工具电商数据采集 - 综合报告")
    print(f"  采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")

    print(f"\n  [总览]")
    print(f"  总商品数: {len(products)} (去重后)")
    print(f"  覆盖关键词: {len(keywords)} 个")
    for kw, cnt in sorted(keywords.items(), key=lambda x: -x[1]):
        if kw:
            print(f"    - {kw}: {cnt} 件")

    print(f"\n  [品牌分布] (共 {len(brands)} 个品牌)")
    for i, (brand, count) in enumerate(sorted(brands.items(), key=lambda x: -x[1])):
        if i >= 20:
            print(f"    ... 及其他 {len(brands) - 20} 个品牌")
            break
        bar = "█" * min(count, 30)
        print(f"    {brand:12s}: {count:3d} {bar}")

    print(f"\n  [商品分类]")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        label = {"power_tool": "电动工具", "home_appliance": "家用电器", "unknown": "未分类"}.get(cat, cat)
        pct = count / len(products) * 100
        print(f"    {label:10s}: {count:3d} ({pct:.1f}%)")

    if prices:
        print(f"\n  [价格统计]")
        print(f"    最低: ¥{min(prices):.2f}")
        print(f"    最高: ¥{max(prices):.2f}")
        print(f"    均价: ¥{sum(prices)/len(prices):.2f}")
        print(f"    中位: ¥{sorted(prices)[len(prices)//2]:.2f}")

    if power_tool_prices:
        print(f"\n  [电动工具价格统计] ({len(power_tool_prices)} 件)")
        print(f"    最低: ¥{min(power_tool_prices):.2f}")
        print(f"    最高: ¥{max(power_tool_prices):.2f}")
        print(f"    均价: ¥{sum(power_tool_prices)/len(power_tool_prices):.2f}")

        ranges = [(0, 50), (50, 100), (100, 200), (200, 300), (300, 500), (500, 99999)]
        print(f"\n    价格区间分布:")
        for lo, hi in ranges:
            cnt = sum(1 for p in power_tool_prices if lo <= p < hi)
            label = f"¥{lo}-{hi}" if hi < 99999 else f"¥{lo}+"
            bar = "█" * min(cnt, 25)
            print(f"      {label:12s}: {cnt:3d} {bar}")

    print(f"\n  [店铺排名 TOP 15]")
    for i, (shop, count) in enumerate(sorted(shops.items(), key=lambda x: -x[1])):
        if i >= 15:
            break
        print(f"    {i+1:2d}. {shop}: {count} 件")

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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python batch_collect.py <input_json> [keyword]")
        print("   or: python batch_collect.py --merge")
        sys.exit(1)

    if sys.argv[1] == "--merge":
        all_data = []
        for f in sorted(DATA_DIR.glob("raw_page_*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    raw = data if isinstance(data, list) else data.get("products", [])
                    kw = f.stem.replace("raw_page_", "")
                    cleaned = process_raw_products(raw, kw)
                    all_data.extend(cleaned)
                    print(f"  {f.name}: {len(raw)} raw -> {len(cleaned)} cleaned")
            except Exception as e:
                print(f"  Error reading {f.name}: {e}")

        merged = merge_and_dedup(all_data)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = DATA_DIR / f"batch_all_keywords_{ts}.json"
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, ensure_ascii=False, indent=2)

        latest_path = DATA_DIR / "batch_all_keywords_latest.json"
        with open(latest_path, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, ensure_ascii=False, indent=2)

        print(f"\n合并完成: {len(merged)} 件商品 (去重后)")
        print(f"保存到: {out_path}")
        print_full_report(merged)
    else:
        input_file = sys.argv[1]
        keyword = sys.argv[2] if len(sys.argv) > 2 else "电动工具"

        with open(input_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        raw_products = raw_data if isinstance(raw_data, list) else raw_data.get("products", [])
        cleaned = process_raw_products(raw_products, keyword)

        out_name = f"raw_page_{keyword}.json"
        out_path = DATA_DIR / out_name
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)

        print(f"关键词: {keyword}")
        print(f"本页提取: {len(raw_products)} 条")
        print(f"清洗后: {len(cleaned)} 条")
        print(f"保存到: {out_path}")
