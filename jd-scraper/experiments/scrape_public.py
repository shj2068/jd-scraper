#!/usr/bin/env python3
"""京东公开页面数据采集 - 直接抓取 HTML 内容提取数据"""
import httpx, re, json, sys, time
from pathlib import Path
from datetime import datetime
from html.parser import HTMLParser

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

results = {"pages": [], "apis": [], "products": []}

print("=" * 70)
print(f"  京东公开页面数据采集 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

client = httpx.Client(timeout=15.0, headers=HEADERS, follow_redirects=True)

# ── 阶段 1: 京东搜索结果页 ─────────────────────────────────────────
print("\n[阶段 1] 京东搜索结果页 search.jd.com")
try:
    r = client.get("https://search.jd.com/Search", params={"keyword": "轴承", "enc": "utf-8"})
    print(f"  status={r.status_code}, size={len(r.text)}")
    # 提取 title
    title = re.search(r'<title>(.*?)</title>', r.text)
    print(f"  title: {title.group(1) if title else '(无)'}")
    # 提取商品数据 - JD 搜索结果通常在 script 标签中以 JSON 形式存在
    # 搜索 gl-item 或 data-sku 模式
    skus = re.findall(r'data-sku=["\'](\d+)["\']', r.text)
    print(f"  商品 SKU 数量: {len(skus)}")
    if skus:
        print(f"  SKU 示例: {skus[:5]}")
    # 搜索商品名称
    product_names = re.findall(r'<div class="p-name[^"]*">\s*<a[^>]*>(.*?)</a>', r.text, re.DOTALL)
    if not product_names:
        product_names = re.findall(r'class="p-name[^"]*"[^>]*>(.*?)</em>', r.text, re.DOTALL)
    print(f"  商品名称数量: {len(product_names)}")
    for name in product_names[:3]:
        clean = re.sub(r'<[^>]+>', '', name).strip()
        if clean:
            print(f"    - {clean[:80]}")
    # 提取价格
    prices = re.findall(r'<strong class="p-price"[^>]*>\s*<i>([\d.]+)</i>', r.text)
    print(f"  价格数量: {len(prices)}")
    for p in prices[:5]:
        print(f"    ¥{p}")
    # 提取店铺
    shops = re.findall(r'<a class="p-shop[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL)
    print(f"  店铺数量: {len(shops)}")
    for s in shops[:3]:
        clean = re.sub(r'<[^>]+>', '', s).strip()
        if clean:
            print(f"    - {clean}")
    results["pages"].append({"url": "search.jd.com", "status": r.status_code, "skus": len(skus), "products": len(product_names)})
    results["products"].extend([{"sku": s, "name": re.sub(r'<[^>]+>', '', product_names[i]).strip() if i < len(product_names) else ""} for i, s in enumerate(skus[:10])])
except Exception as e:
    print(f"  ERROR: {e}")

time.sleep(0.5)

# ── 阶段 2: 京东商品详情页 ─────────────────────────────────────────
print("\n[阶段 2] 京东商品详情页 item.jd.com")
TEST_SKUS = ["100012043978", "100009375439", "100038014896"]  # 一些可能的工业品 SKU
for sku in TEST_SKUS:
    try:
        r = client.get(f"https://item.jd.com/{sku}.html")
        title = re.search(r'<title>(.*?)</title>', r.text)
        title_text = title.group(1) if title else "(无)"
        print(f"  SKU {sku}: status={r.status_code}, size={len(r.text)}, title={title_text[:60]}")
        # 提取价格
        price_match = re.search(r'"p":\s*"([\d.]+)"', r.text)
        if price_match:
            print(f"    价格: ¥{price_match.group(1)}")
        # 提取商品名称
        name_match = re.search(r'<div class="sku-name"[^>]*>\s*(.*?)\s*</div>', r.text, re.DOTALL)
        if name_match:
            print(f"    名称: {name_match.group(1).strip()[:80]}")
        # 提取店铺名
        shop_match = re.search(r'<a class="p-shop-name"[^>]*>(.*?)</a>', r.text, re.DOTALL)
        if shop_match:
            print(f"    店铺: {shop_match.group(1).strip()}")
        results["pages"].append({"url": f"item.jd.com/{sku}", "status": r.status_code, "title": title_text[:60]})
    except Exception as e:
        print(f"  SKU {sku}: ERROR {e}")
    time.sleep(0.3)

# ── 阶段 3: 京东分类导航 ──────────────────────────────────────────
print("\n[阶段 3] 京东分类导航页面")
try:
    r = client.get("https://www.jd.com/allSort.aspx")
    print(f"  status={r.status_code}, size={len(r.text)}")
    # 提取分类
    categories = re.findall(r'<a[^>]*href="[^"]*"[^>]*>(.*?)</a>', r.text[:20000])
    clean_cats = [re.sub(r'<[^>]+>', '', c).strip() for c in categories if len(re.sub(r'<[^>]+>', '', c).strip()) > 1]
    print(f"  分类数量: {len(clean_cats)}")
    for cat in clean_cats[:15]:
        print(f"    {cat}")
    results["pages"].append({"url": "jd.com/allSort", "categories": len(clean_cats)})
except Exception as e:
    print(f"  ERROR: {e}")

time.sleep(0.5)

# ── 阶段 4: 京东排行榜 ──────────────────────────────────────────
print("\n[阶段 4] 京东排行榜 (re.jd.com)")
try:
    r = client.get("https://re.jd.com/cate/rank")
    print(f"  status={r.status_code}, size={len(r.text)}")
    title = re.search(r'<title>(.*?)</title>', r.text)
    print(f"  title: {title.group(1) if title else '(无)'}")
except Exception as e:
    print(f"  ERROR: {e}")

# ── 阶段 5: 用不同 appid 尝试 API ─────────────────────────────────
print("\n[阶段 5] 不同 appid/client 组合测试")
sys.path.insert(0, str(Path(__file__).parent))
from python.sign import generate_sign
from python.fingerprint import FingerprintGenerator

fp = FingerprintGenerator(platform="desktop")
uuid = fp.get_or_create_uuid()

# 尝试不同的 appid 和 client 组合
APPID_TESTS = [
    ("wh5", "h5", "1.0.0"),
    ("jdstoreh5", "h5", "1.0.0"),
    ("JD4iPhone", "iOS", "10.4.0"),
    ("jd_android", "android", "10.4.0"),
    ("pc", "pc", "1.0.0"),
    ("10058026", "h5", "1.0.0"),
]

FIDS_TO_TEST = [
    ("searchAutoComplete", {"keyword": "轴承"}),
    ("getSearchResult", {"keyword": "轴承", "page": "1", "pagesize": "5"}),
    ("bizSearchCategoryList", {"cid": "0"}),
]

for appid, client_type, version in APPID_TESTS:
    for fid, body in FIDS_TO_TEST[:2]:
        body_str = json.dumps(body, separators=(",", ":"))
        sign, t = generate_sign(
            function_id=fid, body=body_str, uuid=uuid,
            appid=appid, client=client_type, client_version=version
        )
        params = {
            "functionId": fid, "appid": appid, "client": client_type,
            "clientVersion": version, "t": t, "uuid": uuid, "sign": sign, "body": body_str,
        }
        try:
            r = client.get("https://api.m.jd.com/", params=params)
            data = r.json()
            code = data.get("code", "?")
            echo = data.get("echo", data.get("message", ""))
            has_data = bool(data.get("data") or data.get("result"))
            if has_data or code != 2:
                marker = "✓" if has_data else "✗"
                print(f"  {marker} appid={appid} client={client_type} | {fid}: code={code} echo={str(echo)[:40]}")
                if has_data:
                    print(f"    DATA: {json.dumps(data, ensure_ascii=False)[:200]}")
                    results["apis"].append({"appid": appid, "fid": fid, "code": code, "has_data": True})
        except Exception as e:
            pass
    time.sleep(0.2)

# ── 阶段 6: 京东工业品搜索 ──────────────────────────────────────
print("\n[阶段 6] 京东工业品搜索 (gong.jd.com / i.jd.com)")
for url in [
    "https://i.jd.com/search?keyword=轴承",
    "https://gong.jd.com/search?keyword=轴承",
    "https://list.jd.com/list.html?cat=6233,6257,6264",
]:
    try:
        r = client.get(url)
        title = re.search(r'<title>(.*?)</title>', r.text)
        title_text = title.group(1) if title else "(无)"
        print(f"  {url.split('?')[0].split('/')[-1]}: status={r.status_code}, size={len(r.text)}, title={title_text[:50]}")
        # 提取商品
        skus = re.findall(r'data-sku=["\'](\d+)["\']', r.text)
        if skus:
            print(f"    商品数: {len(skus)}, SKU: {skus[:5]}")
    except Exception as e:
        print(f"  ERROR: {e}")
    time.sleep(0.3)

client.close()

# ── 保存结果 ──────────────────────────────────────────────────────
output = Path(__file__).parent / "data" / f"public_scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
output.parent.mkdir(parents=True, exist_ok=True)
with open(output, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n" + "=" * 70)
print("  采集汇总")
print("=" * 70)
print(f"  页面: {len(results['pages'])} 个")
print(f"  API 成功: {len(results['apis'])} 个")
print(f"  商品: {len(results['products'])} 个")
print(f"  结果: {output}")
print("=" * 70)
