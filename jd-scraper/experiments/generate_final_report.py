#!/usr/bin/env python3
"""生成京东电动工具电商数据分析报告"""
import json, sys, io
from pathlib import Path
from datetime import datetime
from collections import Counter

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# 从浏览器提取的原始数据
raw_data = [
    {"sku":"10156925961082","title":"新款电动指甲刀宝宝磨甲器家用全自动修甲快充儿童磨甲器升级","price":"1.77","shop":"京喜自营官方店","review":"100万+条评价","approval":"87%好评"},
    {"sku":"10164211439046","title":"【钜惠让利】充电式电动螺丝刀家用充电小型螺丝批锂电电钻工具 简单配置3件套装","price":"7.67","shop":"京喜自营官方店","review":"50万+条评价","approval":"91%好评"},
    {"sku":"100141612619","title":"志高（CHIGO）抽水器桶装水 电动抽水泵饮水机纯净水取水器自动上水器MX-H17","price":"17.82","shop":"志高（CHIGO）厨具京东自营旗舰店","review":"100万+条评价","approval":"96%好评"},
    {"sku":"100005134556","title":"飞科（FLYCO）【价保双11】电动理发器FC5908成人儿童电推剪家用剃头刀自理发神器理发工具","price":"106.78","shop":"飞科京东自营旗舰店","review":"200万+条评价","approval":"99%好评"},
    {"sku":"100254936646","title":"苏泊尔（SUPOR）上水器桶装水自动抽水器抗菌吸水器电动矿泉水压水器饮水机抽水泵","price":"38.88","shop":"苏泊尔京东自营旗舰店","review":"10万+条评价","approval":"98%好评"},
    {"sku":"100179217061","title":"小熊（Bear）桶装水抽水器饮水机取水器电动上水器压水器自动抽水泵YSJ-F06Q1","price":"51.68","shop":"小熊京东自营旗舰店","review":"100万+条评价","approval":"97%好评"},
    {"sku":"100251723038","title":"荣事达（Royalstar）桶装水抽水神器自动饮水机取水器矿泉水压水器电动抽水泵","price":"17.68","shop":"荣事达小工具京东自营旗舰店","review":"20万+条评价","approval":"98%好评"},
    {"sku":"100089230368","title":"双枪抽水器桶装水神器99.9%抗菌静音矿泉水电动抽水泵折叠自动上水器","price":"14.79","shop":"双枪京东自营旗舰店","review":"50万+条评价","approval":"97%好评"},
    {"sku":"100344870000","title":"苏泊尔（SUPOR）绞肉机家用小型多功能打泥搅拌婴儿宝宝便携辅食料理机蒜泥捣碎器","price":"54.35","shop":"苏泊尔京东自营旗舰店","review":"50万+条评价","approval":"99%好评"},
    {"sku":"100324817054","title":"京东京造 抽水器桶装水 316不锈钢电动自动抽水泵饮水机吸水上水器大水量","price":"33.4","shop":"京东京造自营旗舰店","review":"2万+条评价","approval":"98%好评"},
    {"sku":"100021400901","title":"康佳（KONKA）电动理发器 理发电推子 家用成人儿童剃头理发器理发神器自己剪剪 剃发器工具套装","price":"49.89","shop":"康佳（KONKA）个护京东自营旗舰店","review":"20万+条评价","approval":"98%好评"},
    {"sku":"100066038179","title":"Seemagic醒刻电动指甲刀pro全自动指甲刀成人指甲剪打磨器老人剪指甲安全防夹肉磨甲器","price":"81.88","shop":"Seemagic京东自营旗舰店","review":"10万+条评价","approval":"96%好评"},
    {"sku":"100281192978","title":"拜杰抽水器桶装水神器自动抽水泵电动吸水器取水器饮水机上水器","price":"6.99","shop":"拜杰京东自营旗舰店","review":"10万+条评价","approval":"94%好评"},
    {"sku":"100138579333","title":"京东京造 抽水器桶装水 抽水神器电动抽水机饮水机自动抽水器（双泵折叠）","price":"44.91","shop":"京东京造自营旗舰店","review":"10万+条评价","approval":"97%好评"},
    {"sku":"100229733995","title":"荣事达（Royalstar）电动打奶泡器 咖啡奶泡机 家用牛奶打泡器 手持迷你搅拌打蛋器","price":"9.39","shop":"荣事达小工具京东自营旗舰店","review":"5万+条评价","approval":"99%好评"},
    {"sku":"100219342806","title":"京东京造电动理发器T3专业级成人儿童智能理发电推剪理发工具电推子家用剃头刀","price":"74.52","shop":"京东京造自营旗舰店","review":"10万+条评价","approval":"99%好评"},
    {"sku":"100052005395","title":"苏泊尔SUPOR 桶装水电动抽水器自动取水器饮水机上水器 KGE14AB10","price":"35.91","shop":"苏泊尔京东自营旗舰店","review":"50万+条评价","approval":"94%好评"},
    {"sku":"10218487756817","title":"LOROLI电动鼻毛修剪器男士专用女士无痛耳鼻毛可水洗旅行便携充电款","price":"80.78","shop":"LOROLI个护旗舰店","review":"1万+条评价","approval":"99%好评"},
    {"sku":"100073568421","title":"欧莱德无刷电钻手电钻电动螺丝刀充电式双速锂电钻家用手钻工具箱套装","price":"118.62","shop":"欧莱德（OULAIDE）京东自营旗舰店","review":"10万+条评价","approval":"99%好评"},
    {"sku":"10216713826891","title":"苏泊尔（SUPOR）电动蒜泥打蒜器小型绞肉机家用料理机婴儿宝宝辅食搅拌机捣蒜神器","price":"52.13","shop":"苏泊尔旗舰店","review":"2万+条评价","approval":"99%好评"},
    {"sku":"100070266967","title":"得力（deli）电动螺丝刀充电式家用小型手电钻迷你电动螺丝批起子机25批头套装","price":"82.38","shop":"得力工具京东自营旗舰店","review":"10万+条评价","approval":"99%好评"},
    {"sku":"49415960015","title":"奥克斯（AUX）剃头理发器电推子成人电推剪婴儿电动剪发器家用儿童剃头刀剪头发推子剪刀理发工具套装","price":"56.68","shop":"奥克斯个护电器旗舰店","review":"100万+条评价","approval":"98%好评"},
    {"sku":"100262714424","title":"小熊（Bear）桶装水抽水器 电动吸水器自动上水器矿泉水压水器抽水泵YSJ-H06D1","price":"35.87","shop":"小熊京东自营旗舰店","review":"5万+条评价","approval":"98%好评"},
    {"sku":"10113500399731","title":"奥克斯抽水器桶装水电动压水器自动吸水器矿泉水饮水机大桶抽水泵取水器","price":"34.48","shop":"奥克斯小杏梅专卖店","review":"10万+条评价","approval":"98%好评"},
    {"sku":"100363203330","title":"双枪（Suncha）抽水器桶装水 抽水神器电动大水量抽水机饮水机自动抽水器 双泵","price":"21.68","shop":"双枪京东自营旗舰店","review":"10万+条评价","approval":"98%好评"},
    {"sku":"100378521732","title":"志高（CHIGO）电动奶泡打发器咖啡打泡器牛奶搅拌棒家用小型迷你打蛋器","price":"12.85","shop":"志高（CHIGO）厨具京东自营旗舰店","review":"1万+条评价","approval":"98%好评"},
    {"sku":"100004849092","title":"东成角磨机WSM710-100手磨机磨光机打磨机切割机电动工具","price":"134.18","shop":"东成电动工具京东自营旗舰店","review":"20万+条评价","approval":"98%好评"},
    {"sku":"100115021838","title":"得力12V手电钻电动螺丝刀锂电钻多功能家用充电式起子机电动工具套装","price":"103.42","shop":"得力工具京东自营旗舰店","review":"10万+条评价","approval":"98%好评"},
    {"sku":"69924210093","title":"飞科（FLYCO）理发器电动成人儿童剃头电推子全身水洗家用剃头剪刀理发工具套装","price":"122.88","shop":"飞科官方旗舰店","review":"20万+条评价","approval":"98%好评"},
    {"sku":"100237641153","title":"炊大皇电动打蒜器小型绞肉机捣蒜器6叶刀片玻璃杯蒜泥神器辅食搅碎","price":"38.16","shop":"炊大皇京东自营旗舰店","review":"2万+条评价","approval":"93%好评"},
]

