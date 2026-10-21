"""
请求构造器模块

组装完整的京东 API 请求，自动注入 sign、h5st、uuid、Cookie 等参数。
"""

from __future__ import annotations

import json
import uuid as uuid_lib
from typing import Any, Dict, Optional

from .anti_detect import AntiDetect
from .cookie_manager import CookieManager
from .fingerprint import FingerprintGenerator
from .jsrpc_client import JSRPCClient
from .models import JDRequest, SignResponse
from .sign import generate_sign
from .tls_client import TLSClient
from .utils import setup_logger, timestamp_ms

logger = setup_logger(__name__)

# 京东 API 基础 URL
JD_API_BASE_URL = "https://api.m.jd.com/"

# 常见 functionId 及其配置
FUNCTION_CONFIGS = {
    "bizSearchCategoryList": {
        "method": "GET",
        "encryption_level": "medium",
        "requires_h5st": True,
        "requires_login": False,
    },
    "vendorQualificationQuery": {
        "method": "POST",
        "encryption_level": "high",
        "requires_h5st": True,
        "requires_login": False,
    },
    "supplierServiceProviderList": {
        "method": "GET",
        "encryption_level": "medium",
        "requires_h5st": True,
        "requires_login": False,
    },
    "jd_industry_news_list": {
        "method": "GET",
        "encryption_level": "low",
        "requires_h5st": False,
        "requires_login": False,
    },
    "promotionActivityDetail": {
        "method": "POST",
        "encryption_level": "high",
        "requires_h5st": True,
        "requires_login": True,
    },
}


