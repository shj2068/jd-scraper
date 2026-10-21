#!/usr/bin/env python3
"""
京东电动工具多页数据采集 - 数据清洗与保存
从浏览器提取的原始数据中清洗出结构化商品信息
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
}

TOOL_KW = [
    "电钻", "手电钻", "冲击钻", "电锤", "角磨机", "磨光机", "切割机",
    "电动螺丝刀", "螺丝批", "起子机", "起子", "电链锯", "电锯",
    "打泡器", "打蛋器", "绞肉机", "捣蒜", "拉蒜", "刮鱼鳞",
    "工具箱套装", "电动工具", "锂电钻", "无刷",
    "打磨机", "修枝", "伐木", "砍树",
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


def clean_review(raw: str) -> str:
    if not raw:
        return ""
    m = re.search(r'(\d+[万]?\+?条评价)', raw)
    return m.group(1) if m else raw.strip()[:20]


def process_raw_products(raw_products: list, keyword: str, page: int) -> list:
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

        review = clean_review(p.get("review", ""))

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
            "page": page,
            "collected_at": datetime.now().isoformat(),
        })
    return cleaned


def load_existing(filepath: Path) -> list:
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_data(products: list, keyword: str):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = DATA_DIR / f"all_pages_{keyword}_{ts}.json"

    all_products = load_existing(DATA_DIR / f"all_pages_{keyword}_latest.json")
    existing_skus = {p["sku"] for p in all_products}

    new_count = 0
    for p in products:
        if p["sku"] not in existing_skus:
            all_products.append(p)
            existing_skus.add(p["sku"])
            new_count += 1

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    latest_path = DATA_DIR / f"all_pages_{keyword}_latest.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2)

    return new_count, len(all_products), filepath


def print_summary(products: list, keyword: str):
    brands = defaultdict(int)
    shops = defaultdict(int)
    categories = defaultdict(int)
    prices = []

    for p in products:
        brands[p["brand"]] += 1
        if p["shop"]:
            shops[p["shop"]] += 1
        categories[p["category"]] += 1
        if p["price"] > 0:
            prices.append(p["price"])

    print(f"\n{'='*60}")
    print(f"  关键词: {keyword}")
    print(f"  总商品数: {len(products)}")
    print(f"{'='*60}")

    print(f"\n  品牌分布:")
    for brand, count in sorted(brands.items(), key=lambda x: -x[1])[:15]:
        print(f"    {brand}: {count}")

    print(f"\n  商品分类:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        label = {"power_tool": "电动工具", "home_appliance": "家用电器", "unknown": "未分类"}.get(cat, cat)
        print(f"    {label}: {count}")

    if prices:
        print(f"\n  价格统计:")
        print(f"    最低: ¥{min(prices):.2f}")
        print(f"    最高: ¥{max(prices):.2f}")
        print(f"    均价: ¥{sum(prices)/len(prices):.2f}")

    print(f"\n  店铺 TOP 10:")
    for shop, count in sorted(shops.items(), key=lambda x: -x[1])[:10]:
        print(f"    {shop}: {count}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python collect_all_pages.py <input_json_file> [keyword] [page]")
        sys.exit(1)

    input_file = sys.argv[1]
    keyword = sys.argv[2] if len(sys.argv) > 2 else "电动工具"
    page = int(sys.argv[3]) if len(sys.argv) > 3 else 1

    with open(input_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    raw_products = raw_data if isinstance(raw_data, list) else raw_data.get("products", [])
    cleaned = process_raw_products(raw_products, keyword, page)
    new_count, total_count, filepath = save_data(cleaned, keyword)

    print(f"本页提取: {len(raw_products)} 条")
    print(f"清洗后: {len(cleaned)} 条")
    print(f"新增: {new_count} 条 (去重后)")
    print(f"累计: {total_count} 条")
    print(f"保存到: {filepath}")

    latest_path = DATA_DIR / f"all_pages_{keyword}_latest.json"
    all_data = load_existing(latest_path)
    print_summary(all_data, keyword)
