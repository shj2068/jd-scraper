#!/usr/bin/env python3
"""
京东电动工具电商数据采集报告生成器
基于公开 API 可用数据 + 采集架构说明
仅用于技术学习与研究
"""

import json
import sys
import io
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_category_data() -> dict:
    """加载已有的分类品牌数据"""
    existing = DATA_DIR / "jd_categories_20261014_062146.json"
    if existing.exists():
        with open(existing, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def generate_report():
    """生成电动工具数据采集报告"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print(f"  京东电动工具电商数据采集报告")
    print(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 加载已有数据
    cat_data = load_category_data()
    summary = cat_data.get("summary", {})

    print(f"\n[数据来源]")
    print(f"  主数据源: dc.3.cn/category/get (京东分类 API)")
    print(f"  采集时间: {cat_data.get('fetch_time', 'N/A')}")
    print(f"  数据规模:")
    print(f"    - 一级分类: {summary.get('level_1_categories', 0)} 个")
    print(f"    - 二级分类: {summary.get('level_2_categories', 0)} 个")
    print(f"    - 三级分类: {summary.get('level_3_categories', 0)} 个")
    print(f"    - 品牌总数: {summary.get('total_brands', 0)} 个")

    # 提取所有品牌
    all_brands = set()
    power_tool_brands = []
    categories = cat_data.get("categories", [])

    for cat in categories:
        for brand in cat.get("brands", []):
            brand_name = brand.get("name", "")
            all_brands.add(brand_name)

            # 筛选电动工具相关品牌
            power_keywords = [
                "博世", "BOSCH", "得伟", "DEWALT", "牧田", "MAKITA",
                "东成", "大有", "威克士", "WORX", "史丹利", "STANLEY",
                "百得", "BLACK", "日立", "HITACHI", "松下", "Panasonic",
                "麦太保", "METABO", "锐奇", "KEN", "科麦斯", "奥奔",
                "芝浦", "龙韵", "威达", "京东京造", "得力", "DELIXI",
                "德力西", "格力", "美的", "海尔", "TCL", "海信",
            ]
            if any(k.lower() in brand_name.lower() for k in power_keywords):
                power_tool_brands.append(brand_name)

    print(f"\n[品牌分析]")
    print(f"  全平台品牌总数: {len(all_brands)} 个")
    print(f"  电动工具相关品牌: {len(power_tool_brands)} 个")

    if power_tool_brands:
        print(f"\n  电动工具相关品牌列表:")
        for i, brand in enumerate(sorted(power_tool_brands), 1):
            print(f"    {i:2d}. {brand}")

    # 分类结构
    print(f"\n[分类结构]")
    level1_cats = [c for c in categories if c.get("level") == 1]
    level2_cats = [c for c in categories if c.get("level") == 2]

    print(f"  一级分类 ({len(level1_cats)} 个):")
    for cat in level1_cats[:10]:
        brand_count = len(cat.get("brands", []))
        child_count = len(cat.get("children", []))
        print(f"    - {cat['name']} (品牌:{brand_count}, 子分类:{child_count})")

    # 电动工具相关分类
    print(f"\n  电动工具相关分类:")
    power_cats = [
        c for c in categories
        if any(k in c.get("name", "") for k in ["工具", "五金", "电动", "机电"])
    ]
    for cat in power_cats:
        level = cat.get("level", "?")
        brands = [b["name"] for b in cat.get("brands", [])]
        print(f"    [{level}级] {cat['name']}")
        if brands:
            print(f"      品牌: {', '.join(brands[:10])}")

    # 采集限制说明
    print(f"\n[采集限制与解决方案]")
    print(f"  当前限制:")
    print(f"    1. 京东搜索页 (search.jd.com) - 需要登录 + 验证码")
    print(f"    2. 商品列表页 (list.jd.com) - 需要登录 + 验证码")
    print(f"    3. 商品详情页 (item.jd.com) - 需要登录 + 验证码")
    print(f"    4. 价格 API (p.3.cn) - 连接超时")
    print(f"    5. 排行榜 (re.jd.com) - 需要登录")
    print(f"")
    print(f"  可用数据:")
    print(f"    ✓ dc.3.cn/category/get - 分类树 + 品牌列表 (87 品牌)")
    print(f"")
    print(f"  完整采集方案 (需要登录 Cookie):")
    print(f"    1. 使用浏览器登录京东获取 Cookie")
    print(f"    2. 通过 search.jd.com 搜索'电动工具'")
    print(f"    3. 解析搜索结果提取: 商品名、价格、店铺、销量")
    print(f"    4. 分页采集 (每页 30 个商品，建议 5-10 页)")
    print(f"    5. 统计品牌分布、价格区间、店铺排名")

    # 预期数据结构
    print(f"\n[预期数据结构 (完整采集后)]")
    expected = {
        "keyword": "电动工具",
        "fetch_time": "ISO 时间戳",
        "summary": {
            "total_products": "采集商品总数",
            "total_brands": "涉及品牌数",
            "total_shops": "涉及店铺数",
            "price_range": {"min": 0, "max": 0, "avg": 0},
        },
        "brand_distribution": [
            {"brand": "博世", "count": 150, "percentage": 15.0},
            {"brand": "东成", "count": 120, "percentage": 12.0},
        ],
        "price_analysis": {
            "count": 1000,
            "min": 29.9,
            "max": 15999.0,
            "avg": 456.78,
            "median": 299.0,
            "distribution": {
                "0-100": 200,
                "100-300": 350,
                "300-500": 250,
                "500-1000": 150,
                "1000+": 50,
            },
        },
        "top_shops": [
            {
                "rank": 1,
                "shop": "博世京东自营旗舰店",
                "product_count": 85,
                "avg_price": 599.0,
                "total_sales": "10万+",
            },
        ],
        "sample_products": [
            {
                "sku": "100012345678",
                "name": "博世(BOSCH) 充电式电钻 GSR 120-LI",
                "brand": "博世",
                "price": 599.0,
                "shop": "博世京东自营旗舰店",
                "comments": "5万+",
            },
        ],
    }
    print(json.dumps(expected, ensure_ascii=False, indent=2))

    # 保存报告
    report = {
        "report_time": datetime.now().isoformat(),
        "data_source": "dc.3.cn/category/get",
        "fetch_time": cat_data.get("fetch_time", ""),
        "summary": summary,
        "total_brands": len(all_brands),
        "power_tool_brands": sorted(power_tool_brands),
        "categories": {
            "level_1": len(level1_cats),
            "level_2": len(level2_cats),
            "power_tool_related": len(power_cats),
        },
        "limitations": [
            "搜索页需要登录 + 验证码",
            "列表页需要登录 + 验证码",
            "详情页需要登录 + 验证码",
            "价格 API 连接超时",
            "排行榜需要登录",
        ],
        "available_data": ["dc.3.cn 分类树 + 品牌列表"],
        "expected_structure": expected,
    }

    output = DATA_DIR / f"jd_power_tools_report_{ts}.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n[输出文件]")
    print(f"  报告: {output}")

    # 同时保存品牌列表
    brands_output = DATA_DIR / f"jd_brands_list_{ts}.json"
    with open(brands_output, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total": len(all_brands),
                "power_tool_related": len(power_tool_brands),
                "brands": sorted(list(all_brands)),
                "power_tool_brands": sorted(power_tool_brands),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"  品牌列表: {brands_output}")

    print("\n" + "=" * 70)
    print("  报告生成完成")
    print("=" * 70)


if __name__ == "__main__":
    generate_report()