class RequestBuilder:
    """京东 API 请求构造器"""

    def __init__(
        self,
        jsrpc_client: Optional[JSRPCClient] = None,
        cookie_manager: Optional[CookieManager] = None,
        tls_client: Optional[TLSClient] = None,
        anti_detect: Optional[AntiDetect] = None,
        fingerprint: Optional[FingerprintGenerator] = None,
        appid: str = "ebf5a3c8",
        client: str = "h5",
        client_version: str = "1.0.0",
    ):
        """
        初始化请求构造器

        Args:
            jsrpc_client: JSRPC 客户端（用于获取 h5st）
            cookie_manager: Cookie 管理器
            tls_client: TLS 客户端
            anti_detect: 反检测工具
            fingerprint: 指纹生成器
            appid: 应用 ID
            client: 客户端类型
            client_version: 客户端版本
        """
        self.jsrpc_client = jsrpc_client
        self.cookie_manager = cookie_manager
        self.tls_client = tls_client or TLSClient()
        self.anti_detect = anti_detect or AntiDetect()
        self.fingerprint = fingerprint or FingerprintGenerator()
        self.appid = appid
        self.client = client
        self.client_version = client_version

        logger.info("请求构造器初始化完成")

    def build_request(
        self,
        function_id: str,
        body: Optional[Dict[str, Any]] = None,
        include_h5st: bool = True,
        include_sign: bool = True,
        include_cookies: bool = True,
    ) -> JDRequest:
        """
        构建完整的京东 API 请求

        Args:
            function_id: 接口名称
            body: 业务参数
            include_h5st: 是否包含 h5st
            include_sign: 是否包含 sign
            include_cookies: 是否包含 Cookie

        Returns:
            JDRequest 对象
        """
        if body is None:
            body = {}

        # 获取或生成 UUID
        uuid = self.fingerprint.get_or_create_uuid()

        # 生成时间戳
        t = timestamp_ms()

        # 序列化 body
        body_str = json.dumps(body, separators=(",", ":"))

        # 生成 sign
        sign = ""
        if include_sign:
            sign, t = generate_sign(
                function_id=function_id,
                body=body_str,
                uuid=uuid,
                t=t,
                appid=self.appid,
                client=self.client,
                client_version=self.client_version,
            )

        # 获取 h5st
        h5st = ""
        if include_h5st and self.jsrpc_client:
            try:
                sign_response = self.jsrpc_client.get_h5st(
                    function_id=function_id,
                    body=body_str,
                    uuid=uuid,
                    t=t,
                )
                if sign_response.is_success:
                    h5st = sign_response.h5st
            except Exception as e:
                logger.warning(f"获取 h5st 失败，继续无 h5st 请求: {e}")

        # 获取 Cookie
        cookies = {}
        if include_cookies and self.cookie_manager:
            cookies = self.cookie_manager.get_all_cookies()

        # 构建请求对象
        request = JDRequest(
            function_id=function_id,
            body=body,
            uuid=uuid,
            sign=sign,
            h5st=h5st,
            t=t,
            appid=self.appid,
            client=self.client,
            client_version=self.client_version,
            cookies=cookies,
        )

        # 注入隐秘参数（文档第四章 4.4 节）
        self._inject_hidden_params(request)

        logger.debug(f"构建请求: functionId={function_id}, sign={sign[:16]}...")
        return request

    def _inject_hidden_params(self, request: JDRequest) -> None:
        """
        注入隐秘参数（文档第四章 4.4 节）

        京东常见隐秘参数：
        - x-api-eid: 设备标识，来自 Cookie 中的 eid
        - x-rp-client: 客户端标识，如 "pc" / "h5"
        - x-request-id: 唯一请求 ID，防重放

        缺少这些参数可能导致直接 403。
        """
        # x-api-eid: 从 Cookie 中的 eid 获取
        eid = ""
        if request.cookies and "eid" in request.cookies:
            eid = request.cookies["eid"]
        elif self.cookie_manager:
            eid = self.cookie_manager.get_cookie("eid") or ""
        request.x_api_eid = eid

        # x-rp-client: 根据 client 类型自动设置
        if self.client == "h5":
            request.x_rp_client = "h5"
        elif self.client == "pc":
            request.x_rp_client = "pc"
        else:
            request.x_rp_client = self.client

        # x-request-id: 生成唯一请求 ID（UUID v4 无连字符）
        request.x_request_id = uuid_lib.uuid4().hex

    def send_request(
        self,
        request: JDRequest,
        method: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        发送请求到京东 API

        Args:
            request: JDRequest 对象
            method: HTTP 方法（默认根据 functionId 自动选择）
            custom_headers: 自定义请求头

        Returns:
            响应 JSON
        """
        # 确定 HTTP 方法
        if method is None:
            func_config = FUNCTION_CONFIGS.get(request.function_id, {})
            method = func_config.get("method", "GET")

        # 构建请求头
        headers = self.anti_detect.build_stealth_headers()
        if custom_headers:
            headers.update(custom_headers)

        # 添加 Cookie 头
        if request.cookies:
            cookie_str = "; ".join(
                f"{k}={v}" for k, v in request.cookies.items()
            )
            headers["Cookie"] = cookie_str

        # 注入隐秘参数请求头（文档第四章 4.4 节）
        hidden_headers = request.get_hidden_headers()
        if hidden_headers:
            headers.update(hidden_headers)

        # 构建参数
        params = request.to_params()

        # 发送请求
        logger.info(f"发送请求: {method} {request.function_id}")

        if method.upper() == "GET":
            response = self.tls_client.get(
                JD_API_BASE_URL,
                params=params,
                headers=headers,
            )
        else:
            response = self.tls_client.post(
                JD_API_BASE_URL,
                data=params,
                headers=headers,
            )

        # 解析响应
        try:
            result = response.json()
            logger.debug(f"响应成功: {request.function_id}")
            return result
        except json.JSONDecodeError:
            logger.error(f"响应解析失败: {response.text[:200]}")
            return {"error": "invalid_response", "raw": response.text}

    def quick_fetch(
        self,
        function_id: str,
        body: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        快速采集（构建 + 发送一体化）

        Args:
            function_id: 接口名称
            body: 业务参数
            **kwargs: 传递给 build_request 的参数

        Returns:
            响应 JSON
        """
        request = self.build_request(function_id, body, **kwargs)
        return self.send_request(request)

    def get_function_info(self, function_id: str) -> Dict[str, Any]:
        """获取接口配置信息"""
        return FUNCTION_CONFIGS.get(
            function_id,
            {
                "method": "GET",
                "encryption_level": "unknown",
                "requires_h5st": False,
                "requires_login": False,
            },
        )

    def list_supported_functions(self) -> list:
        """列出所有支持的 functionId"""
        return list(FUNCTION_CONFIGS.keys())

    def close(self) -> None:
        """关闭所有客户端"""
        if self.tls_client:
            self.tls_client.close()
        if self.jsrpc_client:
            self.jsrpc_client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
