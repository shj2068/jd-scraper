"""
京东浏览器自动化采集 v2 - Playwright + Edge
修复: 搜索页重定向、执行上下文销毁
"""
import json
import os
import re
import time
from datetime import datetime
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

captured_apis = []
captured_responses = []


def on_response(response):
    url = response.url
    status = response.status
    ct = response.headers.get("content-type", "")
    is_json = "json" in ct or "javascript" in ct
    is_api = any(kw in url for kw in [
        "api.m.jd.com", "p.3.cn", "pe.3.cn", "cd.jd.com",
        "club.jd.com", "comment", "price", "ware-detail",
        "item-soa", "searchSoa", "wq.jd.com", "api.jd.com",
        "re.jd.com", "dsp.jd.com", "im.jd.com", "dc.3.cn",
    ])
    if is_api and is_json and status == 200:
        try:
            body = response.text()
            captured_apis.append({
                "url": url[:500],
                "status": status,
                "content_type": ct,
                "size": len(body),
                "timestamp": datetime.now().isoformat(),
            })
            text = body.strip()
            m = re.match(r'^[a-zA-Z_]\w*\((.*)\);?$', text, re.DOTALL)
            if m:
                text = m.group(1)
            try:
                data = json.loads(text)
                captured_responses.append({"url": url[:500], "data": data, "size": len(body)})
            except json.JSONDecodeError:
                captured_responses.append({"url": url[:500], "raw_preview": text[:2000], "size": len(body)})
        except Exception:
            pass


def safe_scroll(page, positions=[500, 1500, 3000, 5000]):
    """安全滚动，处理上下文销毁"""
    for pos in positions:
        try:
            page.evaluate(f"window.scrollTo(0, {pos})")
            time.sleep(0.8)
        except Exception:
            time.sleep(1)
            try:
                page.evaluate(f"window.scrollTo(0, {pos})")
                time.sleep(0.5)
            except Exception:
                break


def extract_products_from_dom(page):
    """从 DOM 提取商品数据，多种选择器兼容"""
    products = []
    # 尝试多种选择器
    selectors = [
        ".gl-item",
        ".J_goodsList li[data-sku]",
        "li[data-sku]",
        ".goods-list-v2 .gl-item",
        "#J_goodsList .gl-item",
    ]
    items = []
    for sel in selectors:
        try:
            items = page.query_selector_all(sel)
            if items:
                break
        except Exception:
            continue

    for item in items[:60]:
        try:
            sku = item.get_attribute("data-sku") or ""
            name_el = item.query_selector(".p-name a em, .p-name em, .p-name a")
            name = name_el.inner_text().strip() if name_el else ""
            price_el = item.query_selector(".p-price strong i, .p-price i, .p-price")
            price = price_el.inner_text().strip() if price_el else ""
            shop_el = item.query_selector(".p-shop a, .p-shopnum a")
            shop = shop_el.inner_text().strip() if shop_el else ""
            comment_el = item.query_selector(".p-commit a")
            comments = comment_el.inner_text().strip() if comment_el else ""
            link = f"https://item.jd.com/{sku}.html" if sku else ""
            if name or sku:
                products.append({
                    "sku": sku, "name": name[:200], "price": price,
                    "shop": shop, "comments": comments, "link": link,
                })
        except Exception:
            continue
    return products


