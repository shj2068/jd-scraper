#!/usr/bin/env python3
"""生成京东电动工具电商数据可视化 HTML 报告"""
import json, sys, io
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

data_path = sorted(Path(__file__).parent.glob("data/jd_power_tools_final_*.json"))[-1]
data = json.loads(data_path.read_text("utf-8"))

products = data["products"]
brands = data["brand_distribution"]
shops = data["shop_ranking"]
summary = data["summary"]

# 品牌数据
brand_items = sorted(brands.items(), key=lambda x: -x[1])
brand_colors = {
    "东成": "#e74c3c", "德力西电气": "#3498db", "博世": "#2ecc71",
    "得力": "#f39c12", "班帝森": "#9b59b6", "欧莱德": "#1abc9c",
    "爱瑞德": "#e67e22", "其他": "#95a5a6", "优力特": "#34495e",
    "上海人民": "#d35400", "亚特": "#16a085", "星固": "#27ae60",
    "光宸": "#8e44ad",
}

# 价格区间
prices = [p["price"] for p in products if p["price"] > 0]
ranges = [(0,50,"¥0-50"),(50,100,"¥50-100"),(100,150,"¥100-150"),(150,200,"¥150-200"),(200,300,"¥200-300"),(300,500,"¥300+")]
range_data = [{"label": l, "count": sum(1 for p in prices if lo<=p<hi), "lo": lo, "hi": hi} for lo, hi, l in ranges]
max_range = max(r["count"] for r in range_data) if range_data else 1

# 店铺排名
shop_items = [(s["shop"], s["count"]) for s in shops[:10]]
max_shop = max(c for _, c in shop_items) if shop_items else 1

# 品牌均价
brand_avg = {}
for p in products:
    b = p["brand"]
    if b not in brand_avg:
        brand_avg[b] = []
    if p["price"] > 0:
        brand_avg[b].append(p["price"])