# 识别品牌
BRANDS = {
    "东成": ["东成"],
    "欧莱德": ["欧莱德"],
    "得力": ["得力", "deli"],
    "博世": ["博世", "BOSCH"],
    "德力西": ["德力西"],
    "大有": ["大有", "Devon"],
    "绿林": ["绿林", "GREENER"],
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
}

def detect_brand(title, shop):
    for brand, keywords in BRANDS.items():
        for kw in keywords:
            if kw in title or kw in shop:
                return brand
    return "其他"

# 分类商品
TOOL_KW = ["电钻", "角磨机", "螺丝刀", "电起子", "扳手", "切割机", "磨光机", "电刨", "电锯",
           "砂轮机", "冲击钻", "电锤", "电动工具", "手电钻", "起子机", "电螺丝刀", "工具箱"]
HOME_KW = ["指甲刀", "磨甲器", "抽水器", "饮水机", "理发器", "电推剪", "剃头", "绞肉机",
           "打蒜器", "奶泡", "料理机", "鼻毛", "捣碎器", "打蛋器", "取水器"]

def classify_product(p):
    title = p["title"]
    shop = p["shop"]
    for kw in TOOL_KW:
        if kw in title or kw in shop:
            return "power_tool"
    for kw in HOME_KW:
        if kw in title:
            return "home_appliance"
    return "other"

