"""
京东 API sign 签名生成模块

实现京东 API 网关的 MD5 sign 签名算法（八元组公式）。
sign = md5(functionId + body + uuid + client + clientVersion + t + appid + token)
"""

from __future__ import annotations

import hashlib
import time
from typing import Optional

from .models import SignParams
from .utils import md5_hash, setup_logger, timestamp_ms

logger = setup_logger(__name__)

# 默认常量（H5 端）
DEFAULT_CLIENT = "h5"
DEFAULT_CLIENT_VERSION = "1.0.0"
DEFAULT_APPID = "ebf5a3c8"


def generate_sign(
    function_id: str,
    body: str,
    uuid: str,
    token: str = "",
    t: Optional[str] = None,
    client: str = DEFAULT_CLIENT,
    client_version: str = DEFAULT_CLIENT_VERSION,
    appid: str = DEFAULT_APPID,
) -> tuple[str, str]:
    """
    生成京东 API sign 签名

    Args:
        function_id: 接口名称，如 bizSearchCategoryList
        body: POST 业务参数的 JSON 字符串
        uuid: 设备 UUID
        token: 登录态 token（未登录时为空）
        t: 毫秒时间戳（默认自动生成）
        client: 客户端类型（H5 端固定为 h5）
        client_version: 客户端版本号
        appid: 应用 ID

    Returns:
        (sign_hash, timestamp) 元组

    Example:
        >>> sign, t = generate_sign(
        ...     function_id="bizSearchCategoryList",
        ...     body='{"cid":"0"}',
        ...     uuid="abc123def456..."
        ... )
    """
    if t is None:
        t = timestamp_ms()

    # 构造签名字符串（八元组公式）
    sign_string = (
        f"functionId={function_id}"
        f"&body={body}"
        f"&uuid={uuid}"
        f"&client={client}"
        f"&clientVersion={client_version}"
        f"&t={t}"
        f"&appid={appid}"
        f"&token={token}"
    )

    # 计算 MD5 哈希
    sign_hash = hashlib.md5(sign_string.encode("utf-8")).hexdigest()

    logger.debug(f"生成签名: functionId={function_id}, t={t}")
    logger.debug(f"签名字符串: {sign_string[:100]}...")
    logger.debug(f"签名结果: {sign_hash}")

    return sign_hash, t


def generate_sign_from_params(params: SignParams) -> tuple[str, str]:
    """
    从 SignParams 对象生成签名

    Args:
        params: 签名参数对象

    Returns:
        (sign_hash, timestamp) 元组
    """
    sign_string = params.to_sign_string()
    sign_hash = hashlib.md5(sign_string.encode("utf-8")).hexdigest()

    logger.debug(f"生成签名(对象模式): functionId={params.function_id}")

    return sign_hash, params.t


def verify_sign(
    sign_hash: str,
    function_id: str,
    body: str,
    uuid: str,
    t: str,
    token: str = "",
    client: str = DEFAULT_CLIENT,
    client_version: str = DEFAULT_CLIENT_VERSION,
    appid: str = DEFAULT_APPID,
) -> bool:
    """
    验证 sign 签名是否正确

    Args:
        sign_hash: 待验证的签名
        其他参数同 generate_sign

    Returns:
        签名是否有效
    """
    expected_sign, _ = generate_sign(
        function_id=function_id,
        body=body,
        uuid=uuid,
        token=token,
        t=t,
        client=client,
        client_version=client_version,
        appid=appid,
    )

    return sign_hash == expected_sign


def create_sign_params(
    function_id: str,
    body: str,
    uuid: str,
    token: str = "",
    **kwargs,
) -> SignParams:
    """
    创建 SignParams 对象的便捷工厂

    Args:
        function_id: 接口名称
        body: 业务参数 JSON 字符串
        uuid: 设备 UUID
        token: 登录态 token
        **kwargs: 其他可选参数（client, client_version, appid, t）

    Returns:
        SignParams 对象
    """
    return SignParams(
        function_id=function_id,
        body=body,
        uuid=uuid,
        token=token,
        client=kwargs.get("client", DEFAULT_CLIENT),
        client_version=kwargs.get("client_version", DEFAULT_CLIENT_VERSION),
        appid=kwargs.get("appid", DEFAULT_APPID),
        t=kwargs.get("t", timestamp_ms()),
    )
