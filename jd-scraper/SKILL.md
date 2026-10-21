# AI+JS逆向京东工业网数据采集智能体

> **合规警示**: 本智能体仅用于技术学习与研究目的。未经授权批量采集可能违反《个人信息保护法》《反不正当竞争法》及平台用户协议。

## 概述

基于 jd-scraper v2.0 爬虫系统架构的 AI 智能体，具备以下核心能力：

1. **h5st 签名版本感知** — 自动识别 v1/v2/v3 版本，推荐最优签名策略
2. **JSRPC 签名服务编排** — 管理 Node.js 浏览器池生命周期
3. **MCP 五步法 API 嗅探** — 自动发现、分类、标记逆向目标
4. **生产级监控告警** — 签名失败率 / Cookie 过期 / IP 封禁 / h5st 版本变化
5. **三级降级策略** — JSRPC → 本地 sign → 直接请求自动切换
6. **反检测指纹管理** — Canvas/WebGL 扰动、Sec-CH-UA 一致性、Bezier 鼠标轨迹

## 触发条件

当用户提到以下关键词时激活本智能体：

- 京东数据采集、JD 爬虫、京东 API 逆向
- h5st 签名、JSRPC、京东反爬
- 京东工业品、招商网数据、zhaoshang.jd.com
- 签名失败率、Cookie 过期、IP 封禁
- 京东分类数据、商品搜索、品牌采集

## 工作流程

### Phase 1: 环境诊断

```
1. 检查 Python/Node.js 版本
2. 验证依赖安装 (pip install -r requirements.txt, cd node && npm install)
3. 检查 Playwright Chromium 浏览器
4. 加载 config/settings.yaml 配置
5. 输出环境就绪报告
```

### Phase 2: 服务启动

```
1. 启动 Node.js JSRPC 签名服务 (node server.js)
2. 验证健康检查 (GET /health)
3. 确认浏览器池 Worker 就绪
4. 初始化 Python 端各模块
```

### Phase 3: API 嗅探

```
1. 打开目标页面 (zhaoshang.jd.com)
2. 拦截所有 API 流量
3. 触发业务操作 (搜索/翻页/筛选)
4. 参数自动分类 (签名/时间戳/业务/设备/会话)
5. 标记逆向目标 (含 h5st/sign 的接口)
6. 生成嗅探报告 (Markdown)
```

### Phase 4: 签名策略选型

```
h5st 版本检测 → 策略推荐:
  v1 (2020-2021) → 纯 Python MD5 (high reliability)
  v2 (2022-2023) → JSRPC 远程调用 (recommended)
  v3 (2024-2026) → Playwright 兜底 (medium reliability)
  unknown         → JSRPC (default)
```

### Phase 5: 数据采集执行

```
1. 构造请求 (RequestBuilder)
   - 注入 functionId / body / uuid / timestamp
   - 注入隐秘参数 (x-api-eid / x-rp-client / x-request-id)
   - 生成 Sec-CH-UA 一致性头
2. 签名生成
   - 优先 JSRPC → 降级本地 sign → 兜底直接请求
3. 发送请求 (curl_cffi / httpx)
4. 解析响应 → 存储到 data/
5. 监控指标上报
```

### Phase 6: 持续监控

```
监控维度:
  - 签名失败率 > 10% → WARNING 告警
  - IP 封禁率 > 20% → CRITICAL 告警 (建议切换代理)
  - Cookie 即将过期 (thor/ctoken 2h) → WARNING
  - h5st 版本变化 → CRITICAL (需重新逆向)
```

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    AI 智能体 (agent.py)                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
│  │ h5st     │ │ API      │ │ 生产     │ │ 降级策略   │ │
│  │ 解析器   │ │ 嗅探器   │ │ 监控器   │ │ 引擎       │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬──────┘ │
└───────┼────────────┼────────────┼──────────────┼────────┘
        │            │            │              │
┌───────┴────────────┴────────────┴──────────────┴────────┐
│              Python 核心库 (python/)                      │
│  sign.py │ models.py │ request_builder.py │ jsrpc_client │
│  tls_client.py │ cookie_manager.py │ fingerprint.py      │
│  anti_detect.py │ utils.py                               │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP/JSON
┌────────────────────────┴────────────────────────────────┐
│              Node.js 签名服务 (node/)                     │
│  server.js (Express :3000)                               │
│  ├── browser_pool.js (Playwright 池, size=3)             │
│  ├── sign_worker.js (h5st 签名执行)                      │
│  └── stealth.js (Canvas/WebGL/鼠标轨迹反检测)            │
└─────────────────────────────────────────────────────────┘
```

## 关键文件索引

| 文件 | 职责 |
|------|------|
| `python/h5st_parser.py` | h5st 版本检测与策略推荐 |
| `python/monitor.py` | 签名失败率/Cookie/IP 监控 |
| `python/api_sniffer.py` | MCP 五步法 API 嗅探 |
| `python/anti_detect.py` | Sec-CH-UA 一致性 + 反检测头 |
| `python/cookie_manager.py` | Cookie 池 + 自动刷新守护线程 |
| `python/request_builder.py` | 请求构造 + 隐秘参数注入 |
| `python/jsrpc_client.py` | JSRPC 客户端 + 降级逻辑 |
| `node/stealth.js` | Canvas 像素扰动 + WebGL 覆盖 + Bezier 鼠标 |
| `node/browser_pool.js` | Playwright 池管理 + 信号量限流 |
| `config/settings.yaml` | 统一配置（API/JSRPC/浏览器池/监控） |

## 命令参考

```bash
# 环境诊断
python main.py status

# 签名测试
python main.py sign-test

# JSRPC 连通性检查
python main.py jsrpc-check

# 完整演示
python main.py demo

# 数据采集
python main.py fetch <functionId> [--body '{}']

# 启动签名服务
cd node && node server.js

# 运行测试
python -m pytest tests/ -v
```

## 已知限制

1. **dc.3.cn/category/get** 是唯一无需认证的公开 API
2. **api.m.jd.com** 所有 functionId 调用需有效登录态 + h5st
3. **search/item/list 页面** 触发反爬验证（需 Cookie 注入）
4. **h5st 签名函数** 需从京东页面动态加载，非硬编码
5. **thor/ctoken Cookie** 有效期仅 2 小时，需持续刷新
