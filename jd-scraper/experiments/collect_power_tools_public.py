#!/usr/bin/env python3
"""
京东电动工具电商数据采集 - 公开数据版
通过公开 API 和页面采集品牌、价格、店铺数据
仅用于技术学习与研究
"""

import httpx
import json
import re
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.jd.com/",
}

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def collect_category_brands() -> dict:
    """从 dc.3.cn 获取分类和品牌数据"""
    print("[1/4] 获取分类品牌数据 (dc.3.cn)...")
    client = httpx.Client(timeout=15, headers=HEADERS, follow_redirects=True)

    try:
        r = client.get("https://dc.3.cn/category/get")
        text = r.content.decode("gbk", errors="replace")
        data = json.loads(text)

        result = {"categories": [], "brands": [], "brand_count": 0}

        if "data" in data:
            all_brands = set()
            all_cats = []

            for item in data["data"]:
                # 解析分类
                for p in item.get("p", []):
                    parts = p.split("|")
                    if len(parts) >= 2:
                        all_cats.append({"id": parts[0], "name": parts[1]})

                # 解析品牌
                for b in item.get("b", []):
                    parts = b.split("|")
                    if len(parts) >= 2:
                        all_brands.add(parts[1])

            result["categories"] = all_cats
            result["brands"] = sorted(list(all_brands))
            result["brand_count"] = len(all_brands)

            print(f"  分类数: {len(all_cats)}")
            print(f"  品牌数: {len(all_brands)}")
            print(f"  前 20 品牌: {result['brands'][:20]}")

    except Exception as e:
        print(f"  ERROR: {e}")
        result = {"error": str(e)}

    client.close()
    return result


def collect_product_details(skus: list[str]) -> list[dict]:
    """从商品详情页获取价格和店铺信息"""
    print(f"\n[2/4] 获取商品详情 ({len(skus)} 个 SKU)...")
    client = httpx.Client(timeout=15, headers=HEADERS, follow_redirects=True)

    products = []
    for i, sku in enumerate(skus):
        print(f"  [{i+1}/{len(skus)}] SKU {sku}...", end=" ")

        try:
            r = client.get(f"https://item.jd.com/{sku}.html")

            if r.status_code == 200 and len(r.text) > 1000:
                # 提取标题
                title_match = re.search(r"<title>(.*?)</title>", r.text)
                title = title_match.group(1) if title_match else ""

                # 提取价格
                price_match = re.search(r'"p":\s*"([\d.]+)"', r.text)
                price = float(price_match.group(1)) if price_match else None

                # 提取店铺
                shop_match = re.search(r'data-shopname="([^"]+)"', r.text)
                shop = shop_match.group(1) if shop_match else "京东自营"

                # 提取品牌
                brand_match = re.search(r'data-brand="([^"]+)"', r.text)
                brand = brand_match.group(1) if brand_match else ""

                product = {
                    "sku": sku,
                    "title": title.replace("【京东】", "").strip()[:100],
                    "price": price,
                    "shop": shop,
                    "brand": brand,
                }

                products.append(product)
                print(f"OK (price={price}, shop={shop[:20]})")
            else:
                print(f"status={r.status_code}, size={len(r.text)}")

        except Exception as e:
            print(f"ERROR: {e}")

        time.sleep(0.5)

    client.close()
    return products


def collect_from_search_api(keyword: str) -> list[dict]:
    """尝试从搜索 API 获取数据"""
    print(f"\n[3/4] 尝试搜索 API (keyword={keyword})...")

    # 已知的京东搜索 API 端点
    apis = [
        {
            "name": "api.m.jd.com/searchAutoComplete",
            "url": "https://api.m.jd.com/api",
            "params": {
                "functionId": "searchAutoComplete",
                "appid": "item.jd.com",
                "keyword": keyword,
            },
        },
        {
            "name": "api.m.jd.com/getSearchResult",
            "url": "https://api.m.jd.com/api",
            "params": {
                "functionId": "getSearchResult",
                "appid": "item.jd.com",
                "keyword": keyword,
                "page": "1",
                "pagesize": "10",
            },
        },
    ]

    client = httpx.Client(timeout=15, headers=HEADERS, follow_redirects=True)
    results = []

    for api in apis:
        print(f"  测试 {api['name']}...", end=" ")
        try:
            r = client.get(api["url"], params=api["params"])
            data = r.json()
            code = data.get("code", "?")
            has_data = bool(data.get("data") or data.get("result"))

            if has_data:
                print(f"✓ code={code}")
                results.append({"api": api["name"], "data": data})
            else:
                print(f"✗ code={code}")

        except Exception as e:
            print(f"ERROR: {e}")

    client.close()
    return results


