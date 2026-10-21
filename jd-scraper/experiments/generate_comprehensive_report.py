#!/usr/bin/env python3
"""生成京东电动工具电商数据综合报告 - 合并电钻+电动工具搜索结果"""
import json, sys, io, re
from pathlib import Path
from datetime import datetime
from collections import Counter

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# ── 电钻搜索结果 (60件, 前30件有详情) ──
drill_data = [
    {"sku":"10225569868767","title":"新款16V无刷锂电电钻充电式电动螺丝批钻家用多功能","price":"394.78","shop":""},
    {"sku":"100115021838","title":"得力12V锂电钻套装","price":"103.42","shop":"得力工具京东自营旗舰店"},
    {"sku":"100241702002","title":"德力西电气手电钻锂电充电式家用小型冲击手枪钻转多功能电动螺丝刀12V冲击","price":"138.99","shop":"德力西电气电动工具京东自营旗舰店"},
    {"sku":"100231301118","title":"班帝森21V手电钻大功率锂电池家用电钻电动螺丝刀手枪钻电起子电动工具","price":"170","shop":"班帝森京东自营旗舰店"},
    {"sku":"100002159649","title":"德力西电气710W冲击钻","price":"142.68","shop":"德力西电气工具京东自营旗舰店"},
    {"sku":"100348690262","title":"优力特手电钻多功能家用大功率手枪钻打墙打孔电动工具冲击钻手持瓷砖","price":"65.67","shop":"优力特电动工具京东自营旗舰店"},
    {"sku":"10215559227140","title":"SRM上海人民多功能3000W大功率正品手电钻有线手枪钻冲击钻多功能转","price":"119","shop":""},
    {"sku":"100045351812","title":"博世GBM 400 KLE 手电钻","price":"150.43","shop":"博世电动工具京东自营旗舰店"},
    {"sku":"100010507886","title":"东成手电钻WJZ400-10多功能家用电钻电动螺丝刀电动工具","price":"121.77","shop":"东成电动工具京东自营旗舰店"},
    {"sku":"100244528329","title":"东成 手电钻家用多功能打孔","price":"109.45","shop":"东成电动工具京东自营旗舰店"},
    {"sku":"100222192774","title":"班帝森手电钻家用充电电钻电动螺丝刀锂电池手枪钻电动起子电动工具","price":"135.85","shop":"班帝森京东自营旗舰店"},
    {"sku":"100091442550","title":"东成20V无刷手电钻","price":"227.46","shop":"东成电动工具京东自营旗舰店"},
    {"sku":"100299592238","title":"博世（BOSCH）手电钻16V锂电电动螺丝刀55牛米大扭矩起拧家用SR160两电一充","price":"366.78","shop":"博世电动工具京东自营旗舰店"},
    {"sku":"10128640268618","title":"德力西家用电钻手电钻电动螺丝刀起子机交流电220v多功能打孔电动工具","price":"106.68","shop":"德力西海若专卖店"},
    {"sku":"10083287054861","title":"爱瑞德手电钻家用充电电钻电动螺丝刀锂电起子螺丝批电转 电动工具","price":"66.58","shop":"爱瑞德电动工具旗舰店"},
    {"sku":"10170524598882","title":"【德国品质】手电钻冲击钻家用手枪钻锂电多功能充电式电动螺丝刀","price":"60.66","shop":"京喜自营官方店"},
    {"sku":"10192224086516","title":"东成 锂电钻电动螺丝刀充电式手电钻多功能手枪钻家用套装电动工具 DCJZ1208B","price":"123.62","shop":"东成电动工具旗舰店"},
    {"sku":"100009838731","title":"东成锂电钻WJZ1601D手电钻充电式电动螺丝刀起子机家用16V多功能套装","price":"172.9","shop":"东成电动工具京东自营旗舰店"},
    {"sku":"10121940382153","title":"爱瑞德充电电钻家用手电钻锂电池电动螺丝刀电起子螺丝批电转 电动工具","price":"77.58","shop":"爱瑞德工具旗舰店"},
    {"sku":"100142121728","title":"德力西电气手电钻锂电钻电动螺丝刀家用充电式手钻电起子电批电动工具箱套装","price":"96.78","shop":"德力西电气电动工具京东自营旗舰店"},
    {"sku":"57214157538","title":"东成 锂电钻电动螺丝刀充电式手电钻多功能手枪钻家用套装电动工具 MJZ1201D","price":"157.06","shop":"东成电动工具旗舰店"},
    {"sku":"100009007521","title":"东成锂电钻WJZ1601S手电钻充电式电动螺丝刀起子机家用16V双电套装","price":"257.38","shop":"东成电动工具京东自营旗舰店"},
    {"sku":"100195409716","title":"欧莱德充电电钻电动螺丝刀充电式双速锂电钻家用手钻电动工具手电钻","price":"56.68","shop":"欧莱德（OULAIDE）京东自营旗舰店"},
    {"sku":"100088388261","title":"博世（BOSCH）冲击钻手电钻家装维修瓷砖木材金属砖墙钻孔600瓦插电式GSB 600","price":"258.33","shop":"博世电动工具京东自营旗舰店"},
    {"sku":"100292363619","title":"大功率打孔手电钻冲击款","price":"91.08","shop":""},
    {"sku":"100095867991","title":"大功率家用冲击钻","price":"132.78","shop":""},
    {"sku":"100110109721","title":"亚特 手电钻工具箱家用无级变速","price":"77.98","shop":"亚特（YAT）京东自营旗舰店"},
    {"sku":"100398938994","title":"博世（BOSCH）400瓦高功率电钻金属瓷砖木材钻孔带自锁夹头便携家用BM380","price":"147.18","shop":"博世电动工具京东自营旗舰店"},
    {"sku":"10151653694623","title":"星固手电钻家用电钻电动螺丝刀","price":"53.23","shop":"京喜自营官方店"},
    {"sku":"100335483876","title":"光宸手电钻电动螺丝刀钻墙打孔锂电冲击钻手枪钻工具箱全套家用五金","price":"296.78","shop":"光宸京东自营旗舰店"},
]

