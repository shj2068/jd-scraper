"""
数据模型定义

定义京东 API 请求/响应的结构化数据模型，使用 Pydantic 进行类型验证。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FunctionId(str, Enum):
    """京东工业招商网常见 API functionId 对照表"""

    BIZ_SEARCH_CATEGORY_LIST = "bizSearchCategoryList"
    VENDOR_QUALIFICATION_QUERY = "vendorQualificationQuery"
    SUPPLIER_SERVICE_PROVIDER_LIST = "supplierServiceProviderList"
    JD_INDUSTRY_NEWS_LIST = "jd_industry_news_list"
    PROMOTION_ACTIVITY_DETAIL = "promotionActivityDetail"

    @classmethod
    def get_encryption_level(cls, func_id: str) -> str:
        """获取接口的加密等级"""
        levels = {
            cls.BIZ_SEARCH_CATEGORY_LIST.value: "medium",
            cls.VENDOR_QUALIFICATION_QUERY.value: "high",
            cls.SUPPLIER_SERVICE_PROVIDER_LIST.value: "medium",
            cls.JD_INDUSTRY_NEWS_LIST.value: "low",
            cls.PROMOTION_ACTIVITY_DETAIL.value: "high",
        }
        return levels.get(func_id, "unknown")


class DegradationLevel(str, Enum):
    """降级策略级别"""

    LEVEL1_JSRPC = "jsrpc"
    LEVEL2_LOCAL_SIGN = "local_sign"
    LEVEL3_DIRECT = "direct"


@dataclass
class SignParams:
    """签名参数结构（八元组）"""

    function_id: str
    body: str
    uuid: str
    client: str = "h5"
    client_version: str = "1.0.0"
    t: str = ""
    appid: str = "ebf5a3c8"
    token: str = ""

    def __post_init__(self):
        if not self.t:
            self.t = str(int(time.time() * 1000))

    def to_sign_string(self) -> str:
        """生成用于 MD5 计算的签名字符串"""
        return (
            f"functionId={self.function_id}"
            f"&body={self.body}"
            f"&uuid={self.uuid}"
            f"&client={self.client}"
            f"&clientVersion={self.client_version}"
            f"&t={self.t}"
            f"&appid={self.appid}"
            f"&token={self.token}"
        )


@dataclass
class JDRequest:
    """完整京东 API 请求结构"""

    function_id: str
    body: Dict[str, Any]
    uuid: str
    sign: str = ""
    h5st: str = ""
    t: str = ""
    appid: str = "ebf5a3c8"
    client: str = "h5"
    client_version: str = "1.0.0"
    method: str = "GET"
    cookies: Dict[str, str] = field(default_factory=dict)
    extra_headers: Dict[str, str] = field(default_factory=dict)
    # 隐秘参数（文档第四章 4.4 节）
    x_api_eid: str = ""  # 设备标识，来自 Cookie eid
    x_rp_client: str = ""  # 客户端标识，如 "pc"
    x_request_id: str = ""  # 唯一请求 ID，防重放

    def __post_init__(self):
        if not self.t:
            self.t = str(int(time.time() * 1000))

    def to_params(self) -> Dict[str, str]:
        """转换为 URL 查询参数"""
        import json

        params = {
            "functionId": self.function_id,
            "appid": self.appid,
            "client": self.client,
            "clientVersion": self.client_version,
            "t": self.t,
            "uuid": self.uuid,
        }
        if self.sign:
            params["sign"] = self.sign
        if self.h5st:
            params["h5st"] = self.h5st
        if self.body:
            params["body"] = json.dumps(self.body, separators=(",", ":"))
        return params

    def get_hidden_headers(self) -> Dict[str, str]:
        """
        获取隐秘参数请求头（文档第四章 4.4 节）

        京东常见隐秘参数：x-api-eid、x-rp-client、x-request-id
        缺少这些参数可能导致直接 403。
        """
        headers = {}
        if self.x_api_eid:
            headers["x-api-eid"] = self.x_api_eid
        if self.x_rp_client:
            headers["x-rp-client"] = self.x_rp_client
        if self.x_request_id:
            headers["x-request-id"] = self.x_request_id
        return headers

    def get_body_json(self) -> str:
        """获取 body 的 JSON 字符串"""
        import json

        return json.dumps(self.body, separators=(",", ":"))


@dataclass
class SignResponse:
    """JSRPC 签名服务响应"""

    code: int
    h5st: str = ""
    sign: str = ""
    t: str = ""
    error: str = ""

    @property
    def is_success(self) -> bool:
        return self.code == 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SignResponse:
        return cls(
            code=data.get("code", -1),
            h5st=data.get("h5st", ""),
            sign=data.get("sign", ""),
            t=data.get("t", ""),
            error=data.get("error", ""),
        )


@dataclass
class CookieEntry:
    """单个 Cookie 条目"""

    name: str
    value: str
    domain: str = ".jd.com"
    path: str = "/"
    expires: float = -1.0
    created_at: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        if self.expires < 0:
            return False
        return time.time() > self.expires

    @property
    def ttl(self) -> float:
        """剩余有效时间（秒）"""
        if self.expires < 0:
            return float("inf")
        return max(0, self.expires - time.time())


@dataclass
class CookieJar:
    """Cookie 管理器模型"""

    cookies: Dict[str, CookieEntry] = field(default_factory=dict)
    account_id: str = "default"

    def set(self, name: str, value: str, expires: float = -1.0) -> None:
        """设置 Cookie"""
        self.cookies[name] = CookieEntry(
            name=name, value=value, expires=expires
        )

    def get(self, name: str) -> Optional[str]:
        """获取 Cookie 值"""
        entry = self.cookies.get(name)
        if entry and not entry.is_expired:
            return entry.value
        return None

    def remove(self, name: str) -> bool:
        """移除 Cookie"""
        if name in self.cookies:
            del self.cookies[name]
            return True
        return False

    def clear_expired(self) -> int:
        """清理过期 Cookie，返回清理数量"""
        expired = [k for k, v in self.cookies.items() if v.is_expired]
        for k in expired:
            del self.cookies[k]
        return len(expired)

    def to_header_string(self) -> str:
        """转换为 HTTP Cookie 头字符串"""
        valid = [
            f"{k}={v.value}"
            for k, v in self.cookies.items()
            if not v.is_expired
        ]
        return "; ".join(valid)

    def to_dict(self) -> Dict[str, str]:
        """转换为字典（仅有效 Cookie）"""
        return {
            k: v.value for k, v in self.cookies.items() if not v.is_expired
        }

    @property
    def count(self) -> int:
        return len(self.cookies)

    @property
    def valid_count(self) -> int:
        return sum(1 for v in self.cookies.values() if not v.is_expired)


@dataclass
class BrowserFingerprint:
    """浏览器设备指纹"""

    user_agent: str
    platform: str = "Win32"
    language: str = "zh-CN"
    languages: List[str] = field(default_factory=lambda: ["zh-CN", "zh", "en"])
    hardware_concurrency: int = 8
    device_memory: int = 8
    screen_width: int = 1920
    screen_height: int = 1080
    color_depth: int = 24
    pixel_ratio: float = 1.0
    timezone: str = "Asia/Shanghai"
    canvas_hash: str = ""
    webgl_vendor: str = ""
    webgl_renderer: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "userAgent": self.user_agent,
            "platform": self.platform,
            "language": self.language,
            "languages": self.languages,
            "hardwareConcurrency": self.hardware_concurrency,
            "deviceMemory": self.device_memory,
            "screenWidth": self.screen_width,
            "screenHeight": self.screen_height,
            "colorDepth": self.color_depth,
            "pixelRatio": self.pixel_ratio,
            "timezone": self.timezone,
            "canvasHash": self.canvas_hash,
            "webglVendor": self.webgl_vendor,
            "webglRenderer": self.webgl_renderer,
        }