brand_avg_data = [(b, round(sum(v)/len(v), 0), len(v)) for b, v in brand_avg.items() if v]
brand_avg_data.sort(key=lambda x: -x[1])

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>京东电动工具电商数据采集报告</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, 'Segoe UI', 'Microsoft YaHei', sans-serif; background: #0f1923; color: #e0e6ed; padding: 20px; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
.header {{ text-align: center; padding: 30px 0; border-bottom: 1px solid #1e2d3d; margin-bottom: 30px; }}
.header h1 {{ font-size: 28px; color: #e74c3c; margin-bottom: 8px; }}
.header .meta {{ color: #7f8c9b; font-size: 14px; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 30px; }}
.stat-card {{ background: #1a2736; border-radius: 12px; padding: 20px; text-align: center; border: 1px solid #253545; }}
.stat-card .value {{ font-size: 32px; font-weight: 700; color: #e74c3c; }}
.stat-card .label {{ font-size: 13px; color: #7f8c9b; margin-top: 4px; }}
.section {{ background: #1a2736; border-radius: 12px; padding: 24px; margin-bottom: 24px; border: 1px solid #253545; }}
.section h2 {{ font-size: 18px; color: #3498db; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #253545; }}
.bar-chart {{ display: flex; flex-direction: column; gap: 10px; }}
.bar-row {{ display: flex; align-items: center; gap: 12px; }}
.bar-label {{ width: 100px; text-align: right; font-size: 13px; color: #b0bec5; flex-shrink: 0; }}
.bar-track {{ flex: 1; height: 28px; background: #0f1923; border-radius: 6px; overflow: hidden; position: relative; }}
.bar-fill {{ height: 100%; border-radius: 6px; display: flex; align-items: center; padding-left: 10px; font-size: 12px; font-weight: 600; color: #fff; transition: width 0.8s ease; min-width: 40px; }}
.bar-value {{ width: 60px; font-size: 13px; color: #7f8c9b; text-align: left; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; padding: 10px 12px; font-size: 12px; color: #7f8c9b; text-transform: uppercase; border-bottom: 2px solid #253545; }}
td {{ padding: 10px 12px; font-size: 13px; border-bottom: 1px solid #1e2d3d; }}
tr:hover td {{ background: #1e2d3d; }}
.price {{ color: #e74c3c; font-weight: 600; }}
.brand-tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
.shop-name {{ color: #3498db; font-size: 12px; }}
.review {{ color: #f39c12; font-size: 12px; }}
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
@media (max-width: 768px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
.price-dist {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.price-bucket {{ background: #0f1923; border-radius: 8px; padding: 12px 16px; text-align: center; flex: 1; min-width: 120px; border: 1px solid #253545; }}
.price-bucket .count {{ font-size: 24px; font-weight: 700; color: #e74c3c; }}
.price-bucket .range {{ font-size: 12px; color: #7f8c9b; margin-top: 4px; }}
.footer {{ text-align: center; padding: 20px; color: #4a5568; font-size: 12px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>京东电动工具电商数据采集报告</h1>
    <div class="meta">采集时间: {data['collected_at'][:19]} | 关键词: 电钻 + 电动工具 | 排序: 销量 | 来源: search.jd.com</div>
  </div>

  <div class="stats-grid">
    <div class="stat-card"><div class="value">{summary['total_products']}</div><div class="label">采集商品数</div></div>
    <div class="stat-card"><div class="value">{summary['unique_brands']}</div><div class="label">品牌数量</div></div>
    <div class="stat-card"><div class="value">{summary['unique_shops']}</div><div class="label">店铺数量</div></div>
    <div class="stat-card"><div class="value">&yen;{summary['price_range']['avg']:.0f}</div><div class="label">平均价格</div></div>
    <div class="stat-card"><div class="value">&yen;{summary['price_range']['min']:.0f}</div><div class="label">最低价格</div></div>
    <div class="stat-card"><div class="value">&yen;{summary['price_range']['max']:.0f}</div><div class="label">最高价格</div></div>
  </div>

  <div class="two-col">
    <div class="section">
      <h2>品牌分布 (按商品数量)</h2>
      <div class="bar-chart">
"""

for brand, count in brand_items[:10]:
    pct = count / len(products) * 100
    color = brand_colors.get(brand, "#7f8c9b")
    width = max(count / max(brands.values()) * 100, 8)
    html += f"""        <div class="bar-row">
          <div class="bar-label">{brand}</div>
          <div class="bar-track"><div class="bar-fill" style="width:{width}%;background:{color}">{count}</div></div>
          <div class="bar-value">{pct:.1f}%</div>
        </div>
"""

html += """      </div>
    </div>
    <div class="section">
      <h2>品牌均价排行</h2>
      <div class="bar-chart">
"""

for brand, avg, cnt in brand_avg_data[:10]:
    color = brand_colors.get(brand, "#7f8c9b")
    width = max(avg / max(a for _, a, _ in brand_avg_data) * 100, 8)
    html += f"""        <div class="bar-row">
          <div class="bar-label">{brand}</div>
          <div class="bar-track"><div class="bar-fill" style="width:{width}%;background:{color}">&yen;{avg:.0f}</div></div>
          <div class="bar-value">{cnt}件</div>
        </div>
"""

html += """      </div>
    </div>
  </div>

  <div class="section">
    <h2>价格区间分布</h2>
    <div class="price-dist">
"""

for r in range_data:
    html += f"""      <div class="price-bucket">
        <div class="count">{r['count']}</div>
        <div class="range">{r['label']}</div>
      </div>
"""

html += """    </div>
  </div>

  <div class="section">
    <h2>店铺排名 TOP 10 (按商品数量)</h2>
    <div class="bar-chart">
"""

for shop, count in shop_items:
    width = max(count / max_shop * 100, 8)
    short_shop = shop.replace("京东自营旗舰店", "").replace("旗舰店", "").replace("专卖店", "")
    html += f"""      <div class="bar-row">
        <div class="bar-label" style="width:200px" title="{shop}">{short_shop}</div>
        <div class="bar-track"><div class="bar-fill" style="width:{width}%;background:#3498db">{count}</div></div>
        <div class="bar-value">{count}件</div>
      </div>
"""

html += """    </div>
  </div>

  <div class="section">
    <h2>全部商品明细 (按价格排序)</h2>
    <table>
      <thead>
        <tr><th>#</th><th>品牌</th><th>商品名称</th><th>价格</th><th>店铺</th></tr>
      </thead>
      <tbody>
"""

for idx, p in enumerate(products, 1):
    color = brand_colors.get(p["brand"], "#7f8c9b")
    html += f"""        <tr>
          <td>{idx}</td>
          <td><span class="brand-tag" style="background:{color}22;color:{color}">{p['brand']}</span></td>
          <td title="{p['title']}">{p['title'][:50]}{'...' if len(p['title'])>50 else ''}</td>
          <td class="price">&yen;{p['price']:.2f}</td>
          <td class="shop-name">{p['shop'][:20] if p['shop'] else '-'}</td>
        </tr>
"""

html += f"""      </tbody>
    </table>
  </div>

  <div class="section">
    <h2>搜索页品牌筛选区 (京东推荐)</h2>
    <div style="display:flex;gap:12px;flex-wrap:wrap;">
      <span class="brand-tag" style="background:#e74c3c22;color:#e74c3c;padding:8px 16px;font-size:14px">东成</span>
      <span class="brand-tag" style="background:#3498db22;color:#3498db;padding:8px 16px;font-size:14px">欧莱德</span>
      <span class="brand-tag" style="background:#2ecc7122;color:#2ecc71;padding:8px 16px;font-size:14px">德力西电气</span>
      <span class="brand-tag" style="background:#f39c1222;color:#f39c12;padding:8px 16px;font-size:14px">大有 Devon</span>
      <span class="brand-tag" style="background:#9b59b622;color:#9b59b6;padding:8px 16px;font-size:14px">绿林 GREENER</span>
      <span class="brand-tag" style="background:#1abc9c22;color:#1abc9c;padding:8px 16px;font-size:14px">博世 BOSCH</span>
    </div>
  </div>

  <div class="footer">
    京东电动工具电商数据采集报告 | 数据仅供研究参考 | jd-scraper v2.1
  </div>
</div>
</body>
</html>
"""

out_path = Path(__file__).parent / "data" / "reports" / "jd_power_tools_report.html"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(html, encoding="utf-8")
print(f"HTML 报告已生成: {out_path}")
