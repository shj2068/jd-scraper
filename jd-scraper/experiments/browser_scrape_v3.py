"""
京东数据采集 v3 - 移动版 + 深入分析
1. 分析 list.jd.com 页面 script 中的嵌入数据
2. 尝试移动版搜索 (so.m.jd.com)
3. 尝试移动版详情 (item.m.jd.com)
4. 尝试京东开放 API 端点
"""
import json
import os
import re
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

all_products = []
all_api_data = []


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
                # 只保存有实际数据的响应
                if isinstance(data, dict) and any(k in data for k in ["data", "ware", "sku", "price", "products", "result"]):
                    all_api_data.append({"url": url[:300], "data": data, "size": len(body)})
            except Exception:
                pass
        except Exception:
            pass


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("=" * 60)
    print("京东数据采集 v3 - 移动版 + 数据分析")
    print(f"时间: {datetime.now().isoformat()}")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge", headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )

        # ====== Part A: 分析 list.jd.com 嵌入数据 ======
        print("\n[Part A] 分析 list.jd.com 嵌入数据...")
        ctx1 = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        ctx1.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        page1 = ctx1.new_page()
        page1.on("response", on_response)

        page1.goto("https://list.jd.com/list.html?cat=670,671,672", timeout=25000, wait_until="domcontentloaded")
        time.sleep(5)
        for y in [500, 1500, 3000, 5000, 8000]:
            try:
                page1.evaluate(f"window.scrollTo(0, {y})")
                time.sleep(1)
            except Exception:
                pass

        html = page1.content()
        # 提取 script 中的数据
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
        for i, s in enumerate(scripts):
            # 查找包含商品数据的 JSON
            if '"wareId"' in s or '"skuId"' in s or '"wname"' in s:
                print(f"  Script[{i}]: 含商品数据 ({len(s)} chars)")
                # 尝试提取 JSON
                json_matches = re.findall(r'\{[^{}]{50,}(?:\{[^{}]*\}[^{}]*)*\}', s)
                for jm in json_matches[:3]:
                    try:
                        d = json.loads(jm)
                        print(f"    JSON: {json.dumps(d, ensure_ascii=False)[:200]}")
                    except Exception:
                        pass

        # 用 Playwright 选择器查找所有可能的商品元素
        print("\n  尝试各种选择器:")
        selectors_to_try = [
            ("li[data-sku]", "li[data-sku]"),
            (".gl-item", ".gl-item"),
            ("[data-widget='ware-list']", "ware-list"),
            (".p-img a", "p-img links"),
            (".p-name a", "p-name links"),
            ("a[href*='item.jd.com']", "item links"),
            (".goods-list-v2 li", "goods-list-v2"),
            (".shoplist li", "shoplist"),
            (".ml-item", "ml-item"),
            (".j-sku-item", "j-sku-item"),
            (".goods-item", "goods-item"),
            (".ware-list li", "ware-list li"),
            ("#plist li", "plist li"),
            (".list-wrap li", "list-wrap li"),
        ]
        for sel, name in selectors_to_try:
            try:
                els = page1.query_selector_all(sel)
                if els:
                    print(f"    {name}: {len(els)} 个")
                    if len(els) <= 3:
                        for el in els:
                            outer = el.evaluate("el => el.outerHTML.substring(0, 200)")
                            print(f"      {outer[:150]}")
            except Exception:
                pass

        # 提取所有链接和文本
        print("\n  页面所有 href 中含 SKU 的链接:")
        all_hrefs = page1.evaluate("""
            () => {
                const links = document.querySelectorAll('a[href]');
                const results = [];
                for (const a of links) {
                    const href = a.href;
                    if (href.includes('item.jd.com') || href.includes('sku=')) {
                        results.push({href: href.substring(0, 200), text: a.textContent.trim().substring(0, 100)});
                    }
                }
                return results;
            }
        """)
        print(f"    找到 {len(all_hrefs)} 个")
        for link in all_hrefs[:10]:
            print(f"    - {link['href'][:100]}  text='{link['text'][:50]}'")

        # 提取页面中所有可见文本中含价格格式的
        prices_on_page = page1.evaluate("""
            () => {
                const all = document.body.innerText;
                const prices = all.match(/¥[\\d,.]+/g);
                return prices ? prices.slice(0, 20) : [];
            }
        """)
        print(f"\n  页面价格: {len(prices_on_page)} 个")
        if prices_on_page:
            print(f"    {prices_on_page[:10]}")

        ctx1.close()

        # ====== Part B: 移动版搜索 ======
        print("\n[Part B] 移动版搜索 (m.jd.com)...")
        ctx2 = browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            viewport={"width": 390, "height": 844},
            locale="zh-CN",
            is_mobile=True,
        )
        ctx2.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        page2 = ctx2.new_page()
        page2.on("response", on_response)

        for kw in ["轴承", "电机", "PLC控制器"]:
            print(f"\n  搜索: {kw}")
            apis_before = len(all_api_data)
            try:
                page2.goto(f"https://so.m.jd.com/ware/search.action?keyword={kw}", timeout=20000, wait_until="domcontentloaded")
                time.sleep(4)
                print(f"    URL: {page2.url[:100]}")
                print(f"    Title: {page2.title()}")

                # 滚动
                for y in [300, 800, 1500, 3000]:
                    try:
                        page2.evaluate(f"window.scrollTo(0, {y})")
                        time.sleep(0.5)
                    except Exception:
                        pass

                mhtml = page2.content()
                print(f"    HTML: {len(mhtml)} bytes")

                # 提取移动版商品
                m_products = page2.evaluate("""
                    () => {
                        const items = document.querySelectorAll('.ware-item, .search_prolist li, .goods-list li, [data-sku]');
                        return Array.from(items).slice(0, 30).map(el => ({
                            sku: el.getAttribute('data-sku') || el.getAttribute('data-wareid') || '',
                            name: (el.querySelector('.ware-title, .p-name, .goods-name, a') || {}).textContent || '',
                            price: (el.querySelector('.ware-price, .p-price, .goods-price, .price') || {}).textContent || '',
                        }));
                    }
                """)
                print(f"    商品: {len(m_products)} 个")
                for mp in m_products[:3]:
                    print(f"      SKU={mp['sku']} {mp['name'][:50]} ¥{mp['price']}")

                for mp in m_products:
                    mp["keyword"] = kw
                    mp["source"] = "mobile_search"
                all_products.extend(m_products)

                # 截图
                safe_kw = re.sub(r'[^\w]', '_', kw)
                page2.screenshot(path=os.path.join(DATA_DIR, f"mobile_search_{safe_kw}.png"))

                print(f"    新增 API: {len(all_api_data) - apis_before}")

            except Exception as e:
                print(f"    失败: {str(e)[:100]}")

        # ====== Part C: 移动版详情 ======
        print("\n[Part C] 移动版商品详情...")
        test_skus = []
        for prod in all_products:
            if prod.get("sku") and prod["sku"] not in test_skus:
                test_skus.append(prod["sku"])
            if len(test_skus) >= 3:
                break

        for sku in test_skus:
            print(f"\n  详情: SKU {sku}")
            apis_before = len(all_api_data)
            try:
                page2.goto(f"https://item.m.jd.com/product/{sku}.html", timeout=20000, wait_until="domcontentloaded")
                time.sleep(3)
                print(f"    URL: {page2.url[:100]}")
                print(f"    Title: {page2.title()}")

                detail = page2.evaluate("""
                    () => {
                        return {
                            name: (document.querySelector('.sku-name, .item-name, .ware-title, h1') || {}).textContent || '',
                            price: (document.querySelector('.price, .sku-price, .ware-price') || {}).textContent || '',
                        };
                    }
                """)
                print(f"    {detail}")
                detail["sku"] = sku
                detail["source"] = "mobile_detail"
                all_products.append(detail)
                print(f"    新增 API: {len(all_api_data) - apis_before}")

            except Exception as e:
                print(f"    失败: {str(e)[:80]}")

        ctx2.close()
        browser.close()

    # ====== 保存 ======
    # API 数据
    with open(os.path.join(DATA_DIR, f"v3_api_data_{ts}.json"), "w", encoding="utf-8") as f:
        json.dump(all_api_data, f, ensure_ascii=False, indent=2)
    print(f"\nAPI 数据: {len(all_api_data)} 条")

    # 商品数据
    with open(os.path.join(DATA_DIR, f"v3_products_{ts}.json"), "w", encoding="utf-8") as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2)
    print(f"商品数据: {len(all_products)} 条")

    # 打印有价值的 API 数据
    print("\n有价值的 API 响应:")
    for i, api in enumerate(all_api_data[:20]):
        url = api["url"][:100]
        data = api.get("data", {})
        size = api["size"]
        keys = list(data.keys())[:5] if isinstance(data, dict) else []
        print(f"  [{i}] {url}  size={size}  keys={keys}")
        # 如果有 data 字段，展开看
        if isinstance(data, dict) and "data" in data:
            inner = data["data"]
            if isinstance(inner, dict):
                inner_keys = list(inner.keys())[:10]
                print(f"      data keys: {inner_keys}")
            elif isinstance(inner, list) and len(inner) > 0:
                print(f"      data: list[{len(inner)}]")
                if isinstance(inner[0], dict):
                    print(f"      first item keys: {list(inner[0].keys())[:10]}")

    print(f"\n{'=' * 60}")
    print("汇总:")
    print(f"  API 数据: {len(all_api_data)} 条")
    print(f"  商品数据: {len(all_products)} 条")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
