#!/usr/bin/env python3
"""
京东工业招商网数据采集工具库 - CLI 入口

用法:
    python main.py sign-test          测试签名生成
    python main.py jsrpc-check        检查 JSRPC 服务连通性
    python main.py fetch <functionId> 执行数据采集
    python main.py demo               完整演示流程
    python main.py status             显示系统状态
"""

import argparse
import json
import sys
from pathlib import Path

# 项目路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from python.sign import generate_sign, verify_sign
from python.fingerprint import FingerprintGenerator
from python.anti_detect import AntiDetect
from python.cookie_manager import CookieManager
from python.request_builder import RequestBuilder
from python.jsrpc_client import JSRPCClient
from python.tls_client import TLSClientFactory
from python.utils import load_config, setup_logger

logger = setup_logger("main")


def cmd_sign_test(args):
    """测试签名生成"""
    print("=" * 50)
    print("  签名生成测试")
    print("=" * 50)

    uuid = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
    function_id = "bizSearchCategoryList"
    body = '{"cid":"0"}'

    sign, t = generate_sign(
        function_id=function_id,
        body=body,
        uuid=uuid,
    )

    print(f"\nfunctionId: {function_id}")
    print(f"body:       {body}")
    print(f"uuid:       {uuid}")
    print(f"timestamp:  {t}")
    print(f"sign:       {sign}")

    # 验证签名
    is_valid = verify_sign(
        sign_hash=sign,
        function_id=function_id,
        body=body,
        uuid=uuid,
        t=t,
    )
    print(f"\n签名验证:   {'通过' if is_valid else '失败'}")
    print("=" * 50)


def cmd_jsrpc_check(args):
    """检查 JSRPC 服务连通性"""
    print("=" * 50)
    print("  JSRPC 服务连通性检查")
    print("=" * 50)

    config = _load_config_safe()
    server_url = config.get("jsrpc", {}).get("server_url", "http://localhost:3000")

    client = JSRPCClient(server_url=server_url, timeout=5.0)

    print(f"\n服务地址: {server_url}")
    is_healthy = client.check_health()

    if is_healthy:
        print("服务状态: 正常")
    else:
        print("服务状态: 不可用")
        print("\n请确保 Node.js 签名服务已启动:")
        print("  cd node && npm install && node server.js")

    print("=" * 50)


def cmd_fetch(args):
    """执行数据采集"""
    function_id = args.function_id

    print("=" * 50)
    print(f"  数据采集: {function_id}")
    print("=" * 50)

    config = _load_config_safe()

    # 构建请求
    builder = RequestBuilder(jsrpc_client=None, cookie_manager=None)
    request = builder.build_request(
        function_id=function_id,
        body=args.body or {},
        include_h5st=False,  # 无 JSRPC 时跳过 h5st
    )

    params = request.to_params()
    print(f"\n请求参数:")
    for k, v in params.items():
        print(f"  {k}: {v[:80]}{'...' if len(str(v)) > 80 else ''}")

    print(f"\n提示: 完整采集需启动 JSRPC 签名服务")
    print("=" * 50)


