"""
京东数据采集 - 四方案综合对比 + 最优解实现
============================================
方案1: Cookie 注入 + Playwright 浏览器自动化
方案2: 京东开放平台 (JOS) API
方案3: 京东联盟 API
方案4: 第三方服务 / 开源工具 / 公开 API

最终选出最优解并实现
"""
import json
import hashlib
import time
import httpx
import re
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


# ============================================================
# 第一部分: 四方案对比
# ============================================================

def comparison_report():
    """生成四方案对比报告"""
    print("=" * 70)
    print("京东数据采集 - 四方案综合对比")
    print("=" * 70)

    solutions = [
        {
            "name": "方案1: Cookie 注入 + Playwright",
            "feasibility": "需要真实登录 Cookie",
            "data_quality": "★★★★★ (完整商品数据)",
            "difficulty": "★★★☆☆ (需手动登录一次)",
            "stability": "★★☆☆☆ (Cookie 过期需重新登录，反爬频繁)",
            "cost": "免费",
            "pros": [
                "数据最完整（价格/详情/评价/库存）",
                "可模拟真实用户行为",
                "无需注册开发者账号",
            ],
            "cons": [
                "匿名 Cookie 无效（已验证）",
                "搜索页强制登录",
                "详情页触发频控 (403)",
                "Cookie 有效期短（通常 1-7 天）",
                "需要人工介入登录",
            ],
            "verdict": "❌ 不推荐 - 维护成本高，不适合自动化",
        },
        {
            "name": "方案2: 京东开放平台 (JOS) API",
            "feasibility": "需企业认证 + 绑定店铺",
            "data_quality": "★★★★★ (官方全量数据)",
            "difficulty": "★★★★☆ (企业认证流程复杂)",
            "stability": "★★★★★ (官方接口，最稳定)",
            "cost": "免费（基础 QPS=2）",
            "pros": [
                "数据最全、最权威",
                "官方支持，接口稳定",
                "实时库存/价格",
                "支持批量查询（20 SKU/次）",
            ],
            "cons": [
                "必须企业认证（营业执照）",
                "必须绑定京东 POP/自营店铺",
                "审核流程长（数天至数周）",
                "基础 QPS 仅 2",
            ],
            "verdict": "⚠️ 适合有京东店铺的商家",
        },
        {
            "name": "方案3: 京东联盟 API",
            "feasibility": "个人实名认证即可",
            "data_quality": "★★★★☆ (含佣金/推广数据)",
            "difficulty": "★★☆☆☆ (注册简单)",
            "stability": "★★★★☆ (官方接口)",
            "cost": "免费（个人 QPS=5）",
            "pros": [
                "个人即可注册（身份证认证）",
                "无需绑定店铺",
                "含佣金/优惠券/销量数据",
                "审核快（通常当天通过）",
                "接口丰富（搜索/详情/分类/推荐）",
            ],
            "cons": [
                "未参加联盟的商品无法查询",
                "价格是推广价而非实时京东价",
                "无精确实时库存",
                "QPS 限制（个人 5，企业 20）",
            ],
            "verdict": "✅ 最优官方方案 - 门槛最低，数据够用",
        },
        {
            "name": "方案4: 公开 API + 第三方服务",
            "feasibility": "立即可用（部分）",
            "data_quality": "★★☆☆☆ (仅分类/品牌数据)",
            "difficulty": "★☆☆☆☆ (零门槛)",
            "stability": "★★★☆☆ (公开接口可能随时关闭)",
            "cost": "免费 / 第三方付费",
            "pros": [
                "零门槛，无需注册",
                "分类 API 稳定可用（dc.3.cn）",
                "第三方服务开箱即用",
            ],
            "cons": [
                "公开 API 仅返回分类/品牌数据",
                "无商品详情/价格/销量",
                "第三方服务需付费",
                "数据完整度低",
            ],
            "verdict": "✅ 最佳即时方案 - 分类数据可用",
        },
    ]

    for i, s in enumerate(solutions, 1):
        print(f"\n{'─' * 70}")
        print(f"  {s['name']}")
        print(f"{'─' * 70}")
        print(f"  可行性:   {s['feasibility']}")
        print(f"  数据质量: {s['data_quality']}")
        print(f"  难度:     {s['difficulty']}")
        print(f"  稳定性:   {s['stability']}")
        print(f"  成本:     {s['cost']}")
        print(f"\n  优点:")
        for p in s["pros"]:
            print(f"    + {p}")
        print(f"  缺点:")
        for c in s["cons"]:
            print(f"    - {c}")
        print(f"\n  结论: {s['verdict']}")

    print(f"\n{'=' * 70}")
    print("  最优解推荐:")
    print("  ┌─────────────────────────────────────────────────┐")
    print("  │ 即时可用: 方案4 (公开分类 API)                   │")
    print("  │   → dc.3.cn/category/get 稳定返回分类+品牌数据  │")
    print("  │                                                 │")
    print("  │ 长期方案: 方案3 (京东联盟 API)                   │")
    print("  │   → media.jd.com 注册 → 个人认证 → 获取 AppKey  │")
    print("  │   → 调用 jd.union.open.goods.jingfen.query      │")
    print("  │   → 获取精选商品列表（含价格/佣金/销量）         │")
    print("  ─────────────────────────────────────────────────┘")
    print(f"{'=' * 70}")


