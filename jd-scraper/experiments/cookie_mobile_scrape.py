"""
方案1 改进版 v2: 移动端采集（m.jd.com 限制更宽松）
"""
import json
import re
import time
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
COOKIE_FILE = DATA_DIR / "jd_cookies.json"


def scrape_mobile():
    """通过移动端采集商品"""
    from playwright.sync_api import sync_playwright

    cookie_data = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
    cookies = cookie_data["cookies"]
    print(f"✓ 加载 {len(cookies)} 个 Cookie")

    products = []
    all_apis = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge",
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 390, "height": 844},  # iPhone 尺寸
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            is_mobile=True,
            has_touch=True,
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        context.add_cookies(cookies)

        page = context.new_page()

        # 拦截所有 API 响应
        def handle_response(response):
            url = response.url
            ct = response.headers.get("content-type", "")
            if response.status == 200 and ("json" in ct or "javascript" in ct):
                try:
                    body = response.text()
                    if len(body) > 200:
                        all_apis.append({"url": url[:200], "size": len(body), "preview": body[:500]})
                except Exception:
                    pass

        page.on("response", handle_response)

        # 1. 移动端搜索
        keywords = ["轴承", "电机", "传感器"]
        for kw in keywords:
            print(f"\n--- 搜索: {kw} ---")
            search_url = f"https://so.m.jd.com/ware/search.action?keyword={kw}"
            try:
                page.goto(search_url, timeout=20000, wait_until="domcontentloaded")
                time.sleep(5)

                current_url = page.url
                title = page.title()
                print(f"  标题: {title[:60]}")
                print(f"  URL: {current_url[:100]}")

                # 截图
                try:
                    page.screenshot(path=str(DATA_DIR / f"mobile_search_{kw}.png"))
                except Exception:
                    pass

                # 检查是否被拦截
                if "risk" in current_url or "cfe" in current_url:
                    print(f"  ✗ 被风控拦截")
                    continue

                # 提取商品
                html = page.content()

                # 移动端选择器
                sku_matches = re.findall(r'skuId["\s:=]+(\d{5,})', html)
                link_matches = re.findall(r'item\.jd\.com/(\d+)\.html', html)
                # 移动端常用格式
                mobile_sku = re.findall(r'"skuId"\s*:\s*"?(\d{5,})"?', html)
                ware_id = re.findall(r'wareId["\s:=]+(\d{5,})', html)

                all_skus = set(sku_matches + link_matches + mobile_sku + ware_id)
                print(f"  SKU 匹配: skuId={len(sku_matches)}, item.jd={len(link_matches)}, mobile={len(mobile_sku)}, wareId={len(ware_id)}")

                for sku in all_skus:
                    if not any(p["sku_id"] == sku for p in products):
                        products.append({"sku_id": sku, "keyword": kw, "source": "mobile_search"})

                print(f"  累计: {len(products)}")

                # 滚动
                for pos in [300, 600, 900]:
                    try:
                        page.evaluate(f"window.scrollTo(0, {pos})")
                        time.sleep(2)
                    except Exception:
                        break

                # 再次提取
                html2 = page.content()
                sku2 = re.findall(r'skuId["\s:=]+(\d{5,})', html2)
                link2 = re.findall(r'item\.jd\.com/(\d+)\.html', html2)
                mobile2 = re.findall(r'"skuId"\s*:\s*"?(\d{5,})"?', html2)
                for sku in set(sku2 + link2 + mobile2):
                    if not any(p["sku_id"] == sku for p in products):
                        products.append({"sku_id": sku, "keyword": kw, "source": "mobile_search"})

                print(f"  滚动后累计: {len(products)}")

            except Exception as e:
                print(f"  ✗ 异常: {str(e)[:100]}")

        # 2. 移动端分类页
        print("\n--- 移动端分类 ---")
        try:
            page.goto("https://category.m.jd.com/", timeout=20000, wait_until="domcontentloaded")
            time.sleep(5)
            title = page.title()
            print(f"  分类页: {title[:60]}")
            try:
                page.screenshot(path=str(DATA_DIR / "mobile_category.png"))
            except Exception:
                pass
        except Exception as e:
            print(f"  ✗ 异常: {str(e)[:100]}")

        # 3. 尝试访问商品详情页
        print(f"\n--- 详情页测试 ---")
        if products:
            for i, prod in enumerate(products[:5]):
                sku = prod["sku_id"]
                detail_url = f"https://item.m.jd.com/product/{sku}.html"
                try:
                    page.goto(detail_url, timeout=20000, wait_until="domcontentloaded")
                    time.sleep(4)
                    current_url = page.url
                    title = page.title()
                    print(f"  SKU {sku}: {title[:60]}")

                    if "risk" in current_url or "frequent" in current_url:
                        print(f"    ✗ 被拦截")
                        continue

                    html = page.content()
                    name_match = re.search(r'<title>([^<]+)</title>', html)
                    if name_match:
                        prod["name"] = name_match.group(1).strip()

                    price_match = re.search(r'"price"\s*:\s*["\']?([\d.]+)', html)
                    if price_match:
                        prod["price"] = price_match.group(1)

                    print(f"    name: {prod.get('name', 'N/A')[:50]}")
                    print(f"    price: {prod.get('price', 'N/A')}")

                    try:
                        page.screenshot(path=str(DATA_DIR / f"mobile_detail_{sku}.png"))
                    except Exception:
                        pass

                except Exception as e:
                    print(f"  SKU {sku} 异常: {str(e)[:80]}")
        else:
            print("  无商品可访问")

        browser.close()

    # 分析 API 响应
    print(f"\n--- API 响应分析 ---")
    product_apis = [a for a in all_apis if any(kw in a["url"].lower() for kw in [
        "search", "goods", "ware", "product", "list", "recommend",
        "category", "item", "sku", "price", "comment", "functionid"
    ]) and not a["url"].endswith((".js", ".css"))]
    print(f"  总 API: {len(all_apis)}, 商品相关: {len(product_apis)}")
    for api in product_apis[:10]:
        print(f"    {api['url'][:120]} ({api['size']}B)")
        if "preview" in api:
            preview = api["preview"][:200]
            print(f"      preview: {preview[:200]}")

    # 保存
    result = {
        "method": "cookie_mobile_scrape",
        "timestamp": datetime.now().isoformat(),
        "products_count": len(products),
        "api_responses_count": len(all_apis),
        "product_apis_count": len(product_apis),
        "products": products[:100],
        "product_apis": product_apis[:15],
    }
    outfile = DATA_DIR / f"cookie_mobile_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    outfile.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"结果: {len(products)} 个商品, {len(all_apis)} 个 API, {len(product_apis)} 个商品 API")
    print(f"文件: {outfile}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    scrape_mobile()
