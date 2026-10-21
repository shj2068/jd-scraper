#!/usr/bin/env python3
"""
京东公开分类 API 数据采集 v2
API: dc.3.cn/category/get
数据格式: p=父级, b=品牌, s=子分类, n=名称(管道分隔)
"""

import json
import requests
import os
from datetime import datetime


def fetch_categories():
    """获取京东完整分类导航树"""
    url = "https://dc.3.cn/category/get"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.jd.com/",
        "Accept": "application/json, text/javascript, */*; q=0.01"
    }

    print("=" * 60)
    print("京东公开分类 API 数据采集 v2")
    print(f"API: {url}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    resp = requests.get(url, headers=headers, timeout=30)
    resp.encoding = "utf-8"
    print(f"\n✓ HTTP {resp.status_code}, 大小: {len(resp.content)} bytes")

    data = resp.json()
    print(f"✓ JSON 解析成功, 顶层键: {list(data.keys())}")
    return data


def parse_name(n_field):
    """从 n 字段提取名称 (格式: url|显示名|...|)"""
    if not n_field or not isinstance(n_field, str):
        return "", ""
    parts = n_field.split("|")
    url = parts[0] if parts else ""
    name = parts[1] if len(parts) > 1 else ""
    return url, name


def parse_brand(b_str):
    """解析品牌字符串 (格式: url|品牌名|logo路径|)"""
    if not b_str or not isinstance(b_str, str):
        return None
    parts = b_str.split("|")
    if len(parts) < 2:
        return None
    return {
        "url": parts[0],
        "name": parts[1],
        "logo": parts[2] if len(parts) > 2 else ""
    }


def parse_category_tree(data):
    """解析分类树"""
    result = {
        "fetch_time": datetime.now().isoformat(),
        "source": "dc.3.cn/category/get",
        "summary": {},
        "categories": []
    }

    raw_categories = data.get("data", [])
    total_l1 = 0
    total_l2 = 0
    total_l3 = 0
    total_brands = 0

    for cat_data in raw_categories:
        if not isinstance(cat_data, dict):
            continue

        # 一级分类: 从第一个子分类的 n 字段推断名称
        # 一级分类本身没有 n 字段，需要从 s 的子级推断分组名
        level1_name = ""
        level1_url = ""

        # 解析品牌 (b 字段)
        brands = []
        for b_str in cat_data.get("b", []):
            brand = parse_brand(b_str)
            if brand:
                brands.append(brand)

        # 解析二级分类 (s 字段)
        children = []
        for sub_data in cat_data.get("s", []):
            if not isinstance(sub_data, dict):
                continue

            sub_url, sub_name = parse_name(sub_data.get("n", ""))

            # 如果一级名为空，用第一个二级类的名称作为分组参考
            if not level1_name and sub_name:
                # 一级分类名通常可以从子分类 URL 的 keyword 推断
                pass

            # 解析二级分类的品牌
            sub_brands = []
            for b_str in sub_data.get("b", []):
                brand = parse_brand(b_str)
                if brand:
                    sub_brands.append(brand)

            # 解析三级分类 (s 字段中的 s)
            grandchildren = []
            for third_data in sub_data.get("s", []):
                if not isinstance(third_data, dict):
                    continue
                third_url, third_name = parse_name(third_data.get("n", ""))
                if third_name:
                    grandchildren.append({
                        "name": third_name,
                        "url": third_url,
                        "level": 3
                    })

            if sub_name:
                children.append({
                    "name": sub_name,
                    "url": sub_url,
                    "level": 2,
                    "brands": sub_brands,
                    "children": grandchildren
                })

        # 从第一个子分类 URL 中提取一级分类名
        if children:
            first_url = children[0].get("url", "")
            if "keyword=" in first_url:
                kw = first_url.split("keyword=")[1].split("&")[0]
                from urllib.parse import unquote
                level1_name = unquote(kw)

        if level1_name or children:
            total_l1 += 1
            total_l2 += len(children)
            total_brands += len(brands)
            for ch in children:
                total_brands += len(ch["brands"])
                total_l3 += len(ch["children"])

            result["categories"].append({
                "name": level1_name,
                "level": 1,
                "brands": brands,
                "children": children
            })

    result["summary"] = {
        "level_1_categories": total_l1,
        "level_2_categories": total_l2,
        "level_3_categories": total_l3,
        "total_brands": total_brands
    }

    return result


def print_summary(result):
    """打印摘要"""
    print("\n" + "=" * 60)
    print("采集结果摘要")
    print("=" * 60)

    s = result["summary"]
    print(f"  一级分类: {s['level_1_categories']}")
    print(f"  二级分类: {s['level_2_categories']}")
    print(f"  三级分类: {s['level_3_categories']}")
    print(f"  品牌总数: {s['total_brands']}")

    print("\n--- 一级分类及子分类 ---")
    for i, cat in enumerate(result["categories"], 1):
        brand_count = len(cat["brands"])
        brand_str = f" [{brand_count}品牌]" if brand_count > 0 else ""
        print(f"\n  {i:2d}. {cat['name']}{brand_str}")

        for j, ch in enumerate(cat["children"][:8], 1):
            sub_brand_count = len(ch["brands"])
            sub_child_count = len(ch["children"])
            detail_parts = []
            if sub_brand_count > 0:
                detail_parts.append(f"{sub_brand_count}品牌")
            if sub_child_count > 0:
                detail_parts.append(f"{sub_child_count}子类")
            detail_str = f" [{', '.join(detail_parts)}]" if detail_parts else ""
            print(f"      {j:2d}. {ch['name']}{detail_str}")

            # 打印部分三级分类
            for k, gc in enumerate(ch["children"][:3], 1):
                print(f"          - {gc['name']}")
            if sub_child_count > 3:
                print(f"          ... 还有 {sub_child_count - 3} 个")

        if len(cat["children"]) > 8:
            print(f"      ... 还有 {len(cat['children']) - 8} 个二级分类")


def save_results(result, raw_data):
    """保存结果"""
    os.makedirs("data", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 结构化数据
    parsed_path = f"data/jd_categories_{timestamp}.json"
    with open(parsed_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✓ 结构化数据: {parsed_path}")

    # 原始数据
    raw_path = f"data/jd_categories_raw_{timestamp}.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)
    print(f"✓ 原始数据: {raw_path}")

    # 生成简洁的 CSV 格式（方便查看）
    csv_path = f"data/jd_categories_{timestamp}.csv"
    with open(csv_path, "w", encoding="utf-8-sig") as f:
        f.write("一级分类,二级分类,三级分类,品牌\n")
        for cat in result["categories"]:
            cat_name = cat["name"]
            # 一级品牌
            for b in cat["brands"]:
                f.write(f"{cat_name},,,{b['name']}\n")
            for ch in cat["children"]:
                ch_name = ch["name"]
                for b in ch["brands"]:
                    f.write(f"{cat_name},{ch_name},,{b['name']}\n")
                for gc in ch["children"]:
                    f.write(f"{cat_name},{ch_name},{gc['name']},\n")
    print(f"✓ CSV 数据: {csv_path}")

    return parsed_path


def main():
    raw_data = fetch_categories()
    result = parse_category_tree(raw_data)
    print_summary(result)
    save_results(result, raw_data)

    print("\n" + "=" * 60)
    print("采集完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
