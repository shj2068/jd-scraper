#!/usr/bin/env python3
"""Generate final HTML visualization report from merged data"""
import json
import sys
import io
from datetime import datetime
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DATA_DIR = Path(__file__).parent / "data"
REPORT_DIR = Path(__file__).parent / "data" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

data_file = DATA_DIR / "merged_all_data_latest.json"
with open(data_file, "r", encoding="utf-8") as f:
    raw = json.load(f)

products = raw["products"] if isinstance(raw, dict) and "products" in raw else raw

brands = defaultdict(lambda: {"count": 0, "prices": []})
shops = defaultdict(int)
categories = defaultdict(int)
keywords = defaultdict(int)
prices = []
tool_prices = []

for p in products:
    brands[p["brand"]]["count"] += 1
    if p["price"] > 0:
        brands[p["brand"]]["prices"].append(p["price"])
        prices.append(p["price"])
        if p["category"] == "power_tool":
            tool_prices.append(p["price"])
    if p.get("shop"):
        shops[p["shop"]] += 1
    categories[p["category"]] += 1
    keywords[p.get("keyword", "")] += 1

sorted_brands = sorted(brands.items(), key=lambda x: -x[1]["count"])
sorted_shops = sorted(shops.items(), key=lambda x: -x[1])[:15]

brand_colors = {
    "东成": "#e74c3c", "博世": "#3498db", "德力西电气": "#2ecc71",
    "欧莱德": "#f39c12", "绿林": "#1abc9c", "大有": "#9b59b6",
    "威克士": "#e67e22", "小米": "#ff6348", "得力": "#3742fa",
    "爱瑞德": "#7bed9f", "大艺": "#70a1ff", "苏泊尔": "#ff4757",
    "京造": "#ffa502", "其他": "#636e72",
}

def get_color(brand):
    return brand_colors.get(brand, "#95a5a6")

max_brand_count = sorted_brands[0][1]["count"] if sorted_brands else 1
max_shop_count = sorted_shops[0][1] if sorted_shops else 1

tool_power_tools = [p for p in products if p["category"] == "power_tool"]
tool_power_tools.sort(key=lambda x: -x["price"])

price_ranges = [(0, 50), (50, 100), (100, 200), (200, 300), (300, 500), (500, 99999)]
price_range_counts = []
for lo, hi in price_ranges:
    cnt = sum(1 for p in tool_prices if lo <= p < hi)
    label = f"¥{lo}-{hi}" if hi < 99999 else f"¥{lo}+"
    price_range_counts.append((label, cnt))

max_pr_count = max(c for _, c in price_range_counts) if price_range_counts else 1