# ── 电动工具搜索结果 (电动工具类) ──
tool_data = [
    {"sku":"10164211439046","title":"充电式电动螺丝刀家用充电小型螺丝批锂电电钻工具 简单配置3件套装","price":"7.67","shop":"京喜自营官方店","review":"50万+条评价","approval":"91%好评"},
    {"sku":"100073568421","title":"欧莱德无刷电钻手电钻电动螺丝刀充电式双速锂电钻家用手钻工具箱套装","price":"118.62","shop":"欧莱德（OULAIDE）京东自营旗舰店","review":"10万+条评价","approval":"99%好评"},
    {"sku":"100070266967","title":"得力（deli）电动螺丝刀充电式家用小型手电钻迷你电动螺丝批起子机25批头套装","price":"82.38","shop":"得力工具京东自营旗舰店","review":"10万+条评价","approval":"99%好评"},
    {"sku":"100004849092","title":"东成角磨机WSM710-100手磨机磨光机打磨机切割机电动工具","price":"134.18","shop":"东成电动工具京东自营旗舰店","review":"20万+条评价","approval":"98%好评"},
    {"sku":"100115021838","title":"得力12V手电钻电动螺丝刀锂电钻多功能家用充电式起子机电动工具套装","price":"103.42","shop":"得力工具京东自营旗舰店","review":"10万+条评价","approval":"98%好评"},
]

# ── 品牌检测 ──
BRAND_MAP = {
    "东成": ["东成"],
    "欧莱德": ["欧莱德", "OULAIDE"],
    "得力": ["得力", "deli"],
    "博世": ["博世", "BOSCH"],
    "德力西电气": ["德力西", "DELIXI"],
    "大有": ["大有", "Devon"],
    "绿林": ["绿林", "GREENER"],
    "班帝森": ["班帝森"],
    "优力特": ["优力特"],
    "爱瑞德": ["爱瑞德"],
    "亚特": ["亚特", "YAT"],
    "光宸": ["光宸"],
    "星固": ["星固"],
    "飞科": ["飞科", "FLYCO"],
    "苏泊尔": ["苏泊尔", "SUPOR"],
    "小熊": ["小熊", "Bear"],
    "志高": ["志高", "CHIGO"],
    "康佳": ["康佳", "KONKA"],
    "荣事达": ["荣事达", "Royalstar"],
    "双枪": ["双枪", "Suncha"],
    "奥克斯": ["奥克斯", "AUX"],
    "京造": ["京东京造"],
    "Seemagic": ["Seemagic", "醒刻"],
    "拜杰": ["拜杰"],
    "LOROLI": ["LOROLI"],
    "炊大皇": ["炊大皇"],
    "上海人民": ["上海人民", "SRM"],
}

def detect_brand(title, shop=""):
    combined = title + " " + shop
    for brand, keywords in BRAND_MAP.items():
        for kw in keywords:
            if kw in combined:
                return brand
    return "其他"

# ── 合并去重 ──
all_products = {}
for item in drill_data + tool_data:
    sku = item["sku"]
    if sku not in all_products:
        price = float(item["price"]) if item["price"] else 0
        brand = detect_brand(item["title"], item.get("shop", ""))
        all_products[sku] = {
            "sku": sku,
            "title": item["title"],
            "price": price,
            "shop": item.get("shop", ""),
            "brand": brand,
            "review": item.get("review", ""),
            "approval": item.get("approval", ""),
        }

products = list(all_products.values())

