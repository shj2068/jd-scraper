"""
JSRPC 客户端模块

通过 HTTP 调用 Node.js 签名服务，获取 h5st 签名。
支持批量请求、重试机制、降级策略。
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import SignResponse
from .utils import retry, setup_logger

logger = setup_logger(__name__)


class JSRPCClient:
    """JSRPC 客户端（调用 Node.js 签名服务）"""

    def __init__(
        self,
        server_url: str = "http://localhost:3000",
        timeout: float = 10.0,
        max_retries: int = 3,
        enable_fallback: bool = True,
    ):
        """
        初始化 JSRPC 客户端

        Args:
            server_url: Node.js 签名服务地址
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            enable_fallback: 是否启用降级（JSRPC 失败时使用本地签名）
        """
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.enable_fallback = enable_fallback
        self._session = None

        logger.info(f"JSRPC 客户端初始化: server={server_url}")

    def _get_session(self):
        """获取 HTTP 会话"""
        if self._session is None:
            import requests

            self._session = requests.Session()
            self._session.headers.update(
                {"Content-Type": "application/json"}
            )
        return self._session

    @retry(max_retries=3, delay=1.0, backoff=2.0)
    def get_h5st(
        self,
        function_id: str,
        body: str,
        uuid: str,
        t: Optional[str] = None,
    ) -> SignResponse:
        """
        获取 h5st 签名

        Args:
            function_id: 接口名称
            body: 业务参数 JSON 字符串
            uuid: 设备 UUID
            t: 时间戳（默认自动生成）

        Returns:
            SignResponse 对象
        """
        if t is None:
            t = str(int(time.time() * 1000))

        url = f"{self.server_url}/sign"
        payload = {
            "functionId": function_id,
            "body": body,
            "t": t,
            "uuid": uuid,
        }

        logger.debug(f"请求 h5st: functionId={function_id}")

        try:
            session = self._get_session()
            response = session.post(
                url,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            sign_response = SignResponse.from_dict(data)

            if sign_response.is_success:
                logger.debug(f"获取 h5st 成功: {sign_response.h5st[:30]}...")
            else:
                logger.warning(f"获取 h5st 失败: {sign_response.error}")

            return sign_response

        except Exception as e:
            logger.error(f"JSRPC 请求失败: {e}")

            if self.enable_fallback:
                logger.info("启用降级策略：使用本地签名")
                return self._fallback_sign(function_id, body, uuid, t)

            raise

    def _fallback_sign(
        self,
        function_id: str,
        body: str,
        uuid: str,
        t: str,
    ) -> SignResponse:
        """降级签名（仅生成 sign，无 h5st）"""
        from .sign import generate_sign

        sign_hash, _ = generate_sign(
            function_id=function_id,
            body=body,
            uuid=uuid,
            t=t,
        )

        return SignResponse(
            code=0,
            h5st="",  # 降级模式无 h5st
            sign=sign_hash,
            t=t,
        )

    def get_h5st_batch(
        self,
        requests: List[Dict[str, str]],
        max_workers: int = 5,
    ) -> List[SignResponse]:
        """
        批量获取 h5st 签名

        Args:
            requests: 请求列表，每项包含 functionId, body, uuid
            max_workers: 最大并发数

        Returns:
            SignResponse 列表
        """
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self.get_h5st,
                    req["functionId"],
                    req["body"],
                    req["uuid"],
                    req.get("t"),
                ): req
                for req in requests
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"批量签名失败: {e}")
                    results.append(
                        SignResponse(code=-1, error=str(e))
                    )

        logger.info(f"批量签名完成: {len(results)} 项")
        return results

    def check_health(self) -> bool:
        """
        检查签名服务健康状态

        Returns:
            服务是否可用
        """
        url = f"{self.server_url}/health"

        try:
            session = self._get_session()
            response = session.get(url, timeout=5.0)
            data = response.json()

            is_healthy = data.get("status") == "ok"
            logger.info(f"签名服务健康检查: {'正常' if is_healthy else '异常'}")
            return is_healthy

        except Exception as e:
            logger.warning(f"签名服务不可用: {e}")
            return False

    def inject_cookies(self, cookies: Dict[str, str]) -> bool:
        """
        向签名服务注入 Cookie

        Args:
            cookies: Cookie 字典

        Returns:
            是否成功
        """
        url = f"{self.server_url}/cookie/inject"

        try:
            session = self._get_session()
            response = session.post(
                url,
                json={"cookies": cookies},
                timeout=self.timeout,
            )
            data = response.json()
            return data.get("code") == 0

        except Exception as e:
            logger.error(f"Cookie 注入失败: {e}")
            return False

    def close(self) -> None:
        """关闭客户端"""
        if self._session is not None:
            self._session.close()
            self._session = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class JSRPCClientFactory:
    """JSRPC 客户端工厂"""

    @staticmethod
    def from_config(config: Dict[str, Any]) -> JSRPCClient:
        """从配置创建客户端"""
        jsrpc_config = config.get("jsrpc", {})
        return JSRPCClient(
            server_url=jsrpc_config.get("server_url", "http://localhost:3000"),
            timeout=jsrpc_config.get("timeout", 10.0),
            max_retries=jsrpc_config.get("retry", 3),
        )
