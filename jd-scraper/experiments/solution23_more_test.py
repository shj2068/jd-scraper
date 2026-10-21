"""
方案2+3 补充: 正确处理分类 API 的 GBK 编码 + 测试更多公开接口
"""
import json
import httpx
import re
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


def test_category_api_fixed():
    """修复分类 API 的 GBK 编码问题"""
    print("=" * 60)
    print("分类 API 详细测试 (GBK 编码修复)")
    print("=" * 60)

    url = "https://dc.3.cn/category/get"
    r = httpx.get(url, headers=headers, timeout=15)
    ct = r.headers.get("content-type", "")
    print(f"  Content-Type: {ct}")
    print(f"  原始大小: {len(r.content)} bytes")

    # 尝试多种编码
    for enc in ["utf-8", "gbk", "gb2312", "gb18030"]:
        try:
            text = r.content.decode(enc)
            j = json.loads(text)
            print(f"  ✓ 编码 {enc} 成功!")
            print(f"  类型: {type(j).__name__}")
            if isinstance(j, list):
                print(f"  顶层元素: {len(j)}")
                if len(j) > 0:
                    print(f"  第一个元素: {str(j[0])[:200]}")
            elif isinstance(j, dict):
                print(f"  键: {list(j.keys())[:10]}")
            return j
        except Exception as e:
            print(f"  ✗ {enc}: {str(e)[:80]}")

    # 尝试 JSONP 解析
    text = r.content.decode("gbk", errors="ignore")
    m = re.match(r'^[a-zA-Z_]\w*\((.*)\);?$', text, re.DOTALL)
    if m:
        print(f"  JSONP 匹配成功!")
        try:
            j = json.loads(m.group(1))
            print(f"  ✓ JSONP 解析成功: {type(j).__name__}")
            return j
        except Exception as e:
            print(f"  JSONP 解析失败: {e}")

    # 保存原始数据
    (DATA_DIR / "category_raw.bin").write_bytes(r.content)
    print(f"  原始数据已保存: data/category_raw.bin")
    print(f"  前 500 字节: {r.content[:500]}")
    return None