def navigate_safe(page, url, timeout=25000):
    """安全导航，处理重定向和验证页"""
    try:
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        time.sleep(2)
        # 检查是否被重定向到验证页
        current_url = page.url
        title = page.title()
        if "验证" in title or "captcha" in current_url.lower():
            print(f"  ⚠ 触发验证页: {title}")
            return False
        # 等待页面稳定
        time.sleep(2)
        return True
    except Exception as e:
        print(f"  ⚠ 导航异常: {str(e)[:100]}")
        time.sleep(2)
        return True  # 继续尝试


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("=" * 60)
    print("京东浏览器自动化采集 v2")
    print(f"时间: {datetime.now().isoformat()}")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge",
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        # 注入反检测脚本
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        page = context.new_page()
        page.on("response", on_response)

        # ====== Phase 1: 首页 ======
        print("\n[Phase 1] 京东首页...")
        if navigate_safe(page, "https://www.jd.com"):
            print(f"  标题: {page.title()}")
            safe_scroll(page, [300, 800])
            print(f"  拦截 API: {len(captured_apis)} 个")

        # ====== Phase 2: 搜索 ======
        search_keywords = ["轴承", "电机", "PLC控制器", "减速机", "传感器"]
        all_search_products = []

        for kw in search_keywords:
            print(f"\n[Phase 2] 搜索: {kw}")
            apis_before = len(captured_apis)
            resps_before = len(captured_responses)
            try:
                ok = navigate_safe(page, f"https://search.jd.com/Search?keyword={kw}&enc=utf-8&wq={kw}")
                if not ok:
                    # 尝试移动版搜索
                    print(f"  尝试移动版搜索...")
                    ok = navigate_safe(page, f"https://so.m.jd.com/ware/search.action?keyword={kw}")
                    if not ok:
                        continue

                safe_scroll(page, [500, 1500, 3000, 5000, 8000])
                time.sleep(1)

                products = extract_products_from_dom(page)
                print(f"  DOM 提取: {len(products)} 商品")
                print(f"  新增 API: {len(captured_apis) - apis_before}, 响应: {len(captured_responses) - resps_before}")

                # 保存截图
                safe_kw = re.sub(r'[^\w]', '_', kw)
                page.screenshot(path=os.path.join(DATA_DIR, f"search_{safe_kw}.png"), full_page=False)

                for prod in products:
                    prod["keyword"] = kw
                all_search_products.extend(products)

            except Exception as e:
                print(f"  搜索失败: {str(e)[:150]}")

        # ====== Phase 3: 商品详情 ======
        detail_products = []
        skus_to_visit = []
        seen = set()
        for prod in all_search_products:
            sku = prod.get("sku")
            if sku and sku not in seen:
                seen.add(sku)
                skus_to_visit.append(sku)
            if len(skus_to_visit) >= 5:
                break

        for sku in skus_to_visit:
            print(f"\n[Phase 3] 详情: SKU {sku}")
            apis_before = len(captured_apis)
            try:
                ok = navigate_safe(page, f"https://item.jd.com/{sku}.html")
                if not ok:
                    continue
                safe_scroll(page, [300, 800, 1500])
                time.sleep(1)

                info = {"sku": sku, "url": f"https://item.jd.com/{sku}.html"}
                for sel, key in [
                    (".sku-name", "name"),
                    (".p-price .price, .summary-price-wrap .price", "price"),
                    ("#parameter-brand li", "brand"),
                    (".comment-count a", "comment_count"),
                ]:
                    try:
                        el = page.query_selector(sel)
                        if el:
                            info[key] = el.inner_text().strip()
                    except Exception:
                        pass

                # 参数列表
                params = []
                try:
                    for el in page.query_selector_all(".p-parameter-list li")[:15]:
                        t = el.inner_text().strip()
                        if t:
                            params.append(t)
                except Exception:
                    pass
                if params:
                    info["params"] = params

                print(f"  {info.get('name', 'N/A')[:50]} | ¥{info.get('price', '?')}")
                print(f"  新增 API: {len(captured_apis) - apis_before}")
                detail_products.append(info)

            except Exception as e:
                print(f"  详情失败: {str(e)[:100]}")

        # ====== Phase 4: 分类列表 ======
        print(f"\n[Phase 4] 分类列表页...")
        cat_pages = [
            ("670,671,672", "笔记本电脑"),
            ("737,738,739", "手机"),
            ("737,738,2694", "对讲机"),
            ("670,671,673", "台式机"),
        ]
        cat_products = []
        for cat_id, cat_name in cat_pages:
            apis_before = len(captured_apis)
            print(f"  分类: {cat_name} ({cat_id})")
            try:
                ok = navigate_safe(page, f"https://list.jd.com/list.html?cat={cat_id}")
                if not ok:
                    continue
                safe_scroll(page, [500, 1500, 3000, 5000])
                products = extract_products_from_dom(page)
                print(f"    {len(products)} 商品, API: {len(captured_apis) - apis_before}")
                for prod in products:
                    prod["cat_name"] = cat_name
                    prod["cat_id"] = cat_id
                cat_products.extend(products)
            except Exception as e:
                print(f"    失败: {str(e)[:80]}")

        browser.close()

    # ====== 保存数据 ======
    # API 日志
    with open(os.path.join(DATA_DIR, f"intercepted_apis_{ts}.json"), "w", encoding="utf-8") as f:
        json.dump(captured_apis, f, ensure_ascii=False, indent=2)

    # API 响应
    with open(os.path.join(DATA_DIR, f"intercepted_responses_{ts}.json"), "w", encoding="utf-8") as f:
        json.dump(captured_responses, f, ensure_ascii=False, indent=2)

    # 搜索结果
    with open(os.path.join(DATA_DIR, f"search_products_{ts}.json"), "w", encoding="utf-8") as f:
        json.dump(all_search_products, f, ensure_ascii=False, indent=2)

    # 详情
    with open(os.path.join(DATA_DIR, f"detail_products_{ts}.json"), "w", encoding="utf-8") as f:
        json.dump(detail_products, f, ensure_ascii=False, indent=2)

    # 分类
    with open(os.path.join(DATA_DIR, f"category_products_{ts}.json"), "w", encoding="utf-8") as f:
        json.dump(cat_products, f, ensure_ascii=False, indent=2)

    # 汇总
    api_domains = list(set(urlparse(a["url"]).netloc for a in captured_apis if a.get("url")))
    summary = {
        "timestamp": ts,
        "browser": "Microsoft Edge (Playwright)",
        "total_intercepted_apis": len(captured_apis),
        "total_intercepted_responses": len(captured_responses),
        "search_keywords": search_keywords,
        "search_products": len(all_search_products),
        "detail_products": len(detail_products),
        "category_products": len(cat_products),
        "unique_skus_searched": len(set(p["sku"] for p in all_search_products if p.get("sku"))),
        "unique_skus_detailed": len(skus_to_visit),
        "api_domains": api_domains,
    }
    with open(os.path.join(DATA_DIR, f"browser_scrape_summary_{ts}.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print("采集结果汇总:")
    print(f"  拦截 API: {len(captured_apis)} 个")
    print(f"  拦截响应: {len(captured_responses)} 个")
    print(f"  搜索商品: {len(all_search_products)} 个")
    print(f"  商品详情: {len(detail_products)} 个")
    print(f"  分类商品: {len(cat_products)} 个")
    print(f"  API 域名: {api_domains}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