html = f'''<div style="font-family:-apple-system,'Segoe UI','Microsoft YaHei',sans-serif;background:#0f1923;color:#e0e6ed;padding:20px;max-width:1200px;margin:0 auto">
  <div style="text-align:center;padding:20px 0;border-bottom:1px solid #1e2d3d;margin-bottom:20px">
    <h1 style="font-size:24px;color:#e74c3c;margin:0">京东电动工具电商数据全量采集报告</h1>
    <p style="color:#7f8c9b;font-size:13px;margin-top:6px">采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 关键词: 电动工具 + 电钻 + 角磨机 | 销量排序 | {len(products)}件商品(去重)</p>
  </div>

  <div style="display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:24px">
    <div style="background:#1a2733;border-radius:8px;padding:16px;text-align:center">
      <div style="font-size:28px;font-weight:bold;color:#e74c3c">{len(products)}</div>
      <div style="color:#7f8c9b;font-size:12px;margin-top:4px">总商品数</div>
    </div>
    <div style="background:#1a2733;border-radius:8px;padding:16px;text-align:center">
      <div style="font-size:28px;font-weight:bold;color:#3498db">{len(brands)}</div>
      <div style="color:#7f8c9b;font-size:12px;margin-top:4px">品牌数</div>
    </div>
    <div style="background:#1a2733;border-radius:8px;padding:16px;text-align:center">
      <div style="font-size:28px;font-weight:bold;color:#2ecc71">{len(shops)}</div>
      <div style="color:#7f8c9b;font-size:12px;margin-top:4px">店铺数</div>
    </div>
    <div style="background:#1a2733;border-radius:8px;padding:16px;text-align:center">
      <div style="font-size:28px;font-weight:bold;color:#f39c12">¥{min(prices):.0f}</div>
      <div style="color:#7f8c9b;font-size:12px;margin-top:4px">最低价</div>
    </div>
    <div style="background:#1a2733;border-radius:8px;padding:16px;text-align:center">
      <div style="font-size:28px;font-weight:bold;color:#9b59b6">¥{sum(prices)/len(prices):.0f}</div>
      <div style="color:#7f8c9b;font-size:12px;margin-top:4px">均价</div>
    </div>
    <div style="background:#1a2733;border-radius:8px;padding:16px;text-align:center">
      <div style="font-size:28px;font-weight:bold;color:#1abc9c">{categories['power_tool']}</div>
      <div style="color:#7f8c9b;font-size:12px;margin-top:4px">电动工具</div>
    </div>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px">
    <div style="background:#1a2733;border-radius:8px;padding:16px">
      <h3 style="margin:0 0 12px;color:#e74c3c;font-size:16px">品牌分布 TOP 15</h3>
      {''.join(f'<div style="margin-bottom:8px"><div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:2px"><span>{b}</span><span style="color:#7f8c9b">{info["count"]}件 | 均价¥{sum(info["prices"])/len(info["prices"]):.0f}</span></div><div style="background:#0f1923;border-radius:4px;height:20px;overflow:hidden"><div style="background:{get_color(b)};height:100%;width:{info["count"]/max_brand_count*100:.0f}%;border-radius:4px"></div></div></div>' for b, info in sorted_brands[:15])}
    </div>
    <div style="background:#1a2733;border-radius:8px;padding:16px">
      <h3 style="margin:0 0 12px;color:#e74c3c;font-size:16px">店铺排名 TOP 15</h3>
      {''.join(f'<div style="margin-bottom:8px"><div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:2px"><span style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{i+1}. {s}</span><span style="color:#7f8c9b">{c}件</span></div><div style="background:#0f1923;border-radius:4px;height:16px;overflow:hidden"><div style="background:#3498db;height:100%;width:{c/max_shop_count*100:.0f}%;border-radius:4px"></div></div></div>' for i, (s, c) in enumerate(sorted_shops))}
    </div>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px">
    <div style="background:#1a2733;border-radius:8px;padding:16px">
      <h3 style="margin:0 0 12px;color:#e74c3c;font-size:16px">电动工具价格区间分布</h3>
      {''.join(f'<div style="margin-bottom:8px"><div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:2px"><span>{label}</span><span style="color:#7f8c9b">{cnt}件</span></div><div style="background:#0f1923;border-radius:4px;height:20px;overflow:hidden"><div style="background:#f39c12;height:100%;width:{cnt/max_pr_count*100:.0f}%;border-radius:4px"></div></div></div>' for label, cnt in price_range_counts)}
    </div>
    <div style="background:#1a2733;border-radius:8px;padding:16px">
      <h3 style="margin:0 0 12px;color:#e74c3c;font-size:16px">关键词覆盖</h3>
      {''.join(f'<div style="background:#0f1923;border-radius:6px;padding:10px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center"><span style="font-size:14px">{kw}</span><span style="background:#e74c3c;color:white;padding:2px 10px;border-radius:12px;font-size:13px">{cnt}件</span></div>' for kw, cnt in sorted(keywords.items(), key=lambda x: -x[1]) if kw)}
      <h3 style="margin:16px 0 12px;color:#e74c3c;font-size:16px">商品分类</h3>
      <div style="display:flex;gap:12px">
        <div style="flex:1;background:#0f1923;border-radius:6px;padding:12px;text-align:center">
          <div style="font-size:24px;font-weight:bold;color:#2ecc71">{categories['power_tool']}</div>
          <div style="color:#7f8c9b;font-size:12px">电动工具 ({categories['power_tool']/len(products)*100:.1f}%)</div>
        </div>
        <div style="flex:1;background:#0f1923;border-radius:6px;padding:12px;text-align:center">
          <div style="font-size:24px;font-weight:bold;color:#3498db">{categories['home_appliance']}</div>
          <div style="color:#7f8c9b;font-size:12px">家用电器 ({categories['home_appliance']/len(products)*100:.1f}%)</div>
        </div>
      </div>
    </div>
  </div>

  <div style="background:#1a2733;border-radius:8px;padding:16px;margin-bottom:24px">
    <h3 style="margin:0 0 12px;color:#e74c3c;font-size:16px">电动工具商品明细 (部分展示，共{len(tool_power_tools)}件)</h3>
    <table style="width:100%;border-collapse:collapse;font-size:12px">
      <thead>
        <tr style="border-bottom:1px solid #2d3d4d">
          <th style="text-align:left;padding:8px;color:#7f8c9b">商品名称</th>
          <th style="text-align:left;padding:8px;color:#7f8c9b">品牌</th>
          <th style="text-align:right;padding:8px;color:#7f8c9b">价格</th>
          <th style="text-align:left;padding:8px;color:#7f8c9b">店铺</th>
          <th style="text-align:left;padding:8px;color:#7f8c9b">评价</th>
        </tr>
      </thead>
      <tbody>
        {''.join(f'<tr style="border-bottom:1px solid #1e2d3d"><td style="padding:6px 8px;max-width:350px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{p["title"]}">{p["title"][:50]}...</td><td style="padding:6px 8px"><span style="background:{get_color(p["brand"])}22;color:{get_color(p["brand"])};padding:2px 6px;border-radius:4px;font-size:11px">{p["brand"]}</span></td><td style="padding:6px 8px;text-align:right;color:#e74c3c;font-weight:bold">¥{p["price"]:.2f}</td><td style="padding:6px 8px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{p.get("shop","")}">{(p.get("shop","") or "")[:25]}</td><td style="padding:6px 8px;color:#7f8c9b">{p.get("review_count","")}</td></tr>' for p in tool_power_tools[:30])}
      </tbody>
    </table>
  </div>

  <div style="text-align:center;color:#4a5568;font-size:11px;padding:12px;border-top:1px solid #1e2d3d">
    数据来源: 京东搜索结果 | 采集方式: Browser-Use MCP | 去重策略: SKU唯一
  </div>
</div>'''

out_path = REPORT_DIR / "jd_power_tools_full_report.html"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Report saved to: {out_path}")
print(f"Size: {len(html)} bytes")
