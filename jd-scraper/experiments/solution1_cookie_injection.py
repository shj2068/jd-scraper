"""
方案1: Cookie 注入 + 浏览器自动化采集
流程:
  Phase A: 打开可见浏览器 → 用户手动登录京东 → 保存 Cookie
  Phase B: 加载 Cookie → 自动化搜索/列表/详情页 → 提取商品数据
"""
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
COOKIE_FILE = DATA_DIR / "jd_cookies.json"


def phase_a_save_cookies():
    """Phase A: 打开浏览器让用户登录，保存 Cookie"""
    from playwright.sync_api import sync_playwright

    print("=" * 60)
    print("方案1 Phase A: 登录京东并保存 Cookie")
    print("=" * 60)
    print()
    print("即将打开 Edge 浏览器，请在浏览器中完成京东登录。")
    print("登录成功后，回到此窗口按 Enter 键保存 Cookie。")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge",
            headless=False,  # 可见浏览器，用户需要手动登录
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        page = context.new_page()

        # 导航到京东首页
        page.goto("https://www.jd.com/", timeout=30000)
        print("✓ 已打开京东首页")
        print("  请在浏览器中点击「请登录」完成登录...")
        print()

        # 等待用户登录（自动检测，无需按 Enter）
        print("  请在浏览器中完成登录，脚本会自动检测登录状态...")
        print("  （如果 3 分钟内未完成，将自动保存当前 Cookie）")
        print()

        logged_in = False
        for check in range(36):  # 最多等 3 分钟（每 5 秒检查一次）
            time.sleep(5)
            current_cookies = context.cookies()
            cookie_names = [c["name"] for c in current_cookies]
            has_pin = any("pin" in n.lower() for n in cookie_names)
            has_key = any(k in cookie_names for k in ["wskey", "pt_key", "pt_pin"])
            if has_pin or has_key:
                print(f"  ✓ 检测到登录态！(第 {(check+1)*5} 秒)")
                logged_in = True
                cookies = current_cookies
                break
            if check % 6 == 5:
                print(f"  ... 已等待 {(check+1)*5} 秒，等待登录中")

        if not logged_in:
            print("  ⚠ 未自动检测到登录，保存当前 Cookie...")
            cookies = context.cookies()

        # 最终验证登录状态
        page.goto("https://www.jd.com/", timeout=15000)
        time.sleep(2)
        cookies = context.cookies()
        cookie_names = [c["name"] for c in cookies]
        has_pin = any("pin" in n.lower() for n in cookie_names)
        has_ws = "wskey" in cookie_names or "pt_key" in cookie_names

        print(f"\n  Cookie 数量: {len(cookies)}")
        print(f"  含 pin: {has_pin}")
        print(f"  含 wskey/pt_key: {has_ws}")

        if has_pin or has_ws:
            # 保存 Cookie
            cookie_data = {
                "saved_at": datetime.now().isoformat(),
                "cookies": cookies,
            }
            COOKIE_FILE.write_text(json.dumps(cookie_data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\n✓ Cookie 已保存到: {COOKIE_FILE}")
            print(f"  共 {len(cookies)} 个 Cookie")
        else:
            print("\n⚠ 未检测到登录态 Cookie，可能尚未登录。")
            print("  仍然保存当前 Cookie（可稍后重试）...")
            cookie_data = {
                "saved_at": datetime.now().isoformat(),
                "cookies": cookies,
            }
            COOKIE_FILE.write_text(json.dumps(cookie_data, ensure_ascii=False, indent=2), encoding="utf-8")

        browser.close()

    return has_pin or has_ws


def phase_b_scrape(keyword="轴承", max_pages=2):
    """Phase B: 使用保存的 Cookie 自动采集"""
    from playwright.sync_api import sync_playwright

    print("\n" + "=" * 60)
    print(f"方案1 Phase B: 使用 Cookie 自动采集「{keyword}」")
    print("=" * 60)

    if not COOKIE_FILE.exists():
        print("✗ Cookie 文件不存在，请先执行 Phase A 登录")
        return None

    # 加载 Cookie
    cookie_data = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
    cookies = cookie_data["cookies"]
    print(f"✓ 加载 {len(cookies)} 个 Cookie (保存于 {cookie_data['saved_at'][:19]})")

    products = []
    api_responses = []

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

        # 注入 Cookie
        context.add_cookies(cookies)
        print("✓ Cookie 已注入浏览器上下文")

        page = context.new_page()

        # 拦截 API 响应
        def handle_response(response):
            url = response.url
            ct = response.headers.get("content-type", "")
            if "json" in ct or "javascript" in ct:
                if any(kw in url for kw in ["search", "goods", "ware", "product", "list", "recommend"]):
                    try:
                        body = response.text()
                        if len(body) > 200:
                            api_responses.append({"url": url[:200], "size": len(body), "preview": body[:300]})
                    except Exception:
                        pass

        page.on("response", handle_response)

        # 1. 先访问首页验证登录态
        print("\n[1/4] 验证登录态...")
        try:
            page.goto("https://www.jd.com/", timeout=20000, wait_until="domcontentloaded")
            time.sleep(3)
            current_url = page.url
            title = page.title()
            print(f"  首页: {title} | {current_url[:80]}")

            # 检查是否被重定向到登录页
            if "passport" in current_url or "login" in current_url:
                print("  ✗ Cookie 已过期，被重定向到登录页")
                browser.close()
                return None
            print("  ✓ 登录态有效")
        except Exception as e:
            print(f"  ⚠ 首页加载异常: {str(e)[:100]}")

        # 2. 搜索页
        print(f"\n[2/4] 搜索「{keyword}」...")
        search_url = f"https://search.jd.com/Search?keyword={keyword}&enc=utf-8"
        try:
            page.goto(search_url, timeout=25000, wait_until="domcontentloaded")
            time.sleep(4)
            current_url = page.url
            title = page.title()
            print(f"  搜索页: {title}")
            print(f"  URL: {current_url[:100]}")

            if "passport" in current_url or "login" in current_url:
                print("  ✗ 搜索需要登录（Cookie 可能过期）")
            else:
                # 滚动加载
                for pos in [500, 1500, 3000]:
                    try:
                        page.evaluate(f"window.scrollTo(0, {pos})")
                        time.sleep(1.5)
                    except Exception:
                        break

                # 提取商品
                items = page.query_selector_all("[data-sku]")
                print(f"  [data-sku] 元素: {len(items)}")

                if len(items) == 0:
                    items = page.query_selector_all(".gl-item, .gl-i-wrap, .J_goodsList li, .goods-list-v2 .gl-item")
                    print(f"  其他选择器: {len(items)}")

                if len(items) == 0:
                    # 尝试从页面 HTML 中提取
                    html = page.content()
                    sku_matches = re.findall(r'data-sku="(\d+)"', html)
                    print(f"  HTML data-sku 匹配: {len(sku_matches)}")

                    # 尝试提取商品链接
                    link_matches = re.findall(r'//item\.jd\.com/(\d+)\.html', html)
                    print(f"  商品链接匹配: {len(link_matches)}")

                    for sku in set(link_matches[:30]):
                        products.append({
                            "sku_id": sku,
                            "source": "search",
                            "keyword": keyword,
                        })

                for item in items[:30]:
                    try:
                        sku = item.get_attribute("data-sku") or ""
                        name_el = item.query_selector(".p-name em, .p-name a em, .p-name a")
                        price_el = item.query_selector(".p-price strong i, .p-price i")
                        name = name_el.inner_text().strip() if name_el else ""
                        price = price_el.inner_text().strip() if price_el else ""
                        if sku:
                            products.append({
                                "sku_id": sku,
                                "name": name[:100],
                                "price": price,
                                "source": "search",
                                "keyword": keyword,
                            })
                    except Exception:
                        continue

                print(f"  提取商品: {len(products)}")

                # 翻页
                for pg in range(2, max_pages + 1):
                    try:
                        page.goto(f"{search_url}&page={pg}", timeout=20000, wait_until="domcontentloaded")
                        time.sleep(3)
                        if "passport" in page.url:
                            break
                        for pos in [500, 1500, 3000]:
                            try:
                                page.evaluate(f"window.scrollTo(0, {pos})")
                                time.sleep(1)
                            except Exception:
                                break
                        items = page.query_selector_all("[data-sku]")
                        for item in items[:30]:
                            try:
                                sku = item.get_attribute("data-sku") or ""
                                name_el = item.query_selector(".p-name em, .p-name a em")
                                price_el = item.query_selector(".p-price strong i, .p-price i")
                                name = name_el.inner_text().strip() if name_el else ""
                                price = price_el.inner_text().strip() if price_el else ""
                                if sku:
                                    products.append({"sku_id": sku, "name": name[:100], "price": price, "source": "search", "keyword": keyword})
                            except Exception:
                                continue
                        print(f"  第{pg}页: +{len(items)} items")
                    except Exception:
                        break

        except Exception as e:
            print(f"  ⚠ 搜索异常: {str(e)[:100]}")

        # 3. 列表页
        print("\n[3/4] 访问列表页...")
        try:
            page.goto("https://list.jd.com/list.html?cat=670,671,672", timeout=20000, wait_until="domcontentloaded")
            time.sleep(5)
            current_url = page.url
            title = page.title()
            print(f"  列表页: {title}")
            print(f"  URL: {current_url[:100]}")

            if "passport" not in current_url and "login" not in current_url and "frequent" not in current_url:
                for pos in [500, 1500, 3000]:
                    try:
                        page.evaluate(f"window.scrollTo(0, {pos})")
                        time.sleep(1.5)
                    except Exception:
                        break

                items = page.query_selector_all("[data-sku], .gl-item")
                html = page.content()
                sku_matches = re.findall(r'data-sku="(\d+)"', html)
                link_matches = re.findall(r'//item\.jd\.com/(\d+)\.html', html)
                print(f"  [data-sku]: {len(items)}, HTML sku: {len(sku_matches)}, HTML links: {len(link_matches)}")

                for sku in set(link_matches[:20]):
                    if not any(p["sku_id"] == sku for p in products):
                        products.append({"sku_id": sku, "source": "list"})
            else:
                print(f"  ✗ 列表页被拦截: {current_url[:80]}")
        except Exception as e:
            print(f"  ⚠ 列表异常: {str(e)[:100]}")

        # 4. 详情页（取第一个商品）
        print("\n[4/4] 访问详情页...")
        if products:
            test_sku = products[0]["sku_id"]
            detail_url = f"https://item.jd.com/{test_sku}.html"
            try:
                page.goto(detail_url, timeout=20000, wait_until="domcontentloaded")
                time.sleep(4)
                current_url = page.url
                title = page.title()
                print(f"  详情页 SKU={test_sku}: {title}")
                print(f"  URL: {current_url[:100]}")

                if "frequent" not in current_url and "passport" not in current_url:
                    # 提取详情
                    detail = {}
                    try:
                        name_el = page.query_selector(".sku-name, .itemInfo-wrap .sku-name, .product-intro .name")
                        if name_el:
                            detail["name"] = name_el.inner_text().strip()[:200]
                    except Exception:
                        pass
                    try:
                        price_el = page.query_selector(".p-price .price, .summary-price-wrap .price, .J-p-price")
                        if price_el:
                            detail["price"] = price_el.inner_text().strip()
                    except Exception:
                        pass

                    if detail:
                        products[0]["detail"] = detail
                        print(f"  ✓ 详情: {detail}")
                    else:
                        print("  ⚠ 未提取到详情")
                else:
                    print(f"  ✗ 详情页被拦截")
            except Exception as e:
                print(f"  ⚠ 详情异常: {str(e)[:100]}")
        else:
            print("  ⚠ 无商品可访问")

        # 保存截图
        try:
            page.goto(f"https://search.jd.com/Search?keyword={keyword}", timeout=15000, wait_until="domcontentloaded")
            time.sleep(3)
            page.screenshot(path=str(DATA_DIR / "cookie_search_result.png"))
            print("\n  ✓ 截图已保存: data/cookie_search_result.png")
        except Exception:
            pass

        browser.close()

    # 保存结果
    result = {
        "method": "cookie_injection",
        "keyword": keyword,
        "timestamp": datetime.now().isoformat(),
        "products_count": len(products),
        "api_responses_count": len(api_responses),
        "products": products[:50],
        "api_responses": api_responses[:10],
    }
    outfile = DATA_DIR / f"cookie_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    outfile.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'=' * 60}")
    print(f"结果: {len(products)} 个商品, {len(api_responses)} 个 API 响应")
    print(f"文件: {outfile}")
    print(f"{'=' * 60}")

    return result


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        phase_a_save_cookies()
    elif len(sys.argv) > 1 and sys.argv[1] == "scrape":
        keyword = sys.argv[2] if len(sys.argv) > 2 else "轴承"
        phase_b_scrape(keyword)
    else:
        print("用法:")
        print("  python cookie_injection.py login    # 打开浏览器登录并保存 Cookie")
        print("  python cookie_injection.py scrape   # 使用 Cookie 自动采集")
        print("  python cookie_injection.py scrape 电机  # 搜索指定关键词")


if __name__ == "__main__":
    main()
