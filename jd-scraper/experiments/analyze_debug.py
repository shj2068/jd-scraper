"""分析调试数据: 拦截的 API + 分类列表页 HTML 结构"""
import json
import re
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# 1. 分析拦截的 API
print("=" * 60)
print("1. 拦截的 API 响应")
print("=" * 60)
apis = json.load(open(os.path.join(DATA_DIR, "debug_apis.json"), "r", encoding="utf-8"))
print(f"总计: {len(apis)} 条")
for i, a in enumerate(apis):
    url = a["url"][:120]
    size = a["size"]
    if a["type"] == "json":
        data = a.get("data", {})
        # 显示顶层 key
        keys = list(data.keys())[:5] if isinstance(data, dict) else []
        print(f"  [{i:2d}] {url}")
        print(f"       size={size}  keys={keys}")
    else:
        preview = a.get("preview", "")[:100]
        print(f"  [{i:2d}] {url}")
        print(f"       size={size}  raw: {preview}")

# 2. 分析分类列表页 HTML
print("\n" + "=" * 60)
print("2. 分类列表页 HTML 结构")
print("=" * 60)
html_path = os.path.join(DATA_DIR, "debug_list_page.html")
if os.path.exists(html_path):
    html = open(html_path, "r", encoding="utf-8").read()
    print(f"HTML 大小: {len(html)} bytes")

    # 查找商品相关元素
    patterns = [
        (r'data-sku="(\d+)"', "data-sku"),
        (r'data-wid="(\d+)"', "data-wid"),
        (r'data-pid="(\d+)"', "data-pid"),
        (r'class="gl-item', "gl-item"),
        (r'class="goods-list', "goods-list"),
        (r'class="p-list', "p-list"),
        (r'class="J_goodsList', "J_goodsList"),
        (r'ware_status', "ware_status"),
        (r'"skuId"', "skuId in HTML"),
        (r'"wareId"', "wareId in HTML"),
        (r'"ware_id"', "ware_id in HTML"),
        (r'class="[^"]*product[^"]*"', "product class"),
        (r'class="[^"]*goods-item[^"]*"', "goods-item class"),
        (r'class="[^"]*list-item[^"]*"', "list-item class"),
        (r'class="[^"]*ware[^"]*"', "ware class"),
        (r'href="//item\.jd\.com/(\d+)\.html"', "item link"),
        (r'//img\d+\.360buyimg\.com', "product image"),
    ]
    for pat, name in patterns:
        matches = re.findall(pat, html)
        if matches:
            print(f"  {name}: {len(matches)} 匹配")
            if len(matches) <= 5:
                for m in matches:
                    print(f"    - {str(m)[:80]}")

    # 查找 script 中的数据
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    print(f"\n  Script 标签: {len(scripts)} 个")
    for i, s in enumerate(scripts):
        if len(s) > 100 and any(kw in s for kw in ["sku", "ware", "price", "product", "goods", "item"]):
            print(f"  Script[{i}] ({len(s)} chars) 含商品关键词:")
            # 提取关键片段
            for kw in ["skuId", "wareId", "ware_id", "price", "skuList", "goodsList"]:
                if kw in s:
                    idx = s.index(kw)
                    print(f"    {kw}: ...{s[max(0,idx-20):idx+80]}...")

    # 查找所有 img 的 src (商品图片)
    imgs = re.findall(r'//img\d+\.360buyimg\.com/[^"\']+', html)
    print(f"\n  商品图片: {len(imgs)} 个")
    if imgs[:3]:
        for img in imgs[:3]:
            print(f"    - {img[:100]}")

    # 查找所有 item.jd.com 链接
    item_links = re.findall(r'//item\.jd\.com/(\d+)\.html', html)
    print(f"  商品链接: {len(item_links)} 个")
    if item_links[:5]:
        print(f"    前5: {item_links[:5]}")

    # 查找所有 jd.com 相关链接
    all_links = re.findall(r'href="([^"]*jd\.com[^"]*)"', html)
    print(f"  jd.com 链接: {len(all_links)} 个")
