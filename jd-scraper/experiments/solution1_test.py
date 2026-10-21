"""
方案1 快速测试: 无登录 Cookie 注入，验证匿名 Cookie 能否绕过部分限制
"""
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def test_anonymous_cookies():
    """测试: 仅访问首页获取匿名 Cookie，然后尝试搜索"""
    from playwright.sync_api import sync_playwright

    print("=" * 60)
    print("方案1 测试: 匿名 Cookie 注入")
    print("=" * 60)

    results = {}

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
            // 伪造更多指纹
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
            window.chrome = { runtime: {} };
        """)

        page = context.new_page()
        api_data = []

        def on_response(response):
            url = response.url
            ct = response.headers.get("content-type", "")
            if ("json" in ct or "javascript" in ct) and response.status == 200:
                if any(kw in url.lower() for kw in ["search", "ware", "product", "goods", "recommend", "category"]):
                    try:
                        body = response.text()
                        if len(body) > 100:
                            api_data.append({"url": url[:200], "size": len(body), "body_preview": body[:500]})
                    except Exception:
                        pass

        page.on("response", on_response)

        # Step 1: 访问首页获取 Cookie
        print("\n[1] 访问首页获取 Cookie...")
        try:
            page.goto("https://www.jd.com/", timeout=20000, wait_until="domcontentloaded")
            time.sleep(4)
            cookies = context.cookies()
            print(f"  首页 Cookie: {len(cookies)} 个")
            for c in cookies[:10]:
                print(f"    {c['name']}: {c['value'][:30]}...")
            results["homepage_cookies"] = len(cookies)
            results["homepage_url"] = page.url
        except Exception as e:
            print(f"  ✗ {str(e)[:100]}")

        # Step 2: 尝试搜索（不登录）
        print("\n[2] 尝试搜索「轴承」...")
        try:
            page.goto("https://search.jd.com/Search?keyword=轴承&enc=utf-8", timeout=20000, wait_until="domcontentloaded")
            time.sleep(5)
            url = page.url
            title = page.title()
            print(f"  结果: {title}")
            print(f"  URL: {url[:120]}")

            is_login = "passport" in url or "login" in url
            is_verify = "验证" in title or "captcha" in url.lower()
            results["search_redirect"] = "login" if is_login else ("verify" if is_verify else "ok")

            if not is_login and not is_verify:
                # 滚动
                for pos in [500, 1500, 3000]:
                    try:
                        page.evaluate(f"window.scrollTo(0, {pos})")
                        time.sleep(1.5)
                    except Exception:
                        break

                html = page.content()
                sku_matches = re.findall(r'data-sku="(\d+)"', html)
                link_matches = re.findall(r'//item\.jd\.com/(\d+)\.html', html)
                img_matches = re.findall(r'//img\d+\.360buyimg\.com/[^"\']+', html)
                print(f"  data-sku: {len(sku_matches)}")
                print(f"  商品链接: {len(link_matches)}")
                print(f"  商品图片: {len(img_matches)}")
                results["search_skus"] = len(sku_matches)
                results["search_links"] = len(link_matches)
                results["search_images"] = len(img_matches)

                # 保存搜索页 HTML
                (DATA_DIR / "s1_search.html").write_text(html[:50000], encoding="utf-8")
                page.screenshot(path=str(DATA_DIR / "s1_search.png"))
            else:
                page.screenshot(path=str(DATA_DIR / "s1_search_blocked.png"))
                print(f"  ✗ 被拦截: {'登录' if is_login else '验证'}")
        except Exception as e:
            print(f"  ⚠ {str(e)[:100]}")
            results["search_error"] = str(e)[:100]

        # Step 3: 尝试列表页
        print("\n[3] 尝试列表页...")
        time.sleep(2)
        try:
            page.goto("https://list.jd.com/list.html?cat=670,671,672", timeout=20000, wait_until="domcontentloaded")
            time.sleep(5)
            url = page.url
            title = page.title()
            print(f"  结果: {title}")
            print(f"  URL: {url[:120]}")

            is_login = "passport" in url or "login" in url
            is_freq = "frequent" in url
            results["list_redirect"] = "login" if is_login else ("freq" if is_freq else "ok")

            if not is_login and not is_freq:
                for pos in [500, 1500, 3000]:
                    try:
                        page.evaluate(f"window.scrollTo(0, {pos})")
                        time.sleep(1.5)
                    except Exception:
                        break

                html = page.content()
                sku_matches = re.findall(r'data-sku="(\d+)"', html)
                link_matches = re.findall(r'//item\.jd\.com/(\d+)\.html', html)
                # 检查 React 渲染的数据
                json_matches = re.findall(r'"skuId"\s*:\s*"?(\d+)"?', html)
                print(f"  data-sku: {len(sku_matches)}")
                print(f"  商品链接: {len(link_matches)}")
                print(f"  skuId JSON: {len(json_matches)}")
                results["list_skus"] = len(sku_matches)
                results["list_links"] = len(link_matches)
                results["list_json_skus"] = len(json_matches)
                page.screenshot(path=str(DATA_DIR / "s1_list.png"))
            else:
                page.screenshot(path=str(DATA_DIR / "s1_list_blocked.png"))
                print(f"  ✗ 被拦截")
        except Exception as e:
            print(f"  ⚠ {str(e)[:100]}")

        # Step 4: 尝试移动版
        print("\n[4] 尝试移动版搜索...")
        time.sleep(2)
        try:
            # 创建移动版上下文
            mobile_ctx = browser.new_context(
                viewport={"width": 375, "height": 812},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            )
            mobile_ctx.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)
            # 复制 Cookie
            mobile_ctx.add_cookies(cookies)

            mobile_page = mobile_ctx.new_page()
            mobile_page.goto("https://so.m.jd.com/ware/search.action?keyword=轴承", timeout=20000, wait_until="domcontentloaded")
            time.sleep(5)
            url = mobile_page.url
            title = mobile_page.title()
            print(f"  结果: {title}")
            print(f"  URL: {url[:120]}")

            is_risk = "risk" in url or "cfe.m.jd.com" in url
            is_login = "passport" in url or "login" in url
            results["mobile_redirect"] = "risk" if is_risk else ("login" if is_login else "ok")

            if not is_risk and not is_login:
                html = mobile_page.content()
                sku_matches = re.findall(r'"skuId"\s*:\s*"?(\d+)"?', html)
                ware_matches = re.findall(r'"wareId"\s*:\s*"?(\d+)"?', html)
                link_matches = re.findall(r'//item\.m\.jd\.com/product/(\d+)', html)
                print(f"  skuId: {len(sku_matches)}")
                print(f"  wareId: {len(ware_matches)}")
                print(f"  商品链接: {len(link_matches)}")
                results["mobile_skus"] = len(sku_matches) + len(ware_matches)
                results["mobile_links"] = len(link_matches)
                mobile_page.screenshot(path=str(DATA_DIR / "s1_mobile.png"))
            else:
                mobile_page.screenshot(path=str(DATA_DIR / "s1_mobile_blocked.png"))
                print(f"  ✗ 被拦截: {'风控' if is_risk else '登录'}")

            mobile_ctx.close()
        except Exception as e:
            print(f"  ⚠ {str(e)[:100]}")

        # Step 5: 尝试京东 H5 页面（可能限制更松）
        print("\n[5] 尝试 H5 搜索接口...")
        try:
            h5_url = "https://api.m.jd.com/api"
            params = {
                "appid": "search_m.jd.com",
                "functionId": "search_auto_complete",
                "client": "wh5",
                "body": json.dumps({"keyword": "轴承", "page": 1, "pageSize": 20}),
            }
            resp = page.request.post(h5_url, params=params)
            text = resp.text()
            print(f"  响应: {len(text)} bytes")
            try:
                j = json.loads(text)
                print(f"  JSON keys: {list(j.keys())[:10]}")
                if "data" in j:
                    print(f"  data keys: {list(j['data'].keys())[:10] if isinstance(j['data'], dict) else type(j['data'])}")
                results["h5_api"] = {"size": len(text), "keys": list(j.keys())[:10]}
            except Exception:
                print(f"  非JSON: {text[:200]}")
        except Exception as e:
            print(f"  ⚠ {str(e)[:100]}")

        # 汇总 API 拦截数据
        print(f"\n[汇总] 拦截到 {len(api_data)} 个相关 API 响应")
        for i, d in enumerate(api_data[:5]):
            print(f"  [{i+1}] {d['url'][:100]} ({d['size']} bytes)")

        browser.close()

    # 保存结果
    results["timestamp"] = datetime.now().isoformat()
    results["api_intercepted"] = len(api_data)
    outfile = DATA_DIR / "solution1_test_result.json"
    outfile.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'=' * 60}")
    print(f"方案1 测试结果已保存: {outfile}")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return results


if __name__ == "__main__":
    test_anonymous_cookies()
