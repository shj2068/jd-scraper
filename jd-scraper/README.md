# jd-scraper - 京东工业招商网数据采集工具库

基于 JSRPC 架构的京东 API 数据采集工具，支持 h5st 签名生成、TLS 指纹模拟、反检测配置。

> **合规警示**: 本工具仅用于技术学习与研究目的。未经授权批量采集可能违反《个人信息保护法》《反不正当竞争法》及平台用户协议。

## 架构概览

```
Python 客户端  <--HTTP/JSON-->  Node.js 签名服务
(请求构造/签名)                  (Playwright 浏览器池)
     |                                |
     v                                v
 curl_cffi (TLS指纹)           Chromium (h5st生成)
```

核心流程:
1. Python 端构造请求参数 (functionId, body, uuid)
2. 通过 JSRPC 调用 Node.js 签名服务获取 h5st
3. Node.js 在真实浏览器中执行 h5st 生成函数
4. Python 端组装完整请求并发送

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+

### 安装

```bash
# Python 依赖
pip install -r requirements.txt

# Node.js 依赖
cd node && npm install && cd ..
```

### 运行测试

```bash
python -m pytest tests/ -v
```

### CLI 使用

```bash
# 测试签名生成
python main.py sign-test

# 检查 JSRPC 服务
python main.py jsrpc-check

# 完整演示
python main.py demo

# 系统状态
python main.py status

# 数据采集 (需要 JSRPC 服务)
python main.py fetch bizSearchCategoryList
```

### 启动签名服务

```bash
cd node
node server.js
```

## 项目结构

```
jd-scraper/
├── config/settings.yaml      # 统一配置
├── python/                   # Python 核心库
│   ├── sign.py               # MD5 sign 签名
│   ├── models.py             # 数据模型
│   ├── request_builder.py    # 请求构造器
│   ├── jsrpc_client.py       # JSRPC 客户端
│   ├── tls_client.py         # TLS 指纹模拟
│   ├── cookie_manager.py     # Cookie 池管理
│   ├── fingerprint.py        # 设备指纹
│   ├── anti_detect.py        # 反检测工具
│   └── utils.py              # 工具函数
├── node/                     # Node.js 签名服务
│   ├── server.js             # Express 服务
│   ├── browser_pool.js       # 浏览器池
│   ├── stealth.js            # 反检测注入
│   └── sign_worker.js        # 签名执行
├── tests/                    # 测试套件
├── main.py                   # CLI 入口
└── requirements.txt          # Python 依赖
```

## 模块说明

| 模块 | 功能 |
|------|------|
| `sign.py` | 京东 API sign 八元组 MD5 签名 |
| `jsrpc_client.py` | JSRPC 客户端，调用 Node.js 获取 h5st |
| `tls_client.py` | curl_cffi TLS 指纹模拟 (JA3/JA4) |
| `cookie_manager.py` | Cookie 池管理，持久化，多账号轮换 |
| `fingerprint.py` | 设备指纹生成 (UUID/Canvas/WebGL) |
| `anti_detect.py` | UA 轮换、请求头标准化、时序模拟 |
| `request_builder.py` | 完整请求构造，自动注入所有参数 |

## 降级策略

| 级别 | 方案 | 说明 |
|------|------|------|
| 一级 | JSRPC | 浏览器池生成 h5st，成功率最高 |
| 二级 | 本地 sign | 仅生成 sign，无 h5st |
| 三级 | 直接请求 | 无签名，仅低敏感接口可用 |

## 配置

编辑 `config/settings.yaml` 自定义:
- API 参数 (appid, client)
- JSRPC 服务地址与超时
- 浏览器池大小
- 反检测参数
- 降级策略

## 合规自查

使用前请确认:
- [ ] 遵守 robots.txt 与平台服务条款
- [ ] 采集频率合理，不影响服务器运行
- [ ] 仅采集公开页面数据
- [ ] 不采集个人信息
- [ ] 不用于商业竞争
- [ ] 已咨询法务确认合规

## License

MIT - 仅用于技术学习与研究
