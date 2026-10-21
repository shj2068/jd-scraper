#!/usr/bin/env python3
"""从浏览器快照解析京东电动工具搜索数据"""
import re, json, sys, io
from pathlib import Path
from datetime import datetime
from collections import Counter

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

SNAPSHOT = Path(r"C:\Users\jie20\.qoder-cn\tmp\d--tongyi\1b7f4d3f-6acb-4c2a-89e5-eb6422276c5f\tool-results\browser-use_take_snapshot_c57c610dfa00.txt")

text = SNAPSHOT.read_text(encoding="utf-8")

# 提取品牌筛选区
brands_filter = re.findall(r'uid=4_\d+ StaticText "([^"]+)"', text)
brand_candidates = ["东成", "欧莱德", "德力西电气", "大有", "绿林", "博世", "得力", "飞科", "苏泊尔", "小熊", "志高", "康佳", "荣事达", "双枪", "奥克斯", "京造", "Seemagic", "拜杰", "LOROLI"]

# 提取所有 StaticText 内容
all_texts = re.findall(r'uid=\d+_\d+ StaticText "([^"]*)"', text)

# 提取商品数据 - 按结构解析
# 每个商品块: 名称(多个StaticText拼接) → 价格(¥数字.数字) → 评价 → 店铺
products = []
i = 0
while i < len(all_texts):
    t = all_texts[i]
    # 检测价格模式: "¥" 后跟数字
    if t == "¥" and i + 3 < len(all_texts):
        # 向后找店铺名和评价
        price_str = ""
        j = i + 1
        while j < len(all_texts) and j < i + 5:
            price_str += all_texts[j]
            j += 1
        try:
            price = float(price_str)
        except:
            price = 0

        # 向前找商品名称(从当前¥位置往前找到上一个商品结束或开头)
        name_parts = []
        k = i - 1
        while k >= 0:
            prev = all_texts[k]
            if prev in ["¥", "到手价", "补贴到手价", "政府补贴价", "新人价"] or re.match(r'^\d+\.\d+$', prev):
                break
            if prev and prev not in ["|", "自营"] and len(prev) > 1:
                name_parts.insert(0, prev)
            k -= 1
        name = "".join(name_parts).strip()

        # 向后找店铺名和评价数
        shop = ""
        reviews = ""
        sales = ""
        for m in range(i + 1, min(i + 30, len(all_texts))):
            mt = all_texts[m]
            if "条评价" in mt:
                reviews = mt
            elif "已售" in mt or "加购" in mt:
                sales = mt
            elif "旗舰店" in mt or "自营店" in mt or "专卖店" in mt or "官方店" in mt:
                shop = mt
                break
            elif mt == "¥" and m > i + 4:
                break

        if name and len(name) > 3:
            # 识别品牌
            brand = ""
            for b in brand_candidates:
                if b in name or b in shop:
                    brand = b
                    break

            products.append({
                "name": name[:80],
                "price": price,
                "shop": shop,
                "reviews": reviews,
                "sales": sales,
                "brand": brand,
            })
    i += 1

# 去重(同一商品可能出现两次价格)
seen = set()
unique = []
for p in products:
    key = (p["name"][:30], p["price"])
    if key not in seen:
        seen.add(key)
        unique.append(p)
products = unique

# 过滤真正的电动工具(排除指甲刀、抽水器、理发器、绞肉机等家用品)
TOOL_KEYWORDS = ["电钻", "角磨机", "螺丝刀", "电起子", "扳手", "切割机", "磨光机", "电刨", "电锯", "砂轮机", "冲击钻", "电锤", "工具"]
HOME_APPLIANCE = ["指甲刀", "磨甲器", "抽水器", "饮水机", "理发器", "电推剪", "剃头", "绞肉机", "打蒜器", "奶泡", "料理机", "鼻毛"]

def is_power_tool(p):
    name = p["name"]
    shop = p["shop"]
    for kw in TOOL_KEYWORDS:
        if kw in name or kw in shop:
            return True
    for kw in HOME_APPLIANCE:
        if kw in name:
            return False
    return "电动工具" in shop or "工具" in shop

power_tools = [p for p in products if is_power_tool(p)]
all_filtered = power_tools if power_tools else products

# 统计
brand_counter = Counter(p["brand"] for p in all_filtered if p["brand"])
shop_counter = Counter(p["shop"] for p in all_filtered if p["shop"])
prices = [p["price"] for p in all_filtered if p["price"] > 0]

print(f"总商品数: {len(products)}")
print(f"电动工具商品: {len(power_tools)}")
print(f"最终统计商品: {len(all_filtered)}")
print(f"\n品牌分布: {dict(brand_counter.most_common(15))}")
print(f"店铺分布: {dict(shop_counter.most_common(15))}")
print(f"价格范围: {min(prices) if prices else 0:.2f} - {max(prices) if prices else 0:.2f}")
print(f"平均价格: {sum(prices)/len(prices) if prices else 0:.2f}")

# 保存结果
output = {
    "collected_at": datetime.now().isoformat(),
    "keyword": "电动工具",
    "total_products": len(products),
    "power_tools_count": len(power_tools),
    "brands": dict(brand_counter.most_common()),
    "shops": dict(shop_counter.most_common()),
    "price_stats": {
        "min": min(prices) if prices else 0,
        "max": max(prices) if prices else 0,
        "avg": round(sum(prices)/len(prices), 2) if prices else 0,
        "count": len(prices),
    },
    "products": all_filtered,
}

out_path = Path(__file__).parent / "data" / f"power_tools_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n数据已保存: {out_path}")

# 打印前20个商品
print("\n前20个商品:")
for idx, p in enumerate(all_filtered[:20], 1):
    print(f"  {idx}. [{p['brand'] or '?'}] {p['name'][:50]}")
    print(f"     ¥{p['price']:.2f} | {p['shop']} | {p['reviews']}")
