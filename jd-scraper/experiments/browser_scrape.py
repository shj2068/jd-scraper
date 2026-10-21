"""
京东浏览器自动化采集 - Playwright + Edge
拦截 XHR 请求，抓取商品搜索/详情/评价数据
"""
import json
import os
import re
import time
from datetime import datetime
from urllib.parse import urlencode, urlparse, parse_qs
from playwright.sync_api import sync_playwright

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 存储拦截到的 API 响应
captured_apis = []
captured_responses = []


def on_response(response):
    """拦截所有响应，筛选有价值的 API"""
    url = response.url
    status = response.status
    ct = response.headers.get("content-type", "")

    # 只关注 JSON/JSONP 响应
    is_json = "json" in ct or "javascript" in ct
    is_api = any(kw in url for kw in [
        "api.m.jd.com", "search.jd.com", "p.3.cn", "pe.3.cn",
        "cd.jd.com", "club.jd.com", "comment", "price",
        "ware-detail", "item-soa", "searchSoa", "list.jd.com",
        "re.jd.com", "dsp.jd.com", "im.jd.com",
        "wq.jd.com", "m.jd.com", "api.jd.com",
    ])

    if is_api and is_json and status == 200:
        try:
            body = response.text()
            entry = {
                "url": url[:500],
                "status": status,
                "content_type": ct,
                "size": len(body),
                "timestamp": datetime.now().isoformat(),
            }
            captured_apis.append(entry)

            # 尝试解析 JSON
            text = body.strip()
            # 处理 JSONP: callback({...})
            m = re.match(r'^[a-zA-Z_]\w*\((.*)\);?$', text, re.DOTALL)
            if m:
                text = m.group(1)
            try:
                data = json.loads(text)
                captured_responses.append({
                    "url": url[:500],
                    "data": data,
                    "size": len(body),
                })
            except json.JSONDecodeError:
                # 保存前 2KB 样本
                captured_responses.append({
                    "url": url[:500],
                    "raw_preview": text[:2000],
                    "size": len(body),
                })
        except Exception as e:
            pass


def extract_search_dom(page):
    """从搜索页面 DOM 提取商品数据"""
    products = []
    try:
        # 等待商品列表加载
        page.wait_for_selector(".gl-item, .J_goodsList li, .goods-list-v2 li", timeout=8000)
        time.sleep(2)  # 额外等待动态加载

        # 提取商品元素
        items = page.query_selector_all(".gl-item, .J_goodsList li[data-sku]")
        for item in items[:60]:
            try:
                sku = item.get_attribute("data-sku") or ""
                name_el = item.query_selector(".p-name a em, .p-name em")
                name = name_el.inner_text().strip() if name_el else ""
                price_el = item.query_selector(".p-price strong i, .p-price i")
                price = price_el.inner_text().strip() if price_el else ""
                shop_el = item.query_selector(".p-shop a, .p-shopnum a")
                shop = shop_el.inner_text().strip() if shop_el else ""
                comment_el = item.query_selector(".p-commit a")
                comments = comment_el.inner_text().strip() if comment_el else ""
                link = ""
                if sku:
                    link = f"https://item.jd.com/{sku}.html"

                if name or sku:
                    products.append({
                        "sku": sku,
                        "name": name[:200],
                        "price": price,
                        "shop": shop,
                        "comments": comments,
                        "link": link,
                    })
            except Exception:
                continue
    except Exception as e:
        print(f"  DOM 提取异常: {e}")
    return products