# ============================================================
# 第二部分: 最优解实现 - 公开 API 数据采集
# ============================================================

def collect_category_data():
    """最优解实现: 使用公开分类 API 采集完整数据"""
    print("\n" + "=" * 70)
    print("最优解实现: 公开分类 API 数据采集")
    print("=" * 70)

    url = "https://dc.3.cn/category/get"
    r = httpx.get(url, headers=HEADERS, timeout=15)
    j = json.loads(r.text)

    if "data" not in j:
        print("✗ 分类 API 无数据")
        return None

    data = j["data"]
    print(f"\n采集到 {len(data)} 个一级分类")

    categories = []
    brands = set()
    search_links = []

    for i, cat in enumerate(data):
        cat_name = f"分类{i+1}"
        cat_info = {"index": i, "name": cat_name, "brands": [], "sub_categories": []}

        # 解析品牌 (b 字段)
        if "b" in cat and isinstance(cat["b"], list):
            for brand_str in cat["b"]:
                parts = brand_str.split("|")
                if len(parts) >= 2:
                    brand_url = parts[0].strip()
                    brand_name = parts[1].strip()
                    if brand_name:
                        brands.add(brand_name)
                        cat_info["brands"].append({
                            "name": brand_name,
                            "url": brand_url if brand_url.startswith("http") else f"https://{brand_url}",
                        })

        # 解析子分类/推荐 (p 字段)
        if "p" in cat and isinstance(cat["p"], list):
            for p_str in cat["p"]:
                parts = p_str.split("|")
                if len(parts) >= 2:
                    p_url = parts[0].strip()
                    p_name = parts[1].strip()
                    if p_name:
                        cat_info["sub_categories"].append({
                            "name": p_name,
                            "url": p_url if p_url.startswith("http") else f"https://{p_url}",
                        })
                        if "search" in p_url or "list" in p_url:
                            search_links.append({"name": p_name, "url": p_url})

        categories.append(cat_info)
        print(f"  [{i+1:2d}] {cat_name}: {len(cat_info['brands'])} 品牌, {len(cat_info['sub_categories'])} 子分类")

    # 保存结果
    result = {
        "source": "dc.3.cn/category/get",
        "timestamp": datetime.now().isoformat(),
        "total_categories": len(categories),
        "total_brands": len(brands),
        "total_search_links": len(search_links),
        "categories": categories,
        "brand_list": sorted(list(brands)),
        "search_links": search_links[:50],
    }

    outfile = DATA_DIR / "optimal_solution_result.json"
    outfile.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ 结果已保存: {outfile}")
    print(f"  分类数: {len(categories)}")
    print(f"  品牌数: {len(brands)}")
    print(f"  搜索链接: {len(search_links)}")

    return result


# ============================================================
# 第三部分: 京东联盟 API 调用模板（需用户提供 AppKey/AppSecret）
# ============================================================

def union_api_template():
    """生成京东联盟 API 调用模板"""
    print("\n" + "=" * 70)
    print("京东联盟 API 调用模板（需注册后填入凭据）")
    print("=" * 70)

    template = '''
# 京东联盟 API 调用步骤:
# 1. 访问 https://media.jd.com/ 注册账号
# 2. 完成个人实名认证
# 3. 进入「开发者管理」→「我的 API」→ 领取授权 Key
# 4. 创建应用 → 获取 AppKey 和 AppSecret
# 5. 申请接口权限（填写用途：选品/比价/数据采集）
# 6. 使用以下代码调用

import hashlib
import time
import httpx
import json

APP_KEY = "你的AppKey"       # 替换为实际值
APP_SECRET = "你的AppSecret"  # 替换为实际值
GATEWAY = "https://router.jd.com/api"

def jd_union_sign(params, app_secret):
    """京东联盟签名算法"""
    sorted_params = sorted(params.items())
    sign_str = app_secret
    for k, v in sorted_params:
        sign_str += str(k) + str(v)
    sign_str += app_secret
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()

def query_jingfen_goods(elite_id=1, page=1, page_size=20):
    """查询京粉精选商品（无需额外申请）"""
    params = {
        "method": "jd.union.open.goods.jingfen.query",
        "app_key": APP_KEY,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "format": "json",
        "v": "1.0",
        "sign_method": "md5",
        "goods_req": json.dumps({
            "eliteId": elite_id,  # 1=好券商品, 2=精选卖场, 10=9.9包邮...
            "pageIndex": page,
            "pageSize": page_size,
        }),
    }
    params["sign"] = jd_union_sign(params, APP_SECRET)

    r = httpx.post(GATEWAY, data=params, timeout=10)
    return r.json()

# 调用示例:
# result = query_jingfen_goods(elite_id=1, page=1, page_size=10)
# print(json.dumps(result, ensure_ascii=False, indent=2))
'''
    print(template)

    # 保存模板
    template_file = Path(__file__).parent / "jd_union_api_template.py"
    template_file.write_text(template.strip(), encoding="utf-8")
    print(f"模板已保存: {template_file}")


# ============================================================
# 主流程
# ============================================================

def main():
    # 1. 对比报告
    comparison_report()

    # 2. 最优解实现 - 公开 API
    collect_category_data()

    # 3. 联盟 API 模板
    union_api_template()

    print("\n" + "=" * 70)
    print("全部完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
