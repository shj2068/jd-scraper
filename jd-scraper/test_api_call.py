#!/usr/bin/env python3
"""测试 API 调用"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from python.jsrpc_client import JSRPCClient
from python.request_builder import RequestBuilder
from python.tls_client import TLSClient
from python.cookie_manager import CookieManager
from python.fingerprint import FingerprintGenerator
from python.anti_detect import AntiDetect

# 初始化组件
jsrpc = JSRPCClient(server_url="http://localhost:3001")
fingerprint = FingerprintGenerator()
cookie_mgr = CookieManager()
anti_detect = AntiDetect()
tls = TLSClient(tls_preset="chrome120")

builder = RequestBuilder(
    jsrpc_client=jsrpc,
    fingerprint=fingerprint,
    cookie_manager=cookie_mgr,
    appid="ebf5a3c8",
    client="h5",
    client_version="1.0.0",
)

# Debug: check what cookies are available
all_cookies = cookie_mgr.get_all_cookies()
print(f"Cookie 管理器返回: {len(all_cookies)} 个 Cookie")
if all_cookies:
    print(f"  Cookie 名称: {list(all_cookies.keys())[:10]}")
else:
    print("  (空)")

# 构建请求
function_id = "searchWareBusiness"
body = {"keyword": "电钻", "page": "1", "pageSize": "20"}

print(f"构建请求: {function_id}")
request = builder.build_request(
    function_id=function_id,
    body=body,
    include_h5st=True,
    include_sign=True,
    include_cookies=True,
)

params = request.to_params()
cookies = request.cookies or {}

print(f"\n请求参数:")
print(f"  functionId: {params.get('functionId')}")
print(f"  h5st length: {len(params.get('h5st', ''))}")
print(f"  sign: {params.get('sign', '')[:32]}...")
print(f"  t: {params.get('t')}")
print(f"  uuid: {params.get('uuid')}")
print(f"  body: {params.get('body')}")
print(f"  cookies count: {len(cookies)}")

# 发送请求
api_url = "https://api.m.jd.com/"
headers = anti_detect.build_headers()
headers["Content-Type"] = "application/x-www-form-urlencoded"

print(f"\n发送请求到: {api_url}")
resp = tls.post(api_url, data=params, headers=headers, cookies=cookies)

print(f"\n响应状态码: {resp.status_code}")
print(f"响应头: {dict(resp.headers)}")
print(f"\n响应体:")
try:
    resp_json = resp.json()
    print(json.dumps(resp_json, indent=2, ensure_ascii=False)[:2000])
except:
    print(resp.text[:2000])