def extract_detail_dom(page):
    """从商品详情页 DOM 提取数据"""
    info = {}
    try:
        page.wait_for_selector(".sku-name, .itemInfo-wrap", timeout=8000)
        time.sleep(1)

        # 商品名称
        name_el = page.query_selector(".sku-name, .itemInfo-wrap .title")
        if name_el:
            info["name"] = name_el.inner_text().strip()

        # 价格
        price_el = page.query_selector(".p-price .price, .summary-price-wrap .price")
        if price_el:
            info["price"] = price_el.inner_text().strip()

        # 品牌
        brand_el = page.query_selector("#parameter-brand li, .p-parameter-list li:first-child")
        if brand_el:
            info["brand"] = brand_el.inner_text().strip()

        # 参数列表
        params = []
        param_els = page.query_selector_all(".p-parameter-list li, #parameter-brand li")
        for el in param_els[:20]:
            t = el.inner_text().strip()
            if t:
                params.append(t)
        if params:
            info["params"] = params

        # 评价数
        comment_el = page.query_selector(".comment-count a, .commtab-count")
        if comment_el:
            info["comment_count"] = comment_el.inner_text().strip()

    except Exception as e:
        print(f"  详情提取异常: {e}")
    return info


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("=" * 60)
    print("京东浏览器自动化采集")
    print(f"时间: {datetime.now().isoformat()}")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        page = context.new_page()
        page.on("response", on_response)

        # ====== Phase 1: 首页探索 ======
        print("\n[Phase 1] 访问京东首页...")
        try:
            page.goto("https://www.jd.com", timeout=20000, wait_until="domcontentloaded")
            time.sleep(3)
            print(f"  标题: {page.title()}")
            print(f"  拦截到 {len(captured_apis)} 个 API 请求")
        except Exception as e:
            print(f"  首页加载失败: {e}")

        # ====== Phase 2: 搜索商品 ======
        search_keywords = ["轴承", "电机", "PLC控制器", "减速机", "传感器"]
        all_search_products = []

        for kw in search_keywords:
            print(f"\n[Phase 2] 搜索: {kw}")
            captured_apis_before = len(captured_apis)
            captured_resp_before = len(captured_responses)
            try:
                url = f"https://search.jd.com/Search?keyword={kw}&enc=utf-8"
                page.goto(url, timeout=20000, wait_until="domcontentloaded")
                time.sleep(3)

                # 滚动页面触发懒加载
                for scroll_y in [500, 1500, 3000, 5000]:
                    page.evaluate(f"window.scrollTo(0, {scroll_y})")
                    time.sleep(0.5)

                products = extract_search_dom(page)
                new_apis = len(captured_apis) - captured_apis_before
                new_resps = len(captured_responses) - captured_resp_before

                print(f"  DOM 提取: {len(products)} 个商品")
                print(f"  新增 API 拦截: {new_apis} 个, 响应: {new_resps} 个")

                for prod in products:
                    prod["keyword"] = kw
                all_search_products.extend(products)

                # 保存搜索截图
                safe_kw = kw.replace("/", "_")
                page.screenshot(path=os.path.join(DATA_DIR, f"search_{safe_kw}.png"), full_page=False)

            except Exception as e:
                print(f"  搜索失败: {e}")

        # ====== Phase 3: 商品详情页 ======
        detail_products = []
        # 从搜索结果中取前 5 个有 SKU 的商品
        skus_to_visit = []
        seen_skus = set()
        for prod in all_search_products:
            if prod.get("sku") and prod["sku"] not in seen_skus:
                seen_skus.add(prod["sku"])
                skus_to_visit.append(prod["sku"])
            if len(skus_to_visit) >= 5:
                break

        for sku in skus_to_visit:
            print(f"\n[Phase 3] 商品详情: SKU {sku}")
            captured_apis_before = len(captured_apis)
            try:
                url = f"https://item.jd.com/{sku}.html"
                page.goto(url, timeout=20000, wait_until="domcontentloaded")
                time.sleep(2)

                # 滚动
                for scroll_y in [300, 800, 1500]:
                    page.evaluate(f"window.scrollTo(0, {scroll_y})")
                    time.sleep(0.3)

                detail = extract_detail_dom(page)
                detail["sku"] = sku
                detail["url"] = url
                new_apis = len(captured_apis) - captured_apis_before
                print(f"  详情: {detail.get('name', 'N/A')[:60]}")
                print(f"  价格: {detail.get('price', 'N/A')}")
                print(f"  新增 API: {new_apis} 个")
                detail_products.append(detail)

            except Exception as e:
                print(f"  详情失败: {e}")

        # ====== Phase 4: 分类导航页 (list.jd.com) ======
        print(f"\n[Phase 4] 分类列表页...")
        cat_ids = [
            ("670", "671", "672"),  # 电脑/办公/笔记本
            ("670", "671", "673"),  # 电脑/办公/台式机
            ("737", "738", "739"),  # 手机/通讯/手机
            ("737", "738", "2694"), # 手机/通讯/对讲机
        ]
        cat_products = []
        for cid in cat_ids:
            cat_url = f"https://list.jd.com/list.html?cat={','.join(cid)}"
            captured_before = len(captured_apis)
            try:
                page.goto(cat_url, timeout=15000, wait_until="domcontentloaded")
                time.sleep(3)
                for scroll_y in [500, 1500, 3000]:
                    page.evaluate(f"window.scrollTo(0, {scroll_y})")
                    time.sleep(0.5)

                products = extract_search_dom(page)
                new_apis = len(captured_apis) - captured_before
                print(f"  分类 {cid}: {len(products)} 商品, {new_apis} API")
                for prod in products:
                    prod["cat"] = cid
                cat_products.extend(products)

            except Exception as e:
                print(f"  分类失败: {e}")

        # ====== 汇总 ======
        browser.close()

    # 保存拦截到的 API 列表
    api_log = os.path.join(DATA_DIR, f"intercepted_apis_{ts}.json")
    with open(api_log, "w", encoding="utf-8") as f:
        json.dump(captured_apis, f, ensure_ascii=False, indent=2)
    print(f"\n拦截 API 日志: {len(captured_apis)} 条 → {api_log}")

    # 保存拦截到的 API 响应
    resp_log = os.path.join(DATA_DIR, f"intercepted_responses_{ts}.json")
    with open(resp_log, "w", encoding="utf-8") as f:
        json.dump(captured_responses, f, ensure_ascii=False, indent=2)
    print(f"拦截响应数据: {len(captured_responses)} 条 → {resp_log}")

    # 保存搜索结果
    search_file = os.path.join(DATA_DIR, f"search_products_{ts}.json")
    with open(search_file, "w", encoding="utf-8") as f:
        json.dump(all_search_products, f, ensure_ascii=False, indent=2)
    print(f"搜索商品: {len(all_search_products)} 条 → {search_file}")

    # 保存详情
    detail_file = os.path.join(DATA_DIR, f"detail_products_{ts}.json")
    with open(detail_file, "w", encoding="utf-8") as f:
        json.dump(detail_products, f, ensure_ascii=False, indent=2)
    print(f"商品详情: {len(detail_products)} 条 → {detail_file}")

    # 保存分类列表
    cat_file = os.path.join(DATA_DIR, f"category_products_{ts}.json")
    with open(cat_file, "w", encoding="utf-8") as f:
        json.dump(cat_products, f, ensure_ascii=False, indent=2)
    print(f"分类商品: {len(cat_products)} 条 → {cat_file}")

    # 汇总报告
    summary = {
        "timestamp": ts,
        "browser": "Microsoft Edge (via Playwright)",
        "total_intercepted_apis": len(captured_apis),
        "total_intercepted_responses": len(captured_responses),
        "search_keywords": search_keywords,
        "search_products_count": len(all_search_products),
        "detail_products_count": len(detail_products),
        "category_products_count": len(cat_products),
        "unique_skus_searched": len(set(p.get("sku") for p in all_search_products if p.get("sku"))),
        "unique_skus_detailed": len(skus_to_visit),
        "api_domains": list(set(
            urlparse(a["url"]).netloc for a in captured_apis if a.get("url")
        )),
    }
    summary_file = os.path.join(DATA_DIR, f"browser_scrape_summary_{ts}.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print("采集汇总:")
    print(f"  拦截 API 请求: {len(captured_apis)} 个")
    print(f"  拦截 API 响应: {len(captured_responses)} 个")
    print(f"  搜索商品: {len(all_search_products)} 个")
    print(f"  商品详情: {len(detail_products)} 个")
    print(f"  分类商品: {len(cat_products)} 个")
    print(f"  API 域名: {summary['api_domains']}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
