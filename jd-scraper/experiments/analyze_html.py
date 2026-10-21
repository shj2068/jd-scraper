"""分析 list.jd.com HTML 中图片附近的结构"""
import re
import os

html = open(os.path.join(os.path.dirname(__file__), "data", "debug_list_page.html"), "r", encoding="utf-8").read()
print(f"HTML 大小: {len(html)} bytes")

# 找到所有 360buyimg 图片
imgs = list(re.finditer(r'//img\d+\.360buyimg\.com/[^\s"\'<>]+', html))
print(f"\n商品图片: {len(imgs)} 个")

for i, m in enumerate(imgs[:8]):
    start = max(0, m.start() - 300)
    end = min(len(html), m.end() + 300)
    context = html[start:end]
    context = re.sub(r'\s+', ' ', context)
    print(f"\n--- 图片 {i}: pos={m.start()} ---")
    print(context[:600])

# 查找所有 <a> 标签
print("\n\n=== 所有链接 ===")
links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
print(f"总链接: {len(links)} 个")
for href, text in links[:30]:
    text_clean = re.sub(r'\s+', ' ', text).strip()[:80]
    if text_clean or 'item' in href.lower():
        print(f"  {href[:100]}  text='{text_clean}'")

# 查找 window.__INITIAL_STATE__ 或类似数据
print("\n\n=== 页面嵌入数据 ===")
for pattern in [
    r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
    r'window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});',
    r'window\.pageConfig\s*=\s*(\{.*?\});',
    r'window\.searchMainConfig\s*=\s*(\{.*?\});',
    r'window\.listConfig\s*=\s*(\{.*?\});',
]:
    matches = re.findall(pattern, html, re.DOTALL)
    if matches:
        print(f"  匹配 {pattern[:50]}: {len(matches)} 个, 大小={len(matches[0])} chars")
        print(f"    前200: {matches[0][:200]}")
