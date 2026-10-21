"""
方案1 改进版: 使用分类浏览页 + 详情页采集（绕过搜索限流）
"""
import json
import re
import time
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
COOKIE_FILE = DATA_DIR / "jd_cookies.json"


def scrape_by_category():
    """通过分类浏览页采集商品"""
    from playwright.sync_api import sync_playwright

    # 加载 Cookie
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
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        context.add_cookies(cookies)

        page = context.new_page()

        # 拦截所有 JSON/XHR 响应
        def handle_response(response):
            url = response.url
            ct = response.headers.get("content-type", "")
            if response.status == 200 and ("json" in ct or "javascript" in ct):
                try:
                    body = response.text()
                    if len(body) > 500 and any(kw in url.lower() for kw in [
                        "search", "goods", "ware", "product", "list", "recommend",
                        "category", "item", "sku", "price", "comment"
                    ]):
                        all_apis.append({"url": url[:200], "size": len(body)})
                except Exception:
                    pass

        page.on("response", handle_response)

        # 测试多个分类页
        categories = [
            ("轴承", "https://list.jd.com/list.html?cat=1318,1381,1384"),
            ("电机", "https://list.jd.com/list.html?cat=1318,1381,1393"),
            ("传感器", "https://list.jd.com/list.html?cat=1318,1381,1386"),
            ("工业品-综合", "https://list.jd.com/list.html?cat=1318"),
        ]

        for cat_name, cat_url in categories:
            print(f"\n--- 分类: {cat_name} ---")
            try:
                page.goto(cat_url, timeout=25000, wait_until="domcontentloaded")
                time.sleep(6)

                current_url = page.url
                title = page.title()
                print(f"  标题: {title[:60]}")
                print(f"  URL: {current_url[:80]}")

                # 检查是否被拦截
                if "frequent" in current_url or "risk" in current_url:
                    print(f"  ✗ 被拦截: {current_url[:80]}")
                    continue

                # 截图
                try:
                    page.screenshot(path=str(DATA_DIR / f"cat_{cat_name}.png"))
                except Exception:
                    pass

                # 尝试多种选择器提取商品
                html = page.content()

                # 方法1: data-sku 属性
                sku_matches = re.findall(r'data-sku="(\d+)"', html)
                print(f"  data-sku 匹配: {len(sku_matches)}")

                # 方法2: item.jd.com 链接
                link_matches = re.findall(r'//item\.jd\.com/(\d+)\.html', html)
                print(f"  商品链接匹配: {len(link_matches)}")

                # 方法3: 360buyimg 商品图片
                img_matches = re.findall(r'img\.jd\.com/n[0-9]*/jfs/[^"\s]+', html)
                print(f"  商品图片匹配: {len(img_matches)}")

                # 方法4: 提取所有 SKU
                all_skus = set(sku_matches + link_matches)
                for sku in all_skus:
                    if not any(p["sku_id"] == sku for p in products):
                        products.append({
                            "sku_id": sku,
                            "category": cat_name,
                            "source": "list",
                        })

                print(f"  累计商品: {len(products)}")

                # 翻页
                for pg in range(2, 4):
                    try:
                        next_url = f"{cat_url}&page={pg}"
                        page.goto(next_url, timeout=20000, wait_until="domcontentloaded")
                        time.sleep(4)
                        if "frequent" in page.url or "risk" in page.url:
                            print(f"  第{pg}页被拦截")
                            break
                        html2 = page.content()
                        sku2 = re.findall(r'data-sku="(\d+)"', html2)
                        link2 = re.findall(r'//item\.jd\.com/(\d+)\.html', html2)
                        new_skus = set(sku2 + link2)
                        for sku in new_skus:
                            if not any(p["sku_id"] == sku for p in products):
                                products.append({"sku_id": sku, "category": cat_name, "source": "list"})
                        print(f"  第{pg}页: +{len(new_skus)} SKU")
                    except Exception as e:
                        print(f"  第{pg}页异常: {str(e)[:60]}")
                        break

            except Exception as e:
                print(f"  ✗ 异常: {str(e)[:100]}")

        # 尝试访问几个详情页
        print(f"\n--- 详情页测试 ---")
        if products:
            for i, prod in enumerate(products[:3]):
                sku = prod["sku_id"]
                detail_url = f"https://item.jd.com/{sku}.html"
                try:
                    page.goto(detail_url, timeout=20000, wait_until="domcontentloaded")
                    time.sleep(4)
                    current_url = page.url
                    title = page.title()
                    print(f"  SKU {sku}: {title[:60]}")

                    if "frequent" in current_url or "risk" in current_url:
                        print(f"    ✗ 被拦截")
                        continue

                    html = page.content()
                    # 提取商品名
                    name_match = re.search(r'<title>([^<]+)</title>', html)
                    if name_match:
                        prod["name"] = name_match.group(1).strip()

                    # 提取价格（从页面脚本中）
                    price_match = re.search(r'"price"\s*:\s*["\']?([\d.]+)', html)
                    if price_match:
                        prod["price"] = price_match.group(1)

                    # 提取品牌
                    brand_match = re.search(r'品牌[：:]\s*([^<"\']+)', html)
                    if brand_match:
                        prod["brand"] = brand_match.group(1).strip()[:50]

                    print(f"    name: {prod.get('name', 'N/A')[:50]}")
                    print(f"    price: {prod.get('price', 'N/A')}")

                    # 截图
                    try:
                        page.screenshot(path=str(DATA_DIR / f"detail_{sku}.png"))
                    except Exception:
                        pass

                except Exception as e:
                    print(f"  SKU {sku} 异常: {str(e)[:80]}")

        browser.close()

    # 保存结果
    result = {
        "method": "cookie_category_browse",
        "timestamp": datetime.now().isoformat(),
        "products_count": len(products),
        "api_responses_count": len(all_apis),
        "products": products[:100],
        "api_urls": [a["url"] for a in all_apis[:20]],
    }
    outfile = DATA_DIR / f"cookie_category_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    outfile.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"结果: {len(products)} 个商品, {len(all_apis)} 个 API 响应")
    print(f"文件: {outfile}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    scrape_by_category()
