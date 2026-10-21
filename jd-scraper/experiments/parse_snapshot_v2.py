#!/usr/bin/env python3
"""从浏览器快照解析京东电动工具搜索数据 - v2"""
import re, json, sys, io
from pathlib import Path
from datetime import datetime
from collections import Counter

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

SNAPSHOT = Path(r"C:\Users\jie20\.qoder-cn\tmp\d--tongyi\1b7f4d3f-6acb-4c2a-89e5-eb6422276c5f\tool-results\browser-use_take_snapshot_c57c610dfa00.txt")
text = SNAPSHOT.read_text(encoding="utf-8")

# 提取所有 (uid, type, value) 三元组
elements = re.findall(r'uid=(\d+_\d+) (\w+)(?: "([^"]*)")?', text)

# 按顺序提取 StaticText 值
static_texts = [(uid, val) for uid, typ, val in elements if typ == "StaticText" and val]

# 提取所有 link URL (包含商品PID)
links = []
for m in re.finditer(r'uid=(\d+_\d+) link.*?url="([^"]+)"', text):
    links.append((m.group(1), m.group(2)))
# 也提取 StaticText
elements_st = re.findall(r'uid=(\d+_\d+) StaticText "([^"]*)"', text)
pid_map = {}
for uid, url in links:
    if "pid=" in url:
        pid_match = re.search(r'pid=(\d+)', url)
        if pid_match:
            pid_map[uid] = pid_match.group(1)

# 提取商品名称 - 从 link URL 的 wname 参数
product_names_from_links = {}
for uid, url in links:
    wname_match = re.search(r'wname=([^&]+)', url)
    seller_match = re.search(r'seller=([^&]+)', url)
    pid_match = re.search(r'pid=(\d+)', url)
    if wname_match and pid_match:
        from urllib.parse import unquote
        name = unquote(unquote(wname_match.group(1)))
        seller = unquote(unquote(seller_match.group(1))) if seller_match else ""
        product_names_from_links[pid_match.group(1)] = {"name": name, "seller": seller}

# 提取价格 - 找 "¥" 后跟数字的模式
# 在 StaticText 序列中找: "¥" -> "数字" -> "." -> "小数"
prices_by_position = {}
for i, (uid, val) in enumerate(static_texts):
    if val == "¥" and i + 3 < len(static_texts):
        _, int_part = static_texts[i + 1]
        _, dot = static_texts[i + 2]
        _, dec_part = static_texts[i + 3]
        if dot == "." and int_part.isdigit():
            try:
                price = float(f"{int_part}.{dec_part}")
                prices_by_position[i] = price
            except:
                pass

# 提取评价数和店铺 - 从 StaticText 序列
review_pattern = re.compile(r'(\d+万?\+?)条评价')
approval_pattern = re.compile(r'(\d+)%好评')

# 构建商品列表 - 从 link URL 提取最准确
products = []
seen_pids = set()
for pid, info in product_names_from_links.items():
    if pid in seen_pids:
        continue
    seen_pids.add(pid)
    name = info["name"]
    seller = info["seller"]

    # 识别品牌
    BRANDS = ["东成", "欧莱德", "德力西电气", "大有", "绿林", "博世", "得力", "飞科",
              "苏泊尔", "小熊", "志高", "康佳", "荣事达", "双枪", "奥克斯", "京造",
              "Seemagic", "拜杰", "LOROLI", "班帝森"]
    brand = ""
    for b in BRANDS:
        if b in name or b in seller:
            brand = b
            break

    products.append({
        "pid": pid,
        "name": name,
        "shop": seller,
        "brand": brand,
        "price": 0,
        "reviews": "",
        "sales": "",
    })

# 从 StaticText 序列中提取评价和店铺信息，关联到商品
# 策略: 找 "X万+条评价" 和 店铺名，按顺序关联
review_shop_pairs = []
for i, (uid, val) in enumerate(static_texts):
    if "条评价" in val:
        review = val
        # 向后找店铺名
        shop = ""
        for j in range(i + 1, min(i + 10, len(static_texts))):
            _, sv = static_texts[j]
            if "旗舰店" in sv or "自营店" in sv or "专卖店" in sv or "官方店" in sv or "旗舰店" in sv:
                shop = sv
                break
            if sv == "¥" or "条评价" in sv:
                break
        review_shop_pairs.append({"reviews": review, "shop": shop})

# 将评价/店铺信息关联到商品(按顺序)
for i, p in enumerate(products):
    if i < len(review_shop_pairs):
        p["reviews"] = review_shop_pairs[i]["reviews"]
        if not p["shop"] and review_shop_pairs[i]["shop"]:
            p["shop"] = review_shop_pairs[i]["shop"]