# ── 统计分析 ──
brand_counter = Counter(p["brand"] for p in products)
shop_counter = Counter(p["shop"] for p in products if p["shop"])
prices = [p["price"] for p in products if p["price"] > 0]

# 按品牌汇总价格
brand_prices = {}
for p in products:
    b = p["brand"]
    if b not in brand_prices:
        brand_prices[b] = []
    if p["price"] > 0:
        brand_prices[b].append(p["price"])

# 店铺排名 (按商品数)
shop_ranking = shop_counter.most_common(10)

# ── 生成报告 ──
report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

print("=" * 70)
print(f"  京东电动工具电商数据采集报告")
print(f"  采集时间: {report_time}")
print(f"  数据来源: search.jd.com (浏览器登录后采集)")
print("=" * 70)

print(f"\n{'━' * 70}")
print(f"  一、数据概览")
print(f"{'━' * 70}")
print(f"  搜索关键词: \"电钻\" + \"电动工具\"")
print(f"  排序方式: 销量优先")
print(f"  采集商品: {len(products)} 件 (去重后)")
print(f"  涉及品牌: {len(brand_counter)} 个")
print(f"  涉及店铺: {len(shop_counter)} 家")
print(f"  价格范围: ¥{min(prices):.2f} ~ ¥{max(prices):.2f}")
print(f"  平均价格: ¥{sum(prices)/len(prices):.2f}")

print(f"\n{'━' * 70}")
print(f"  二、品牌分布 (按商品数量)")
print(f"{'━' * 70}")
for brand, count in brand_counter.most_common(20):
    pct = count / len(products) * 100
    bp = brand_prices.get(brand, [])
    avg_p = f"¥{sum(bp)/len(bp):.0f}" if bp else "N/A"
    bar = "█" * count
    print(f"  {brand:12s} │ {count:2d} 件 ({pct:4.1f}%) │ 均价 {avg_p:>8s} │ {bar}")

print(f"\n{'━' * 70}")
print(f"  三、电动工具品牌 TOP 10 (搜索页筛选区)")
print(f"{'━' * 70}")
jd_brands = ["东成", "欧莱德", "德力西电气（DELIXI ELECTRIC）", "大有（Devon）", "绿林（GREENER）", "博世（BOSCH）"]
for i, b in enumerate(jd_brands, 1):
    print(f"  {i}. {b}")

print(f"\n{'━' * 70}")
print(f"  四、店铺排名 TOP 10 (按商品数量)")
print(f"{'━' * 70}")
for i, (shop, count) in enumerate(shop_ranking, 1):
    # 计算该店铺的平均价格
    shop_prices = [p["price"] for p in products if p["shop"] == shop and p["price"] > 0]
    avg = f"¥{sum(shop_prices)/len(shop_prices):.0f}" if shop_prices else ""
    print(f"  {i:2d}. {shop}")
    print(f"      商品数: {count} 件  {f'均价: {avg}' if avg else ''}")

print(f"\n{'━' * 70}")
print(f"  五、价格区间分布")
print(f"{'━' * 70}")
ranges = [(0, 50), (50, 100), (100, 150), (150, 200), (200, 300), (300, 500)]
for lo, hi in ranges:
    cnt = sum(1 for p in prices if lo <= p < hi)
    pct = cnt / len(prices) * 100 if prices else 0
    bar = "█" * cnt
    print(f"  ¥{lo:>3d}-{hi:<3d} │ {cnt:2d} 件 ({pct:4.1f}%) │ {bar}")

print(f"\n{'━' * 70}")
print(f"  六、全部商品明细 (按价格排序)")
print(f"{'━' * 70}")
sorted_products = sorted(products, key=lambda x: x["price"])
for idx, p in enumerate(sorted_products, 1):
    review_str = f" | {p['review']}" if p["review"] else ""
    print(f"  {idx:2d}. [{p['brand']:6s}] ¥{p['price']:>8.2f} | {p['title'][:45]}")
    if p["shop"]:
        print(f"      店铺: {p['shop']}{review_str}")

# ── 保存 JSON ──
output = {
    "report_title": "京东电动工具电商数据采集报告",
    "collected_at": report_time,
    "source": "search.jd.com (浏览器登录后采集)",
    "keywords": ["电钻", "电动工具"],
    "summary": {
        "total_products": len(products),
        "unique_brands": len(brand_counter),
        "unique_shops": len(shop_counter),
        "price_range": {"min": min(prices), "max": max(prices), "avg": round(sum(prices)/len(prices), 2)},
    },
    "brand_distribution": dict(brand_counter.most_common()),
    "shop_ranking": [{"shop": s, "count": c} for s, c in shop_ranking],
    "products": sorted_products,
}

out_path = Path(__file__).parent / "data" / f"jd_power_tools_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n{'=' * 70}")
print(f"  数据已保存: {out_path}")
print(f"{'=' * 70}")
