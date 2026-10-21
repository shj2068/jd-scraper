# jd-scraper 实验脚本归档

本目录包含开发过程中产生的探索性脚本，按功能分类如下。

**注意：** 这些脚本是一次性工具，不保证可独立运行。正式采集功能请使用 `main.py` 或 `agent.py`。

## 数据采集类

| 脚本 | 说明 |
|------|------|
| `collect.py` | 初版采集脚本 |
| `collect_rest.py` | REST API 采集 |
| `collect_real.py` / `v2` | 真实数据采集（迭代版本） |
| `collect_real_data.py` / `v2` | 真实数据采集中间版本 |
| `collect_power_tools.py` | 电动工具品类采集 |
| `collect_power_tools_public.py` | 公开 API 采集电动工具 |
| `collect_all_pages.py` | 多页采集（含品牌检测） |
| `batch_collect.py` | 多关键词批量采集与合并 |
| `browser_scrape.py` ~ `v4` | 浏览器采集迭代版本（v4 为纯 HTTP 端点探测） |
| `scrape_public.py` | 公开页面采集 |
| `cookie_*_scrape.py` | Cookie 注入采集实验（分类/移动端/详情） |
| `save_dianzuan_data.py` | 电钻数据保存（60件） |
| `save_jiaomoji_data.py` | 角磨机数据保存（60件） |
| `merge_all_data.py` | 多源数据合并去重 |

## 分析调试类

| 脚本 | 说明 |
|------|------|
| `probe.py` | API 端点探测 |
| `api_discovery.py` | API 自动发现 |
| `extract_api.py` | API 提取 |
| `extract_all_js.py` | JS 文件全量提取 |
| `deep_analysis.py` | 深度分析 |
| `deep_category.py` | 品类深度分析 |
| `analyze_debug.py` | 调试数据分析 |
| `analyze_html.py` | HTML 结构分析 |
| `analyze_pages.py` / `pages2` | 页面分析 |
| `debug_browser.py` | 浏览器调试 |
| `parse_jd_pages.py` | 京东页面解析 |
| `parse_category_tree.py` | 品类树解析 |
| `parse_snapshot_data.py` / `v2` | 快照数据解析 |
| `fetch_categories.py` | 品类数据获取 |

## 报告生成类

| 脚本 | 说明 |
|------|------|
| `generate_power_tools_report.py` | 电动工具报告 |
| `generate_final_report.py` | 最终报告 |
| `generate_comprehensive_report.py` | 综合报告 |
| `generate_html_report.py` | HTML 报告 |
| `generate_final_full_report.py` | 全量数据可视化报告 |
| `summary_report.py` | 摘要报告 |
| `final_comparison.py` | 策略对比 |

## 方案实验类

| 脚本 | 说明 |
|------|------|
| `solution1_test.py` | 方案1测试 |
| `solution1_cookie_injection.py` | 方案1 Cookie注入 |
| `solution23_api_test.py` | 方案23 API测试 |
| `solution23_more_test.py` | 方案23扩展测试 |
| `jd_union_api_template.py` | 京东联盟 API 模板 |