# 处理数据
products = []
for item in raw_data:
    price = float(item["price"]) if item["price"] else 0
    brand = detect_brand(item["title"], item["shop"])
    category = classify_product(item)
    products.append({
        **item,
        "price": price,
        "brand": brand,
        "category": category,
    })

power_tools = [p for p in products if p["category"] == "power_tool"]
home_appliances = [p for p in products if p["category"] == "home_appliance"]

# 统计
all_brand_counter = Counter(p["brand"] for p in products)
tool_brand_counter = Counter(p["brand"] for p in power_tools)
all_shop_counter = Counter(p["shop"] for p in products)
tool_shop_counter = Counter(p["shop"] for p in power_tools)
all_prices = [p["price"] for p in products if p["price"] > 0]
tool_prices = [p["price"] for p in power_tools if p["price"] > 0]

# 生成报告
report = {
    "report_title": "京东电动工具电商数据采集报告",
    "collected_at": datetime.now().isoformat(),
    "keyword": "电动工具",
    "sort_by": "销量",
    "page": 1,
    "total_pages": 100,
    "summary": {
        "total_products": len(products),
        "power_tools_count": len(power_tools),
        "home_appliances_count": len(home_appliances),
        "unique_brands": len(set(p["brand"] for p in products)),
        "unique_shops": len(all_shop_counter),
    },
    "power_tools": power_tools,
    "brand_distribution": {
        "all_products": dict(all_brand_counter.most_common()),
        "power_tools_only": dict(tool_brand_counter.most_common()),
    },
    "shop_ranking": {
        "all_products": dict(all_shop_counter.most_common(15)),
        "power_tools_only": dict(tool_shop_counter.most_common(10)),
    },
    "price_analysis": {
        "all_products": {
            "min": min(all_prices) if all_prices else 0,
            "max": max(all_prices) if all_prices else 0,
            "avg": round(sum(all_prices)/len(all_prices), 2) if all_prices else 0,
        },
        "power_tools": {
            "min": min(tool_prices) if tool_prices else 0,
            "max": max(tool_prices) if tool_prices else 0,
            "avg": round(sum(tool_prices)/len(tool_prices), 2) if tool_prices else 0,
        },
    },
}

