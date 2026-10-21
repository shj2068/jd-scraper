"""
方案2 + 方案3: 京东开放平台/联盟 API 测试
测试内容:
  - 京东开放平台 JOS API 网关连通性
  - 京东联盟 API 网关连通性
  - 签名算法验证
  - 无需注册的公开接口探测
"""
import hashlib
import json
import os
import time
import httpx
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# 京东联盟 API 网关
UNION_GATEWAY = "https://router.jd.com/api"
# 京东开放平台网关
JOS_GATEWAY = "https://api.jd.com/routerjson"


def md5_sign(params: dict, app_secret: str) -> str:
    """京东联盟签名算法"""
    sorted_params = sorted(params.items())
    sign_str = app_secret
    for k, v in sorted_params:
        sign_str += str(k) + str(v)
    sign_str += app_secret
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()


def test_without_credentials():
    """测试: 无凭据情况下能获取什么"""
    print("=" * 60)
    print("方案2+3: 京东 API 无凭据探测")
    print("=" * 60)

    results = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # 1. 测试联盟网关连通性
    print("\n[1] 测试联盟网关连通性...")
    try:
        r = httpx.get(UNION_GATEWAY, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}")
        print(f"  响应: {r.text[:300]}")
        results["union_gateway"] = {"status": r.status_code, "response": r.text[:200]}
    except Exception as e:
        print(f"  ✗ {str(e)[:100]}")
        results["union_gateway"] = {"error": str(e)[:100]}

    # 2. 测试 JOS 网关连通性
    print("\n[2] 测试 JOS 网关连通性...")
    try:
        r = httpx.get(JOS_GATEWAY, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}")
        print(f"  响应: {r.text[:300]}")
        results["jos_gateway"] = {"status": r.status_code, "response": r.text[:200]}
    except Exception as e:
        print(f"  ✗ {str(e)[:100]}")
        results["jos_gateway"] = {"error": str(e)[:100]}

    # 3. 测试无效 AppKey 的响应
    print("\n[3] 测试无效 AppKey 响应...")
    try:
        params = {
            "method": "jd.union.open.goods.jingfen.query",
            "app_key": "test_invalid_key",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "format": "json",
            "v": "1.0",
            "sign_method": "md5",
        }
        r = httpx.post(UNION_GATEWAY, data=params, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}")
        try:
            j = json.loads(r.text)
            print(f"  JSON: {json.dumps(j, ensure_ascii=False)[:300]}")
            results["invalid_key"] = j
        except Exception:
            print(f"  非JSON: {r.text[:200]}")
            results["invalid_key"] = {"raw": r.text[:200]}
    except Exception as e:
        print(f"   {str(e)[:100]}")

    # 4. 测试京东 H5 搜索 API（可能不需要签名）
    print("\n[4] 测试 H5 搜索自动补全...")
    try:
        url = "https://api.m.jd.com/api"
        params = {
            "appid": "search_m.jd.com",
            "functionId": "search_auto_complete",
            "client": "wh5",
            "body": json.dumps({"keyword": "轴承", "page": 1, "pageSize": 10}),
        }
        r = httpx.get(url, params=params, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
            "Referer": "https://so.m.jd.com/",
        }, timeout=10)
        print(f"  状态码: {r.status_code}")
        print(f"  响应: {r.text[:300]}")
        try:
            j = json.loads(r.text)
            results["h5_autocomplete"] = j
        except Exception:
            results["h5_autocomplete"] = {"raw": r.text[:200]}
    except Exception as e:
        print(f"  ✗ {str(e)[:100]}")

    # 5. 测试京东商品价格 API (p.3.cn)
    print("\n[5] 测试价格 API (p.3.cn)...")
    try:
        sku = "100012043978"  # 一个常见商品 SKU
        url = f"https://p.3.cn/prices/mgets?skuIds=J_{sku}"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}")
        print(f"  响应: {r.text[:300]}")
        try:
            j = json.loads(r.text)
            if isinstance(j, list) and len(j) > 0:
                print(f"  ✓ 价格数据: {j[0]}")
                results["price_api"] = {"success": True, "data": j[0]}
            else:
                results["price_api"] = {"success": False, "data": j}
        except Exception:
            results["price_api"] = {"raw": r.text[:200]}
    except Exception as e:
        print(f"  ✗ {str(e)[:100]}")

    # 6. 测试京东评论 API
    print("\n[6] 测试评论 API...")
    try:
        sku = "100012043978"
        url = f"https://club.jd.com/comment/productPageComments.action?productId={sku}&score=0&sortType=5&page=0&pageSize=10"
        r = httpx.get(url, headers={**headers, "Referer": f"https://item.jd.com/{sku}.html"}, timeout=10)
        print(f"  状态码: {r.status_code}")
        print(f"  响应: {r.text[:300]}")
        try:
            j = json.loads(r.text)
            if "comments" in j:
                print(f"  ✓ 评论数: {j.get('productCommentSummary', {}).get('commentCountStr', 'N/A')}")
                results["comment_api"] = {"success": True, "count": len(j.get("comments", []))}
            else:
                results["comment_api"] = {"success": False, "keys": list(j.keys())[:10]}
        except Exception:
            results["comment_api"] = {"raw": r.text[:200]}
    except Exception as e:
        print(f"  ✗ {str(e)[:100]}")

    # 7. 测试京东推荐 API
    print("\n[7] 测试推荐 API...")
    try:
        url = "https://re.jd.com/cats/getCatRecommend.action?cat=670,671,672"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}")
        print(f"  响应: {r.text[:300]}")
        try:
            j = json.loads(r.text)
            results["recommend_api"] = {"success": True, "keys": list(j.keys())[:10]}
        except Exception:
            results["recommend_api"] = {"raw": r.text[:200]}
    except Exception as e:
        print(f"  ✗ {str(e)[:100]}")

    # 8. 测试京东商品详情 (ware-detail)
    print("\n[8] 测试商品详情 API...")
    try:
        sku = "100012043978"
        url = f"https://cd.jd.com/description/channel?skuId={sku}&mainSkuId={sku}&cdn=2&callback=jQuery"
        r = httpx.get(url, headers={**headers, "Referer": f"https://item.jd.com/{sku}.html"}, timeout=10)
        print(f"  状态码: {r.status_code}")
        print(f"  响应: {r.text[:300]}")
        results["detail_api"] = {"status": r.status_code, "size": len(r.text)}
    except Exception as e:
        print(f"  ✗ {str(e)[:100]}")

    # 9. 测试京东搜索建议 (suggestion)
    print("\n[9] 测试搜索建议 API...")
    try:
        url = "https://search.jd.com/suggest?keyword=轴承&_type=1&json=1&area=1&enc=utf8"
        r = httpx.get(url, headers={**headers, "Referer": "https://www.jd.com/"}, timeout=10)
        print(f"  状态码: {r.status_code}")
        print(f"  响应: {r.text[:300]}")
        try:
            j = json.loads(r.text)
            results["search_suggest"] = j
        except Exception:
            results["search_suggest"] = {"raw": r.text[:200]}
    except Exception as e:
        print(f"  ✗ {str(e)[:100]}")

    # 10. 测试京东分类 API
    print("\n[10] 测试分类 API...")
    try:
        url = "https://dc.3.cn/category/get"
        r = httpx.get(url, headers=headers, timeout=10)
        ct = r.headers.get("content-type", "")
        text = r.text
        if "gbk" in ct.lower():
            text = r.content.decode("gbk")
        print(f"  状态码: {r.status_code}")
        print(f"  响应大小: {len(text)} bytes")
        try:
            j = json.loads(text)
            if isinstance(j, list) and len(j) > 0:
                print(f"  ✓ 分类数据: {len(j)} 个大类")
                results["category_api"] = {"success": True, "count": len(j)}
            else:
                results["category_api"] = {"success": False}
        except Exception:
            results["category_api"] = {"raw": text[:200]}
    except Exception as e:
        print(f"  ✗ {str(e)[:100]}")

    # 11. 测试京东排行榜
    print("\n[11] 测试排行榜 API...")
    try:
        url = "https://rank.jd.com/rank/list?cid1=670&cid2=671&cid3=672&ev=exbrand_&page=1"
        r = httpx.get(url, headers={**headers, "Referer": "https://rank.jd.com/"}, timeout=10)
        print(f"  状态码: {r.status_code}")
        print(f"  响应: {r.text[:200]}")
        results["rank_api"] = {"status": r.status_code, "size": len(r.text)}
    except Exception as e:
        print(f"  ✗ {str(e)[:100]}")

    # 12. 测试京东秒杀
    print("\n[12] 测试秒杀 API...")
    try:
        url = "https://miaosha.jd.com/json/seckilllist.action"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}")
        print(f"  响应: {r.text[:200]}")
        try:
            j = json.loads(r.text)
            results["seckill_api"] = {"success": True, "keys": list(j.keys())[:10]}
        except Exception:
            results["seckill_api"] = {"raw": r.text[:200]}
    except Exception as e:
        print(f"  ✗ {str(e)[:100]}")

    # 汇总
    print(f"\n{'=' * 60}")
    print("汇总:")
    success_count = sum(1 for v in results.values() if isinstance(v, dict) and v.get("success"))
    print(f"  成功: {success_count}/{len(results)}")
    for name, result in results.items():
        status = "✓" if isinstance(result, dict) and result.get("success") else ""
        print(f"  {status} {name}: {json.dumps(result, ensure_ascii=False)[:100]}")

    outfile = DATA_DIR / "solution23_test_result.json"
    outfile.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已保存: {outfile}")

    return results


if __name__ == "__main__":
    test_without_credentials()
