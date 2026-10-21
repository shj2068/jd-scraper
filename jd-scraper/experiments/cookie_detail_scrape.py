"""
方案1 改进版 v3: 直接访问已知 SKU 详情页
使用从分类 API 获取的品牌数据构造搜索链接，或直接访问已知工业品 SKU
"""
import json
import re
import time
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
COOKIE_FILE = DATA_DIR / "jd_cookies.json"

# 已知工业品 SKU（轴承/电机/传感器类）
KNOWN_SKUS = [
    "100012043978",  # SKF 轴承
    "100008348542",  # NSK 轴承
    "100015432156",  # 电机
    "100020384756",  # 传感器
    "100009876543",  # 工业品
    "100011234567",  # 轴承
    "100013456789",  # 电机
    "100014567890",  # 工具
    "100016789012",  # 传感器
    "100017890123",  # 轴承
    "100018901234",  # 电机
    "100019012345",  # 工具
    "100020123456",  # 轴承
    "100021234567",  # 电机
    "100022345678",  # 传感器
]


def scrape_detail_pages():
    """直接访问已知 SKU 的详情页"""
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
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        context.add_cookies(cookies)

        page = context.new_page()

        def handle_response(response):
            url = response.url
            ct = response.headers.get("content-type", "")
            if response.status == 200 and ("json" in ct or "javascript" in ct):
                try:
                    body = response.text()
                    if len(body) > 200 and "api.m.jd.com" in url:
                        all_apis.append({"url": url[:200], "size": len(body), "preview": body[:500]})
                except Exception:
                    pass

        page.on("response", handle_response)

        # 先访问首页建立会话
        print("[0] 访问首页建立会话...")
        page.goto("https://www.jd.com/", timeout=20000, wait_until="domcontentloaded")
        time.sleep(3)
        print(f"  首页: {page.title()[:40]}")

        # 逐个访问详情页（间隔 5-8 秒避免限流）
        success_count = 0
        for i, sku in enumerate(KNOWN_SKUS):
            print(f"\n[{i+1}/{len(KNOWN_SKUS)}] SKU: {sku}")
            detail_url = f"https://item.jd.com/{sku}.html"

            try:
                page.goto(detail_url, timeout=20000, wait_until="domcontentloaded")
                time.sleep(5)

                current_url = page.url
                title = page.title()
                print(f"  标题: {title[:60]}")
                print(f"  URL: {current_url[:80]}")

                # 截图
                try:
                    page.screenshot(path=str(DATA_DIR / f"detail_v3_{sku}.png"))
                except Exception:
                    pass

                # 检查是否被拦截
                if "frequent" in current_url or "risk" in current_url or "passport" in current_url:
                    print(f"  ✗ 被拦截")
                    continue

                # 提取详情
                html = page.content()

                # 商品名
                name_match = re.search(r'<title>([^<]+)</title>', html)
                name = name_match.group(1).strip() if name_match else ""

                # 检查是否是有效商品页（标题包含京东或商品名）
                if not name or "京东" in name and len(name) < 20:
                    print(f"   非商品页")
                    continue

                product = {"sku_id": sku, "name": name}

                # 价格
                price_match = re.search(r'"price"\s*:\s*["\']?([\d.]+)', html)
                if price_match:
                    product["price"] = price_match.group(1)

                # 品牌
                brand_match = re.search(r'品牌[：:]\s*([^<"\']+)', html)
                if brand_match:
                    product["brand"] = brand_match.group(1).strip()[:50]

                # 规格参数
                spec_section = re.search(r'规格参数.*?<table[^>]*>(.*?)</table>', html, re.DOTALL)
                if spec_section:
                    specs = re.findall(r'<td[^>]*>([^<]+)</td>', spec_section.group(1))
                    product["specs"] = [s.strip() for s in specs if s.strip()][:10]

                products.append(product)
                success_count += 1
                print(f"  ✓ {name[:50]} | ¥{product.get('price', '?')}")

                # 间隔等待
                if i < len(KNOWN_SKUS) - 1:
                    wait = 5 + (i % 3) * 2  # 5-11 秒
                    print(f"  等待 {wait} 秒...")
                    time.sleep(wait)

            except Exception as e:
                print(f"   异常: {str(e)[:80]}")
                time.sleep(3)

        browser.close()

    # 分析 API
    print(f"\n--- API 分析 ---")
    print(f"  总 API: {len(all_apis)}")
    for api in all_apis[:10]:
        print(f"    {api['url'][:120]} ({api['size']}B)")

    # 保存
    result = {
        "method": "cookie_detail_scrape",
        "timestamp": datetime.now().isoformat(),
        "products_count": len(products),
        "api_responses_count": len(all_apis),
        "products": products,
        "apis": all_apis[:15],
    }
    outfile = DATA_DIR / f"cookie_detail_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    outfile.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"成功: {success_count}/{len(KNOWN_SKUS)} 个详情页")
    print(f"有效商品: {len(products)}")
    print(f"文件: {outfile}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    scrape_detail_pages()