# 保存 JSON
out_path = Path(__file__).parent / "data" / f"jd_power_tools_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

# 打印报告
print("=" * 70)
print("  京东电动工具电商数据采集报告")
print(f"  采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)
print(f"\n  搜索关键词: {report['keyword']}")
print(f"  排序方式: {report['sort_by']}")
print(f"  采集页数: 第 {report['page']} 页 / 共 {report['total_pages']} 页")

print(f"\n{'─' * 70}")
print(f"  数据概览")
print(f"{'─' * 70}")
s = report["summary"]
print(f"  总商品数: {s['total_products']} 件")
print(f"  电动工具: {s['power_tools_count']} 件")
print(f"  家用电器: {s['home_appliances_count']} 件")
print(f"  品牌数量: {s['unique_brands']} 个")
print(f"  店铺数量: {s['unique_shops']} 家")

print(f"\n{'─' * 70}")
print(f"  电动工具商品详情 (按销量排序)")
print(f"{'─' * 70}")
for idx, p in enumerate(power_tools, 1):
    print(f"\n  {idx}. [{p['brand']}] {p['title'][:60]}")
    print(f"     SKU: {p['sku']}")
    print(f"     价格: ¥{p['price']:.2f}")
    print(f"     店铺: {p['shop']}")
    print(f"     评价: {p['review']} | {p['approval']}")

print(f"\n{'─' * 70}")
print(f"  品牌分布 (全部商品)")
print(f"{'─' * 70}")
for brand, count in all_brand_counter.most_common(15):
    pct = count / len(products) * 100
    bar = "█" * count
    print(f"    {brand:12s}: {count:2d} 件 ({pct:4.1f}%) {bar}")

print(f"\n{'─' * 70}")
print(f"  品牌分布 (电动工具)")
print(f"{'─' * 70}")
for brand, count in tool_brand_counter.most_common():
    print(f"    {brand}: {count} 件")

print(f"\n{'─' * 70}")
print(f"  价格分析")
print(f"{'─' * 70}")
pa = report["price_analysis"]
print(f"\n  全部商品:")
print(f"    最低价: ¥{pa['all_products']['min']:.2f}")
print(f"    最高价: ¥{pa['all_products']['max']:.2f}")
print(f"    平均价: ¥{pa['all_products']['avg']:.2f}")
print(f"\n  电动工具:")
if tool_prices:
    print(f"    最低价: ¥{pa['power_tools']['min']:.2f}")
    print(f"    最高价: ¥{pa['power_tools']['max']:.2f}")
    print(f"    平均价: ¥{pa['power_tools']['avg']:.2f}")
    print(f"\n  价格区间分布 (电动工具):")
    ranges = [(0, 50), (50, 100), (100, 200), (200, 500), (500, 99999)]
    for lo, hi in ranges:
        cnt = sum(1 for p in tool_prices if lo <= p < hi)
        label = f"¥{lo}-{hi}" if hi < 99999 else f"¥{lo}+"
        bar = "█" * cnt
        print(f"    {label:>12s}: {cnt} 件 {bar}")

print(f"\n{'─' * 70}")
print(f"  店铺排名 TOP 10 (全部商品)")
print(f"{'─' * 70}")
for idx, (shop, count) in enumerate(all_shop_counter.most_common(10), 1):
    print(f"    {idx:2d}. {shop}: {count} 件")

print(f"\n{'─' * 70}")
print(f"  店铺排名 (电动工具)")
print(f"{'─' * 70}")
for idx, (shop, count) in enumerate(tool_shop_counter.most_common(), 1):
    print(f"    {idx}. {shop}: {count} 件")

print(f"\n{'─' * 70}")
print(f"  品牌筛选区 (搜索页)")
print(f"{'─' * 70}")
brand_filter = ["东成", "欧莱德", "德力西电气（DELIXI ELECTRIC）", "大有（Devon）", "绿林（GREENER）", "博世（BOSCH）"]
for b in brand_filter:
    print(f"    {b}")

print(f"\n{'=' * 70}")
print(f"  报告已保存: {out_path}")
print(f"{'=' * 70}")