def cmd_demo(args):
    """完整演示流程"""
    print("=" * 60)
    print("  京东数据采集工具库 - 完整演示")
    print("=" * 60)

    # 1. 设备指纹
    print("\n[1/5] 生成设备指纹...")
    fp_gen = FingerprintGenerator(platform="mobile")
    uuid = fp_gen.get_or_create_uuid()
    fingerprint = fp_gen.generate_fingerprint()
    print(f"  UUID: {uuid}")
    print(f"  UA:   {fingerprint.user_agent[:60]}...")

    # 2. 反检测配置
    print("\n[2/5] 配置反检测...")
    anti = AntiDetect(random_delay_range=(0.01, 0.02))
    headers = anti.build_stealth_headers()
    print(f"  UA:     {headers['User-Agent'][:60]}...")
    print(f"  Referer: {headers['Referer']}")

    # 3. Cookie 管理
    print("\n[3/5] 初始化 Cookie 管理...")
    cookie_mgr = CookieManager(auto_save=False)
    cookie_mgr.set_cookies({
        "__jda": "demo_jda_value",
        "jd-uuid": uuid,
    })
    status = cookie_mgr.get_status()
    print(f"  Cookie 数量: {status['total_cookies']}")
    print(f"  关键 Cookie: {sum(status['critical_cookies'].values())} 项已设置")

    # 4. 签名生成
    print("\n[4/5] 生成 API 签名...")
    function_id = "bizSearchCategoryList"
    body = '{"cid":"0"}'
    sign, t = generate_sign(
        function_id=function_id,
        body=body,
        uuid=uuid,
    )
    print(f"  functionId: {function_id}")
    print(f"  sign: {sign}")

    # 5. 请求构造
    print("\n[5/5] 构造完整请求...")
    builder = RequestBuilder(
        cookie_manager=cookie_mgr,
        anti_detect=anti,
        fingerprint=fp_gen,
    )
    request = builder.build_request(
        function_id=function_id,
        body={"cid": "0"},
        include_h5st=False,
    )
    params = request.to_params()
    print(f"  参数数量: {len(params)}")
    print(f"  完整参数:")
    for k, v in params.items():
        val_str = str(v)
        print(f"    {k}: {val_str[:60]}{'...' if len(val_str) > 60 else ''}")

    print("\n" + "=" * 60)
    print("  演示完成！")
    print("  注意: 未使用 JSRPC，h5st 参数为空。")
    print("  完整功能需启动 Node.js 签名服务。")
    print("=" * 60)


def cmd_status(args):
    """显示系统状态"""
    print("=" * 50)
    print("  系统状态")
    print("=" * 50)

    # Python 依赖检查
    print("\n[Python 依赖]")
    deps = {
        "yaml": "pyyaml",
        "requests": "requests",
        "httpx": "httpx",
        "curl_cffi": "curl_cffi",
        "pydantic": "pydantic",
    }
    for module, package in deps.items():
        try:
            __import__(module)
            print(f"  {package}: 已安装")
        except ImportError:
            print(f"  {package}: 未安装")

    # TLS 后端
    print("\n[TLS 后端]")
    backends = TLSClientFactory.available_backends()
    for name, available in backends.items():
        status = "可用" if available else "不可用"
        print(f"  {name}: {status}")

    # 配置文件
    print("\n[配置文件]")
    config_path = PROJECT_ROOT / "config" / "settings.yaml"
    print(f"  settings.yaml: {'存在' if config_path.exists() else '不存在'}")

    # Node.js 服务
    print("\n[Node.js 签名服务]")
    node_dir = PROJECT_ROOT / "node"
    print(f"  服务目录: {'存在' if node_dir.exists() else '不存在'}")

    config = _load_config_safe()
    server_url = config.get("jsrpc", {}).get("server_url", "http://localhost:3000")
    client = JSRPCClient(server_url=server_url, timeout=3.0)
    is_healthy = client.check_health()
    print(f"  服务状态: {'运行中' if is_healthy else '未启动'}")

    print("=" * 50)


def _load_config_safe():
    """安全加载配置"""
    try:
        return load_config()
    except FileNotFoundError:
        logger.warning("配置文件不存在，使用默认配置")
        return {}


def main():
    parser = argparse.ArgumentParser(
        description="京东工业招商网数据采集工具库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py sign-test          测试签名生成
  python main.py jsrpc-check        检查 JSRPC 服务
  python main.py fetch bizSearchCategoryList  采集数据
  python main.py demo               完整演示
  python main.py status             系统状态

合规警示: 本工具仅用于技术学习与研究目的。
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # sign-test
    subparsers.add_parser("sign-test", help="测试签名生成")

    # jsrpc-check
    subparsers.add_parser("jsrpc-check", help="检查 JSRPC 服务连通性")

    # fetch
    fetch_parser = subparsers.add_parser("fetch", help="执行数据采集")
    fetch_parser.add_argument("function_id", help="API functionId")
    fetch_parser.add_argument("--body", type=json.loads, default=None, help="业务参数 JSON")

    # demo
    subparsers.add_parser("demo", help="完整演示流程")

    # status
    subparsers.add_parser("status", help="显示系统状态")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    commands = {
        "sign-test": cmd_sign_test,
        "jsrpc-check": cmd_jsrpc_check,
        "fetch": cmd_fetch,
        "demo": cmd_demo,
        "status": cmd_status,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