def test_more_public_apis():
    """测试更多可能的公开 API"""
    print("\n" + "=" * 60)
    print("更多公开 API 测试")
    print("=" * 60)

    results = {}

    # 1. 京东商品 SKU 查询 (通过 item-soa)
    print("\n[1] item-soa API...")
    try:
        url = "https://item-soa.jd.com/getWareBusiness?skuId=100012043978"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}, 大小: {len(r.text)}")
        print(f"  响应: {r.text[:200]}")
        results["item_soa"] = {"status": r.status_code, "size": len(r.text)}
    except Exception as e:
        print(f"  ✗ {e}")

    # 2. 京东库存查询
    print("\n[2] 库存 API...")
    try:
        url = "https://c0.3.cn/stock?skuId=100012043978&area=1_72_0_0&cat=670,671,672"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}, 大小: {len(r.text)}")
        print(f"  响应: {r.text[:200]}")
        try:
            j = json.loads(r.text)
            results["stock_api"] = j
        except Exception:
            results["stock_api"] = {"raw": r.text[:200]}
    except Exception as e:
        print(f"  ✗ {e}")

    # 3. 京东商品广告/推荐
    print("\n[3] 广告推荐 API...")
    try:
        url = "https://ad.3.cn/ad/getAd?adIds=1:1&posId=704&callback=jsonp"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}, 大小: {len(r.text)}")
        print(f"  响应: {r.text[:200]}")
        results["ad_api"] = {"status": r.status_code, "size": len(r.text)}
    except Exception as e:
        print(f"  ✗ {e}")

    # 4. 京东品牌 API
    print("\n[4] 品牌 API...")
    try:
        url = "https://brand.jd.com/api/brandList?catId1=670&catId2=671"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}, 大小: {len(r.text)}")
        print(f"  响应: {r.text[:200]}")
        results["brand_api"] = {"status": r.status_code, "size": len(r.text)}
    except Exception as e:
        print(f"  ✗ {e}")

    # 5. 京东新品 API
    print("\n[5] 新品 API...")
    try:
        url = "https://xin.jd.com/xin/list?cat1=670&cat2=671&page=1"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}, 大小: {len(r.text)}")
        print(f"  响应: {r.text[:200]}")
        results["xin_api"] = {"status": r.status_code, "size": len(r.text)}
    except Exception as e:
        print(f"  ✗ {e}")

    # 6. 京东企业购
    print("\n[6] 企业购 API...")
    try:
        url = "https://b.jd.com/api/search?keyword=轴承&page=1&pageSize=20"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}, 大小: {len(r.text)}")
        print(f"  响应: {r.text[:200]}")
        results["enterprise_api"] = {"status": r.status_code, "size": len(r.text)}
    except Exception as e:
        print(f"  ✗ {e}")

    # 7. 京东全球购
    print("\n[7] 全球购 API...")
    try:
        url = "https://global.jd.com/search?keyword=轴承&page=1"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}, 大小: {len(r.text)}")
        print(f"  响应: {r.text[:200]}")
        results["global_api"] = {"status": r.status_code, "size": len(r.text)}
    except Exception as e:
        print(f"  ✗ {e}")

    # 8. 京东拍卖
    print("\n[8] 拍卖 API...")
    try:
        url = "https://paimai.jd.com/api/search?keyword=轴承"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}, 大小: {len(r.text)}")
        print(f"  响应: {r.text[:200]}")
        results["auction_api"] = {"status": r.status_code, "size": len(r.text)}
    except Exception as e:
        print(f"   {e}")

    # 9. 京东到家
    print("\n[9] 京东到家 API...")
    try:
        url = "https://daojia.jd.com/api/search?keyword=轴承&cityId=1"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}, 大小: {len(r.text)}")
        print(f"  响应: {r.text[:200]}")
        results["daojia_api"] = {"status": r.status_code, "size": len(r.text)}
    except Exception as e:
        print(f"  ✗ {e}")

    # 10. 京东健康
    print("\n[10] 京东健康 API...")
    try:
        url = "https://health.jd.com/api/search?keyword=轴承"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}, 大小: {len(r.text)}")
        print(f"  响应: {r.text[:200]}")
        results["health_api"] = {"status": r.status_code, "size": len(r.text)}
    except Exception as e:
        print(f"  ✗ {e}")

    # 11. 京东图书
    print("\n[11] 京东图书 API...")
    try:
        url = "https://book.jd.com/booksearch?keyword=轴承&page=1"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}, 大小: {len(r.text)}")
        print(f"  响应: {r.text[:200]}")
        results["book_api"] = {"status": r.status_code, "size": len(r.text)}
    except Exception as e:
        print(f"  ✗ {e}")

    # 12. 京东超市
    print("\n[12] 京东超市 API...")
    try:
        url = "https://chaoshi.jd.com/search?keyword=轴承"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}, 大小: {len(r.text)}")
        print(f"  响应: {r.text[:200]}")
        results["chaoshi_api"] = {"status": r.status_code, "size": len(r.text)}
    except Exception as e:
        print(f"  ✗ {e}")

    # 13. 京东五金/工业品
    print("\n[13] 京东工业品 API...")
    try:
        url = "https://gy.jd.com/search?keyword=轴承"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}, 大小: {len(r.text)}")
        print(f"  响应: {r.text[:200]}")
        results["gy_api"] = {"status": r.status_code, "size": len(r.text)}
    except Exception as e:
        print(f"  ✗ {e}")

    # 14. 京东五金城
    print("\n[14] 京东五金城 API...")
    try:
        url = "https://wujin.jd.com/search?keyword=轴承"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}, 大小: {len(r.text)}")
        print(f"  响应: {r.text[:200]}")
        results["wujin_api"] = {"status": r.status_code, "size": len(r.text)}
    except Exception as e:
        print(f"  ✗ {e}")

    # 15. 京东招商/工业招商
    print("\n[15] 京东工业招商 API...")
    try:
        url = "https://zhaoshang.jd.com/api/search?keyword=轴承"
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"  状态码: {r.status_code}, 大小: {len(r.text)}")
        print(f"  响应: {r.text[:200]}")
        results["zhaoshang_api"] = {"status": r.status_code, "size": len(r.text)}
    except Exception as e:
        print(f"  ✗ {e}")

    # 保存结果
    outfile = DATA_DIR / "solution23_more_apis.json"
    outfile.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已保存: {outfile}")

    return results


if __name__ == "__main__":
    cat_data = test_category_api_fixed()
    more_results = test_more_public_apis()
