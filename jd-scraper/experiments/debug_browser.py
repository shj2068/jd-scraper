"""
调试: 检查浏览器渲染的实际页面内容 + 拦截的 API 响应
"""
import json
import os
import re
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
captured = []


def on_response(response):
    url = response.url
    ct = response.headers.get("content-type", "")
    if ("json" in ct or "javascript" in ct) and response.status == 200:
        try:
            body = response.text()
            text = body.strip()
            m = re.match(r'^[a-zA-Z_]\w*\((.*)\);?$', text, re.DOTALL)
            if m:
                text = m.group(1)
            try:
                data = json.loads(text)
                captured.append({"url": url[:300], "type": "json", "data": data, "size": len(body)})
            except Exception:
                captured.append({"url": url[:300], "type": "raw", "preview": text[:500], "size": len(body)})
        except Exception:
            pass


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge", headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        page = context.new_page()
        page.on("response", on_response)

        # 搜索页
        print("[1] 搜索 '轴承' ...")
        page.goto("https://search.jd.com/Search?keyword=轴承&enc=utf-8", timeout=25000, wait_until="domcontentloaded")
        time.sleep(5)
        # 滚动
        for y in [500, 1500, 3000, 5000]:
            try:
                page.evaluate(f"window.scrollTo(0, {y})")
                time.sleep(1)
            except Exception:
                pass

        # 保存完整 HTML
        html = page.content()
        with open(os.path.join(DATA_DIR, "debug_search_page.html"), "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  URL: {page.url}")
        print(f"  Title: {page.title()}")
        print(f"  HTML 大小: {len(html)} bytes")

        # 分析 HTML 结构
        # 查找所有包含 data-sku 的元素
        sku_matches = re.findall(r'data-sku="(\d+)"', html)
        print(f"  data-sku 匹配: {len(sku_matches)} 个")
        if sku_matches[:5]:
            print(f"    前5个: {sku_matches[:5]}")

        # 查找 gl-item
        gl_items = re.findall(r'class="gl-item', html)
        print(f"  gl-item 匹配: {len(gl_items)} 个")

        # 查找 li 标签中的商品
        li_items = re.findall(r'<li[^>]*data-sku', html)
        print(f"  li[data-sku] 匹配: {len(li_items)} 个")

        # 查找所有 class 中包含 product/goods/item 的
        product_classes = re.findall(r'class="([^"]*(?:product|goods|item|sku)[^"]*)"', html, re.I)
        print(f"  商品相关 class: {len(product_classes)} 个")
        if product_classes[:10]:
            for c in product_classes[:10]:
                print(f"    - {c[:100]}")

        # 查找所有 JSON 数据嵌入
        json_in_script = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
        json_data_found = 0
        for script in json_in_script:
            if '"skuId"' in script or '"wareId"' in script or '"ware_id"' in script:
                json_data_found += 1
                # 提取前 300 字符
                print(f"  脚本中含商品数据: {script[:300]}...")
        print(f"  含商品数据的 script: {json_data_found} 个")

        # 保存截图
        page.screenshot(path=os.path.join(DATA_DIR, "debug_search.png"), full_page=False)

        # 详情页
        print("\n[2] 商品详情页 SKU 62776935498 ...")
        captured.clear()
        page.goto("https://item.jd.com/62776935498.html", timeout=25000, wait_until="domcontentloaded")
        time.sleep(4)
        for y in [300, 800, 1500]:
            try:
                page.evaluate(f"window.scrollTo(0, {y})")
                time.sleep(0.5)
            except Exception:
                pass

        detail_html = page.content()
        with open(os.path.join(DATA_DIR, "debug_detail_page.html"), "w", encoding="utf-8") as f:
            f.write(detail_html)
        print(f"  URL: {page.url}")
        print(f"  Title: {page.title()}")
        print(f"  HTML 大小: {len(detail_html)} bytes")

        # 检查详情元素
        for sel_name, sel in [("sku-name", ".sku-name"), ("price", ".p-price"), ("parameter", ".p-parameter-list")]:
            try:
                el = page.query_selector(sel)
                if el:
                    print(f"  {sel_name}: {el.inner_text().strip()[:100]}")
                else:
                    print(f"  {sel_name}: 未找到")
            except Exception as e:
                print(f"  {sel_name}: 错误 {e}")

        page.screenshot(path=os.path.join(DATA_DIR, "debug_detail.png"), full_page=False)

        # 分类列表
        print("\n[3] 分类列表: 笔记本 ...")
        captured.clear()
        page.goto("https://list.jd.com/list.html?cat=670,671,672", timeout=25000, wait_until="domcontentloaded")
        time.sleep(4)
        for y in [500, 1500, 3000, 5000]:
            try:
                page.evaluate(f"window.scrollTo(0, {y})")
                time.sleep(1)
            except Exception:
                pass

        list_html = page.content()
        with open(os.path.join(DATA_DIR, "debug_list_page.html"), "w", encoding="utf-8") as f:
            f.write(list_html)
        print(f"  URL: {page.url}")
        print(f"  Title: {page.title()}")
        print(f"  HTML 大小: {len(list_html)} bytes")
        sku_in_list = re.findall(r'data-sku="(\d+)"', list_html)
        print(f"  data-sku: {len(sku_in_list)} 个")
        if sku_in_list[:5]:
            print(f"    前5个: {sku_in_list[:5]}")
        page.screenshot(path=os.path.join(DATA_DIR, "debug_list.png"), full_page=False)

        browser.close()

    # 保存拦截到的 API 数据
    with open(os.path.join(DATA_DIR, "debug_apis.json"), "w", encoding="utf-8") as f:
        json.dump(captured, f, ensure_ascii=False, indent=2)
    print(f"\n拦截 API: {len(captured)} 条 → debug_apis.json")


if __name__ == "__main__":
    main()
