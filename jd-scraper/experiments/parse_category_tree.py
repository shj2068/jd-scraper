#!/usr/bin/env python3
"""解析京东分类树原始数据，提取完整分类结构和品牌信息"""
import json, re
from pathlib import Path
from datetime import datetime
from urllib.parse import unquote

raw_path = Path(__file__).parent / "data" / "jd_categories_raw.json"
with open(raw_path, "r", encoding="utf-8") as f:
    raw = json.load(f)

print("=" * 70)
print("  京东分类树深度解析")
print("=" * 70)

data = raw.get("data", [])
print(f"  顶层分类组: {len(data)} 个")

all_categories = []  # 所有分类
all_brands = []      # 所有品牌
all_search_links = [] # 所有搜索链接

def parse_node_name(n_str):
    """解析节点名称字段 (格式: url|display_name||hot_flag)"""
    parts = n_str.split("|")
    url = parts[0] if len(parts) > 0 else ""
    name = parts[1] if len(parts) > 1 else ""
    hot = parts[3] if len(parts) > 3 else "0"
    # 从 URL 提取搜索关键词
    keyword = ""
    if "keyword=" in url:
        m = re.search(r'keyword=([^&]+)', url)
        if m:
            keyword = unquote(m.group(1))
    return {"name": name, "url": url, "keyword": keyword, "hot": hot}

def walk_tree(node, depth=0, parent_path=""):
    """递归遍历分类树"""
    # 处理 s 字段（子分类）
    if isinstance(node, dict) and "s" in node:
        for child in node["s"]:
            n_info = parse_node_name(child.get("n", ""))
            cat_path = f"{parent_path}/{n_info['name']}" if parent_path else n_info['name']
            
            all_categories.append({
                "name": n_info["name"],
                "keyword": n_info["keyword"],
                "depth": depth,
                "path": cat_path,
                "hot": n_info["hot"] == "1",
            })
            
            if n_info["keyword"]:
                all_search_links.append({
                    "category": cat_path,
                    "keyword": n_info["keyword"],
                    "depth": depth,
                })
            
            # 递归子节点
            walk_tree(child, depth + 1, cat_path)

# 遍历顶层
for group_idx, group in enumerate(data):
    brands = group.get("b", [])
    subs = group.get("s", [])
    
    print(f"\n  [组 {group_idx + 1}] 品牌: {len(brands)} 个, 子分类: {len(subs)} 个")
    
    # 解析品牌
    for b_str in brands:
        parts = b_str.split("|")
        if len(parts) >= 2:
            brand_url = parts[0]
            brand_name = parts[1]
            brand_logo = parts[2] if len(parts) > 2 else ""
            all_brands.append({
                "name": brand_name,
                "url": brand_url,
                "logo": brand_logo,
                "group": group_idx,
            })
    
    # 递归遍历子分类树
    for sub in subs:
        n_info = parse_node_name(sub.get("n", ""))
        cat_path = n_info["name"]
        
        all_categories.append({
            "name": n_info["name"],
            "keyword": n_info["keyword"],
            "depth": 0,
            "path": cat_path,
            "hot": n_info["hot"] == "1",
        })
        
        walk_tree(sub, 1, cat_path)

# ── 输出统计 ──────────────────────────────────────────────────────
print(f"\n{'=' * 70}")
print("  解析结果统计")
print("=" * 70)
print(f"  分类总数: {len(all_categories)}")
print(f"  品牌总数: {len(all_brands)}")
print(f"  搜索链接: {len(all_search_links)}")

# 按深度统计
depth_counts = {}
for c in all_categories:
    d = c["depth"]
    depth_counts[d] = depth_counts.get(d, 0) + 1
print(f"\n  按深度统计:")
for d in sorted(depth_counts):
    print(f"    深度 {d}: {depth_counts[d]} 个")

# 输出一级分类
print(f"\n  一级分类:")
level1 = [c for c in all_categories if c["depth"] == 0]
for c in level1:
    hot_mark = " 🔥" if c["hot"] else ""
    print(f"    {c['name']} (搜索: {c['keyword']}){hot_mark}")

# 输出品牌
print(f"\n  所有品牌 ({len(all_brands)}):")
for b in all_brands:
    print(f"    {b['name']}")

# ── 保存结构化数据 ────────────────────────────────────────────────
output = {
    "metadata": {
        "source": "dc.3.cn/category/get",
        "collected_at": datetime.now().isoformat(),
        "total_categories": len(all_categories),
        "total_brands": len(all_brands),
        "total_search_links": len(all_search_links),
    },
    "categories": all_categories,
    "brands": all_brands,
    "search_links": all_search_links,
}

output_path = Path(__file__).parent / "data" / f"jd_structured_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n  结构化数据已保存: {output_path}")
print("=" * 70)