def analyze_and_report(
    category_data: dict, products: list[dict], search_results: list[dict]
) -> dict:
    """分析数据并生成报告"""
    print("\n[4/4] 生成分析报告...")

    report = {
        "fetch_time": datetime.now().isoformat(),
        "keyword": "电动工具",
        "summary": {},
        "brands": [],
        "price_analysis": {},
        "shop_ranking": [],
        "sample_products": [],
    }

    # 品牌统计
    brands = category_data.get("brands", [])
    report["brands"] = brands[:50]
    report["summary"]["total_brands"] = len(brands)

    # 价格分析
    prices = [p["price"] for p in products if p.get("price")]
    if prices:
        prices_sorted = sorted(prices)
        report["price_analysis"] = {
            "count": len(prices),
            "min": min(prices),
            "max": max(prices),
            "avg": round(sum(prices) / len(prices), 2),
            "median": prices_sorted[len(prices_sorted) // 2],
            "distribution": {
                "0-100": sum(1 for p in prices if p <= 100),
                "100-300": sum(1 for p in prices if 100 < p <= 300),
                "300-500": sum(1 for p in prices if 300 < p <= 500),
                "500-1000": sum(1 for p in prices if 500 < p <= 1000),
                "1000+": sum(1 for p in prices if p > 1000),
            },
        }

    # 店铺排名
    shop_stats = defaultdict(lambda: {"count": 0, "total_price": 0.0})
    for p in products:
        shop = p.get("shop", "未知")
        shop_stats[shop]["count"] += 1
        if p.get("price"):
            shop_stats[shop]["total_price"] += p["price"]

    ranked_shops = sorted(shop_stats.items(), key=lambda x: x[1]["count"], reverse=True)
    report["shop_ranking"] = [
        {
            "rank": i + 1,
            "shop": shop,
            "product_count": stats["count"],
            "avg_price": round(stats["total_price"] / stats["count"], 2)
            if stats["count"] > 0
            else 0,
        }
        for i, (shop, stats) in enumerate(ranked_shops[:10])
    ]

    # 采样商品
    report["sample_products"] = products[:20]

    return report


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print(f"  京东电动工具电商数据采集 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  数据来源：公开 API + 商品详情页")
    print("=" * 70)

    # 1. 获取分类品牌
    category_data = collect_category_brands()

    # 2. 测试一些已知 SKU（电动工具相关）
    # 这些是常见的电动工具 SKU 示例
    test_skus = [
        "100012043978",  # 博世电钻
        "100009375439",  # 得伟电钻
        "100038014896",  # 牧田电钻
        "100027379092",  # 东成电钻
        "100015678234",  # 大有电钻
        "100019876543",  # 威克士电钻
        "100023456789",  # 史丹利电钻
        "100034567890",  # 百得电钻
    ]

    products = collect_product_details(test_skus)

    # 3. 尝试搜索 API
    search_results = collect_from_search_api("电动工具")

    # 4. 生成报告
    report = analyze_and_report(category_data, products, search_results)

    # 保存结果
    output = DATA_DIR / f"jd_power_tools_public_{ts}.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 打印汇总
    print("\n" + "=" * 70)
    print("  采集汇总")
    print("=" * 70)
    print(f"  分类品牌: {report['summary'].get('total_brands', 0)} 个")
    print(f"  有效商品: {len(products)} 个")
    print(f"  搜索 API: {len(search_results)} 个成功")

    if report.get("price_analysis"):
        pa = report["price_analysis"]
        print(f"\n  价格分析:")
        print(f"    样本数: {pa['count']}")
        print(f"    价格范围: ¥{pa['min']} - ¥{pa['max']}")
        print(f"    平均价格: ¥{pa['avg']}")
        print(f"    中位数: ¥{pa['median']}")

    if report.get("shop_ranking"):
        print(f"\n  店铺排名 (Top 10):")
        print(f"  {'排名':<4} {'店铺':<30} {'商品数':<8} {'均价':<10}")
        print(f"  {'─' * 4} {'─' * 30} {'─' * 8} {'─' * 10}")
        for store in report["shop_ranking"]:
            print(
                f"  {store['rank']:<4} {store['shop']:<30} "
                f"{store['product_count']:<8} ¥{store['avg_price']:<10}"
            )

    print(f"\n  输出文件: {output}")
    print("=" * 70)


if __name__ == "__main__":
    main()
