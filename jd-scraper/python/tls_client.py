"""
TLS 指纹模拟模块

基于 curl_cffi 模拟 Chrome TLS 指纹（JA3/JA4），绕过京东风控检测。
当 curl_cffi 不可用时，回退到 httpx。
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from .utils import setup_logger
from .proxy_pool import ProxyPool

logger = setup_logger(__name__)

# TLS 指纹预设配置
TLS_PRESETS = {
    "chrome116": "chrome116",
    "chrome118": "chrome118",
    "chrome120": "chrome120",
    "chrome123": "chrome123",
    "chrome124": "chrome124",
    "safari_ios": "safari_ios",
    "safari": "safari",
}


class TLSClient:
    """TLS 指纹模拟客户端"""

    def __init__(
        self,
        tls_preset: str = "chrome118",
        timeout: float = 30.0,
        proxy: Optional[str] = None,
        proxy_pool: Optional[ProxyPool] = None,
    ):
        """
        初始化 TLS 客户端

        Args:
            tls_preset: TLS 指纹预设名称
            timeout: 请求超时时间（秒）
            proxy: 代理地址（如 http://127.0.0.1:8080）
            proxy_pool: 代理池实例（优先于 proxy 参数）
        """
        self.tls_preset = tls_preset
        self.timeout = timeout
        self.proxy = proxy
        self.proxy_pool = proxy_pool
        self._session = None
        self._backend = self._detect_backend()

        logger.info(f"TLS 客户端初始化: backend={self._backend}, preset={tls_preset}")

    def _detect_backend(self) -> str:
        """检测可用的 HTTP 后端"""
        try:
            import curl_cffi.requests  # type: ignore

            return "curl_cffi"
        except ImportError:
            logger.warning("curl_cffi 未安装，回退到 httpx")
            try:
                import httpx  # type: ignore  # noqa: F401

                return "httpx"
            except ImportError:
                logger.warning("httpx 未安装，回退到 requests")
                return "requests"

    def _resolve_proxy(self) -> Optional[str]:
        if self.proxy_pool:
            return self.proxy_pool.get_proxy_url()
        return self.proxy

    def _get_session(self):
        """获取或创建 HTTP 会话"""
        proxy = self._resolve_proxy()

        if self._backend == "curl_cffi":
            from curl_cffi import requests as curl_requests  # type: ignore

            self._session = curl_requests.Session(
                impersonate=self.tls_preset,
                timeout=self.timeout,
                proxies={"http": proxy, "https": proxy} if proxy else None,
            )
        elif self._backend == "httpx":
            import httpx

            self._session = httpx.Client(
                timeout=self.timeout,
                proxy=proxy,
                headers=self._default_headers(),
            )
        else:
            import requests

            self._session = requests.Session()
            self._session.headers.update(self._default_headers())
            if proxy:
                self._session.proxies = {"http": proxy, "https": proxy}

        return self._session

    def _default_headers(self) -> Dict[str, str]:
        """默认请求头"""
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "X-Requested-With": "XMLHttpRequest",
        }

    def get(
        self,
        url: str,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Any:
        """
        发送 GET 请求

        Args:
            url: 请求 URL
            params: URL 查询参数
            headers: 请求头
            cookies: Cookie
            **kwargs: 其他参数

        Returns:
            响应对象
        """
        session = self._get_session()

        request_kwargs = {
            "params": params,
            "headers": headers,
            "cookies": cookies,
            "timeout": kwargs.get("timeout", self.timeout),
        }

        if self._backend == "curl_cffi":
            # curl_cffi 使用 impersonate 参数
            request_kwargs["impersonate"] = self.tls_preset

        logger.debug(f"GET {url} params={params}")
        response = session.get(url, **request_kwargs)
        logger.debug(f"响应状态: {response.status_code}")

        return response

    def post(
        self,
        url: str,
        data: Optional[Dict] = None,
        json: Optional[Dict] = None,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Any:
        """
        发送 POST 请求

        Args:
            url: 请求 URL
            data: 表单数据
            json: JSON 数据
            params: URL 查询参数
            headers: 请求头
            cookies: Cookie
            **kwargs: 其他参数

        Returns:
            响应对象
        """
        session = self._get_session()

        request_kwargs = {
            "data": data,
            "json": json,
            "params": params,
            "headers": headers,
            "cookies": cookies,
            "timeout": kwargs.get("timeout", self.timeout),
        }

        if self._backend == "curl_cffi":
            request_kwargs["impersonate"] = self.tls_preset

        logger.debug(f"POST {url}")
        response = session.post(url, **request_kwargs)
        logger.debug(f"响应状态: {response.status_code}")

        return response

    def close(self) -> None:
        """关闭会话"""
        if self._session is not None:
            self._session.close()
            self._session = None
            logger.debug("TLS 客户端会话已关闭")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class TLSClientFactory:
    """TLS 客户端工厂"""

    @staticmethod
    def create(
        preset: str = "chrome118",
        timeout: float = 30.0,
        proxy: Optional[str] = None,
    ) -> TLSClient:
        """创建 TLS 客户端实例"""
        return TLSClient(tls_preset=preset, timeout=timeout, proxy=proxy)

    @staticmethod
    def available_backends() -> Dict[str, bool]:
        """检查可用的 HTTP 后端"""
        backends = {}

        try:
            import curl_cffi  # type: ignore  # noqa: F401

            backends["curl_cffi"] = True
        except ImportError:
            backends["curl_cffi"] = False

        try:
            import httpx  # type: ignore  # noqa: F401

            backends["httpx"] = True
        except ImportError:
            backends["httpx"] = False

        try:
            import requests  # type: ignore  # noqa: F401

            backends["requests"] = True
        except ImportError:
            backends["requests"] = False

        return backends
