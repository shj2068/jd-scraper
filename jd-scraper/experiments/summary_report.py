"""汇总所有采集结果"""
import json
import os
import glob

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# 1. 已有的分类数据
print("=" * 60)
print("已采集数据汇总")
print("=" * 60)

files = sorted(glob.glob(os.path.join(DATA_DIR, "jd_structured_*.json")))
if files:
    f = files[-1]
    data = json.load(open(f, "r", encoding="utf-8"))
    meta = data.get("metadata", {})
    print(f"\n文件: {os.path.basename(f)}")
    print(f"大小: {os.path.getsize(f) // 1024} KB")
    print(f"分类数: {meta.get('total_categories', '?')}")
    print(f"品牌数: {meta.get('total_brands', '?')}")
    print(f"搜索链接: {meta.get('total_search_links', '?')}")
    tree = data.get("category_tree", [])
    print(f"\n顶级分类 ({len(tree)} 个):")
    for c in tree[:10]:
        print(f"  - {c['name']}")
    if len(tree) > 10:
        print(f"  ... 及其他 {len(tree) - 10} 个")

# 2. 浏览器采集截图
print("\n\n截图文件:")
for png in sorted(glob.glob(os.path.join(DATA_DIR, "*.png"))):
    size = os.path.getsize(png)
    print(f"  {os.path.basename(png)} ({size // 1024} KB)")

# 3. 所有数据文件
print("\n\n所有数据文件:")
total_size = 0
for jf in sorted(glob.glob(os.path.join(DATA_DIR, "*.json"))):
    size = os.path.getsize(jf)
    total_size += size
    print(f"  {os.path.basename(jf)} ({size // 1024} KB)")
print(f"\n数据文件总大小: {total_size // 1024} KB")

# 4. 浏览器自动化发现
print("\n\n" + "=" * 60)
print("浏览器自动化采集发现")
print("=" * 60)
print("""
环境:
  ✓ Playwright 1.61.0 + Microsoft Edge (headless)
  ✓ 反检测: webdriver 属性隐藏

测试结果:
  ✓ 京东首页: 成功加载 (标题正确, 12 个 API 拦截)
  ✗ search.jd.com: 重定向到登录页 (需要登录)
  ✗ item.jd.com: 重定向到频控页 (403 反爬)
  ✗ list.jd.com: HTML 壳加载, 但商品数据由 JS 动态渲染 (无法提取)
  ✗ so.m.jd.com: 重定向到风控验证页
  ✗ item.m.jd.com: 同上

公开 API 端点测试 (17 类, 30+ 端点):
  ✓ dc.3.cn/category/get: 分类导航树 (270KB, 2930 分类)
  ✗ p.3.cn (价格): 超时
  ✗ club.jd.com (评论): 返回空文本
  ✗ api.m.jd.com (搜索/推荐): 需要签名或登录
  ✗ re.jd.com (推荐): HTML 错误页
  ✗ ware-detail/item-soa/cd.jd.com (详情): HTML 错误页
  ✗ rank.jd.com/hot.jd.com (排行): 超时/错误
  ✗ answer.jd.com (问答): 验证页
  ✗ shop.jd.com (店铺): HTML 错误页
  ✗ miaosha.jd.com (秒杀): HTML 错误页
  ✗ brand.jd.com (品牌): 超时
  ✗ xin.jd.com (新品): HTML 错误页
  ✗ b.jd.com (企业购): HTML 错误页
  ✗ api.jd.com (开放平台): 需要 app_key
  ✗ global.jd.com (全球购): HTML 错误页
  ✗ paimai.jd.com (拍卖): HTML 错误页
""")

print("=" * 60)
print("结论")
print("=" * 60)
print("""
京东在 2026 年的反爬策略极其严格:
1. 所有商品数据 API 均需要登录态 + 签名验证
2. 搜索/详情/移动版全部触发风控或要求登录
3. 分类列表页是纯 React SPA, 服务端不返回商品数据
4. 唯一可用的公开端点: dc.3.cn/category/get (分类导航树)

已成功采集的数据:
  - 完整分类导航树: 2,930 个分类 + 87 个品牌 + 592 个搜索链接
  - 数据文件: jd_structured_data_*.json (556 KB)

要进一步采集商品数据, 需要:
  1. 京东账号登录 + Cookie 注入
  2. 或使用京东开放平台 API (需要 app_key)
  3. 或使用京东联盟 API (jd.union.open)
""")