# 提取价格 - 按顺序关联
price_list = list(prices_by_position.values())
# 每个商品有两个价格(到手价+原价), 取第一个
for i, p in enumerate(products):
    price_idx = i * 2
    if price_idx < len(price_list):
        p["price"] = price_list[price_idx]

# 过滤电动工具
TOOL_KW = ["电钻", "角磨机", "螺丝刀", "电起子", "扳手", "切割机", "磨光机", "电刨", "电锯",
           "砂轮机", "冲击钻", "电锤", "电动工具", "手电钻", "起子机", "电螺丝刀"]
HOME_KW = ["指甲刀", "磨甲器", "抽水器", "饮水机", "理发器", "电推剪", "剃头", "绞肉机",
           "打蒜器", "奶泡", "料理机", "鼻毛", "捣碎器", "打蛋器"]

def is_power_tool(p):
    name = p["name"].lower()
    shop = p["shop"].lower()
    for kw in TOOL_KW:
        if kw in name or kw in shop:
            return True
    for kw in HOME_KW:
        if kw in name:
            return False
    return False

power_tools = [p for p in products if is_power_tool(p)]

# 品牌筛选区数据
brand_filter = ["东成", "欧莱德", "德力西电气（DELIXI ELECTRIC）", "大有（Devon）", "绿林（GREENER）", "博世（BOSCH）"]

# 统计
brand_counter = Counter(p["brand"] for p in power_tools if p["brand"])
shop_counter = Counter(p["shop"] for p in products if p["shop"])
prices = [p["price"] for p in power_tools if p["price"] > 0]

print(f"=" * 70)
print(f"  京东电动工具电商数据采集报告")
print(f"  采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"=" * 70)
print(f"\n  搜索关键词: 电动工具 (按销量排序)")
print(f"  总商品数: {len(products)}")
print(f"  电动工具商品: {len(power_tools)}")
print(f"  总页数: 100 (当前第1页)")

print(f"\n{'─' * 50}")
print(f"  品牌筛选 (搜索页)")
print(f"{'─' * 50}")
for b in brand_filter:
    print(f"    {b}")

print(f"\n{'─' * 50}")
print(f"  电动工具商品详情")
print(f"{'─' * 50}")
for idx, p in enumerate(power_tools, 1):
    print(f"\n  {idx}. [{p['brand'] or '其他'}] {p['name'][:60]}")
    print(f"     价格: ¥{p['price']:.2f}")
    print(f"     店铺: {p['shop']}")
    print(f"     评价: {p['reviews']}")

print(f"\n{'─' * 50}")
print(f"  品牌分布 (电动工具)")
print(f"{'─' * 50}")
for brand, count in brand_counter.most_common():
    print(f"    {brand}: {count} 件")

print(f"\n{'─' * 50}")
print(f"  价格统计 (电动工具)")
print(f"{'─' * 50}")
if prices:
    print(f"    最低价: ¥{min(prices):.2f}")
    print(f"    最高价: ¥{max(prices):.2f}")
    print(f"    平均价: ¥{sum(prices)/len(prices):.2f}")
    print(f"    价格区间分布:")
    ranges = [(0, 50), (50, 100), (100, 200), (200, 500), (500, 99999)]
    for lo, hi in ranges:
        cnt = sum(1 for p in prices if lo <= p < hi)
        label = f"¥{lo}-{hi}" if hi < 99999 else f"¥{lo}+"
        bar = "█" * cnt
        print(f"      {label:>12}: {cnt} 件 {bar}")

print(f"\n{'─' * 50}")
print(f"  店铺排名 (按出现次数)")
print(f"{'─' * 50}")
for shop, count in shop_counter.most_common(10):
    print(f"    {shop}: {count} 件")

# 保存
output = {
    "collected_at": datetime.now().isoformat(),
    "keyword": "电动工具",
    "sort": "销量",
    "page": 1,
    "total_pages": 100,
    "total_products": len(products),
    "power_tools_count": len(power_tools),
    "brand_filter": brand_filter,
    "brands": dict(brand_counter.most_common()),
    "shops": dict(shop_counter.most_common(15)),
    "price_stats": {
        "min": min(prices) if prices else 0,
        "max": max(prices) if prices else 0,
        "avg": round(sum(prices)/len(prices), 2) if prices else 0,
        "count": len(prices),
    },
    "power_tools": power_tools,
    "all_products": products,
}

out_path = Path(__file__).parent / "data" / f"power_tools_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n{'=' * 70}")
print(f"  数据已保存: {out_path}")
print(f"{'=' * 70}")
