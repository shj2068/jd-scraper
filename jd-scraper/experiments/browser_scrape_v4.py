"""
京东数据采集 v4 - 公开 API 端点全面尝试
策略: 不依赖浏览器渲染，直接用 HTTP 请求尝试所有已知公开端点
"""
import json
import os
import re
import time
import httpx
from datetime import datetime
from urllib.parse import quote, unquote

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

HEADERS_PC = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.jd.com/",
}

results = {}


def try_api(name, url, method="GET", data=None, headers=None, timeout=10):
    """尝试一个 API 端点"""
    h = headers or HEADERS_PC
    print(f"\n  [{name}]")
    print(f"    URL: {url[:150]}")
    try:
        if method == "POST":
            r = httpx.post(url, data=data, headers=h, timeout=timeout, follow_redirects=True)
        else:
            r = httpx.get(url, headers=h, timeout=timeout, follow_redirects=True)

        ct = r.headers.get("content-type", "")
        text = r.text.strip()

        # 处理编码
        if "gbk" in ct.lower() or "gb2312" in ct.lower():
            try:
                text = r.content.decode("gbk")
            except Exception:
                pass

        # 处理 JSONP
        m = re.match(r'^[a-zA-Z_]\w*\((.*)\);?$', text, re.DOTALL)
        if m:
            text = m.group(1)

        # 尝试解析 JSON
        try:
            j = json.loads(text)
            size = len(text)
            keys = list(j.keys())[:8] if isinstance(j, dict) else f"list[{len(j)}]"
            print(f"    ✓ JSON: {size} bytes, keys={keys}")

            # 检查是否有实际数据
            has_data = False
            if isinstance(j, dict):
                for k in ["data", "result", "ware", "products", "items", "list"]:
                    if k in j:
                        v = j[k]
                        if isinstance(v, list) and len(v) > 0:
                            has_data = True
                            print(f"    ★ {k}: list[{len(v)}]")
                            if isinstance(v[0], dict):
                                print(f"      first keys: {list(v[0].keys())[:10]}")
                        elif isinstance(v, dict) and len(v) > 2:
                            has_data = True
                            print(f"    ★ {k}: dict keys={list(v.keys())[:10]}")
            return {"name": name, "status": "ok", "size": size, "keys": keys, "data": j, "has_product_data": has_data}
        except json.JSONDecodeError:
            # 非 JSON
            preview = text[:200]
            is_html = "<html" in text.lower() or "<!doctype" in text.lower()
            is_verify = "验证" in text or "captcha" in text.lower() or "plogin" in url
            print(f"    ✗ 非JSON: {len(text)} bytes, {'HTML' if is_html else 'text'}{'(验证页)' if is_verify else ''}")
            return {"name": name, "status": "not_json", "preview": preview}
    except Exception as e:
        print(f"    ✗ 错误: {str(e)[:100]}")
        return {"name": name, "status": "error", "error": str(e)}


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("=" * 60)
    print("京东公开 API 端点全面尝试 v4")
    print(f"时间: {datetime.now().isoformat()}")
    print("=" * 60)

    # ====== 1. 已知可用: dc.3.cn 分类树 ======
    print("\n[1] 分类导航树 (已知可用)")
    r = try_api("dc.3.cn/category/get", "https://dc.3.cn/category/get")
    if r and r.get("data"):
        results["category_tree"] = r["data"]

    # ====== 2. 价格 API ======
    print("\n[2] 价格查询 API")
    # 尝试几个已知的价格端点
    skus = "100012043978,100009060983,100008348680"
    try_api("p.3.cn", f"https://p.3.cn/prices/mgets?skuIds=J_{skus}")
    try_api("p.3.cn (peek)", f"https://p.3.cn/prices/peek?skuIds={skus}")

    # ====== 3. 评论 API ======
    print("\n[3] 评论 API")
    try_api("club.jd.com (100012043978)",
            f"https://club.jd.com/comment/productCommentSummaries.action?referenceIds={skus}")
    try_api("club.jd.com comments",
            f"https://club.jd.com/comment/productPageComments.action?productId=100012043978&score=0&sortType=5&page=0&pageSize=10")

    # ====== 4. 搜索建议/联想 ======
    print("\n[4] 搜索联想 API")
    try_api("searchAutoComplete",
            "https://api.m.jd.com/api?appid=search-pc-java&functionId=searchAutoComplete&client=pc&clientVersion=1.0.0&t=1791368200000&body=%7B%22keyword%22%3A%22%E8%BD%B4%E6%89%BF%22%7D")

    # ====== 5. 京东推荐 API ======
    print("\n[5] 推荐 API")
    try_api("re.jd.com rec",
            "https://re.jd.com/api/recommend/getRecommend?cid1=670&cid2=671&cid3=672&limit=20")
    try_api("re.jd.com cate",
            "https://re.jd.com/cate/cat_670_671_672.html")

    # ====== 6. 京东商品详情 (公开) ======
    print("\n[6] 商品详情端点")
    try_api("ware-detail.jd.com",
            "https://ware-detail.jd.com/detail?wareId=100012043978")
    try_api("item-soa.jd.com",
            "https://item-soa.jd.com/get?wareId=100012043978")
    try_api("cd.jd.com (desc)",
            f"https://cd.jd.com/description/channel?skuId=100012043978&mainSkuId=100012043978&cdn=2")

    # ====== 7. 京东排行榜 ======
    print("\n[7] 排行榜/热销 API")
    try_api("rank.jd.com",
            "https://rank.jd.com/rankData?cid1=670&cid2=671&cid3=672&page=1")
    try_api("hot.jd.com",
            "https://hot.jd.com/rank/getRankInfo?cid1=670&cid2=671&cid3=672")

    # ====== 8. 京东问答/评价 ======
    print("\n[8] 问答/评价")
    try_api("answer.jd.com",
            "https://answer.jd.com/question/list?wareId=100012043978&page=1&pageSize=10")

    # ====== 9. 京东店铺 ======
    print("\n[9] 店铺信息")
    try_api("shop.jd.com",
            "https://shop.jd.com/shop/info?shopId=1000000904")

    # ====== 10. 京东秒杀/促销 ======
    print("\n[10] 秒杀/促销")
    try_api("miaosha.jd.com",
            "https://miaosha.jd.com/list/flashBuy/0-0-0-0-0-1.html")
    try_api("prom.3.cn",
            "https://prom.3.cn/flashsale/getFlashSaleList?cid1=670&pageSize=20&pageNo=1")

    # ====== 11. 京东品牌 ======
    print("\n[11] 品牌列表")
    try_api("brand.jd.com",
            "https://brand.jd.com/brand/brandList?cid=670&page=1")

    # ====== 12. 京东众筹/新品 ======
    print("\n[12] 新品/众筹")
    try_api("xin.jd.com",
            "https://xin.jd.com/newProductList?cid1=670&cid2=671&cid3=672&page=1&pageSize=20")

    # ====== 13. 京东企业购 ======
    print("\n[13] 企业购 API")
    try_api("b.jd.com (api)",
            "https://b.jd.com/api/product/search?keyword=轴承&page=1&pageSize=20")

    # ====== 14. 京东开放平台 ======
    print("\n[14] 京东开放 API")
    try_api("api.jd.com (router)",
            "https://api.jd.com/routerjson?v=2&method=jd.union.open.goods.query&app_key=test&param_json=%7B%22goodsReq%22%3A%7B%22keyword%22%3A%22轴承%22%7D%7D")

    # ====== 15. 移动版 ======
    print("\n[15] 移动版 API")
    mobile_h = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        "Accept": "application/json",
        "Referer": "https://m.jd.com/",
    }
    try_api("m.jd.com (home)",
            "https://api.m.jd.com/api?appid=jd-cph-develop&functionId=newHomeData&client=wh5&clientVersion=1.0.0",
            headers=mobile_h)

    # ====== 16. 京东全球购 ======
    print("\n[16] 全球购/跨境")
    try_api("global.jd.com",
            "https://global.jd.com/api/product/list?cid1=670&page=1&pageSize=20")

    # ====== 17. 京东拍卖 ======
    print("\n[17] 拍卖")
    try_api("paimai.jd.com",
            "https://paimai.jd.com/json/searchList?categoryId=670&page=1&limit=20")

    # ====== 汇总 ======
    print(f"\n{'=' * 60}")
    print("汇总: 所有可用数据端点")
    print(f"{'=' * 60}")

    # 保存所有结果
    output = {
        "timestamp": ts,
        "total_endpoints_tried": len(results) + 15,  # 大约
        "successful_endpoints": [],
        "product_data_endpoints": [],
    }

    # 保存 dc.3.cn 分类树（已知可用）
    if "category_tree" in results:
        output["successful_endpoints"].append("dc.3.cn/category/get")
        # 重新解析分类数据
        tree_data = results["category_tree"]
        if isinstance(tree_data, dict) and "data" in tree_data:
            cats = tree_data["data"]
            print(f"\n  ✓ dc.3.cn/category/get: 分类树 ({len(cats)} 个顶级分类)")

    # 保存
    with open(os.path.join(DATA_DIR, f"v4_api_results_{ts}.json"), "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存")


if __name__ == "__main__":
    main()
