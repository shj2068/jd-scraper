"""
MCP 智能 API 嗅探器模块

通过 Chrome DevTools Protocol (CDP) 自动嗅探京东站点的 API 接口，
自动分类参数类型（业务参数/时间戳/签名/设备标识/会话），标记需逆向的目标。

文档参考: AI-JS逆向京东工业招商网数据采集实战指南 - 第一章 1.2 节
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from .utils import setup_logger

logger = setup_logger(__name__)


class ParamType(str, Enum):
    """参数类型分类"""

    BUSINESS = "business"  # 业务参数（keyword, page, pageSize）
    TIMESTAMP = "timestamp"  # 时间戳
    SIGNATURE = "signature"  # 核心签名（h5st, sign）
    DEVICE_ID = "device_id"  # 设备标识（eid, fp, uuid）
    SESSION = "session"  # 会话参数（thor, ctoken, token）
    CLIENT_INFO = "client_info"  # 客户端信息（client, clientVersion, appid）
    UNKNOWN = "unknown"


# 参数名 → 类型映射规则
PARAM_TYPE_RULES: Dict[str, ParamType] = {
    # 签名
    "h5st": ParamType.SIGNATURE,
    "sign": ParamType.SIGNATURE,
    # 时间戳
    "t": ParamType.TIMESTAMP,
    "timestamp": ParamType.TIMESTAMP,
    # 设备标识
    "eid": ParamType.DEVICE_ID,
    "fp": ParamType.DEVICE_ID,
    "uuid": ParamType.DEVICE_ID,
    "jd-uuid": ParamType.DEVICE_ID,
    # 会话
    "thor": ParamType.SESSION,
    "ctoken": ParamType.SESSION,
    "token": ParamType.SESSION,
    "pt_key": ParamType.SESSION,
    "pt_pin": ParamType.SESSION,
    # 客户端信息
    "client": ParamType.CLIENT_INFO,
    "clientVersion": ParamType.CLIENT_INFO,
    "appid": ParamType.CLIENT_INFO,
    "functionId": ParamType.BUSINESS,
}

# 业务参数名模式
BUSINESS_PARAM_PATTERNS = [
    re.compile(r"^(keyword|key|q|query)$", re.I),
    re.compile(r"^(page|pageNum|pageIndex|pageSize|limit|offset)$", re.I),
    re.compile(r"^(cid|categoryId|brandId|shopId)$", re.I),
    re.compile(r"^(sort|order|orderBy)$", re.I),
    re.compile(r"^(body|data|params|payload)$", re.I),
]


@dataclass
class DiscoveredAPI:
    """嗅探到的 API 接口信息"""

    url: str
    method: str = "GET"
    host: str = ""
    path: str = ""
    params: Dict[str, ParamType] = field(default_factory=dict)
    post_data: Optional[Dict[str, Any]] = None
    response_status: int = 0
    response_size: int = 0
    timestamp: float = field(default_factory=time.time)
    needs_reverse: bool = False  # 是否需要逆向
    reverse_target: str = ""  # 需要逆向的参数名
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "url": self.url,
            "method": self.method,
            "host": self.host,
            "path": self.path,
            "params": {k: v.value for k, v in self.params.items()},
            "needs_reverse": self.needs_reverse,
            "reverse_target": self.reverse_target,
            "tags": self.tags,
            "response_status": self.response_status,
            "response_size": self.response_size,
        }


@dataclass
class SniffResult:
    """嗅探结果汇总"""

    apis: List[DiscoveredAPI] = field(default_factory=list)
    total_requests: int = 0
    api_count: int = 0
    signature_params: List[str] = field(default_factory=list)
    reverse_targets: List[str] = field(default_factory=list)
    sniff_duration: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "summary": {
                "total_requests": self.total_requests,
                "api_count": self.api_count,
                "sniff_duration_seconds": round(self.sniff_duration, 2),
                "signature_params": self.signature_params,
                "reverse_targets": self.reverse_targets,
            },
            "apis": [api.to_dict() for api in self.apis],
        }


class APISniffer:
    """
    API 智能嗅探器

    工作流程（文档 1.2 节 MCP 智能嗅探五步法）：
    1. 打开页面 → 导航到目标站点
    2. 拦截流量 → 拦截所有 /api/ 请求
    3. 触发业务 → 模拟搜索/翻页/筛选
    4. 参数分析 → 识别签名/时间戳/业务参数
    5. 标记目标 → 标记需要逆向的加密参数
    """

    # 京东 API 域名模式
    JD_API_PATTERNS = [
        re.compile(r"api\.m\.jd\.com"),
        re.compile(r"api\.jd\.com"),
        re.compile(r"industry-api\.jd\.com"),
        re.compile(r"zhaoshang\.jd\.com"),
        re.compile(r"dc\.3\.cn"),
        re.compile(r"api\.m\.jd\.com"),
    ]

    def __init__(self):
        self._captured_requests: List[Dict] = []
        self._start_time: float = 0
        self._is_sniffing = False

        logger.info("API 嗅探器初始化完成")

    def classify_param(self, name: str, value: str = "") -> ParamType:
        """
        自动分类参数类型

        Args:
            name: 参数名
            value: 参数值（用于辅助判断）

        Returns:
            参数类型
        """
        # 精确匹配
        if name in PARAM_TYPE_RULES:
            return PARAM_TYPE_RULES[name]

        # 模式匹配（业务参数）
        for pattern in BUSINESS_PARAM_PATTERNS:
            if pattern.match(name):
                return ParamType.BUSINESS

        # 值特征推断
        # 13 位数字 → 时间戳
        if re.match(r"^\d{13}$", value):
            return ParamType.TIMESTAMP
        # 32 位 hex → 签名或 UUID
        if re.match(r"^[a-f0-9]{32}$", value, re.I):
            if "sign" in name.lower() or "h5st" in name.lower():
                return ParamType.SIGNATURE
            return ParamType.DEVICE_ID
        # 很长的字符串 → 可能是签名
        if len(value) > 100:
            return ParamType.SIGNATURE

        return ParamType.UNKNOWN

    def analyze_request(
        self,
        url: str,
        method: str = "GET",
        post_data: Optional[str] = None,
        response_status: int = 0,
        response_size: int = 0,
    ) -> Optional[DiscoveredAPI]:
        """
        分析单个请求

        Args:
            url: 请求 URL
            method: HTTP 方法
            post_data: POST 数据
            response_status: 响应状态码
            response_size: 响应大小

        Returns:
            DiscoveredAPI 或 None（非京东 API）
        """
        parsed = urlparse(url)

        # 检查是否为京东 API
        is_jd_api = any(p.search(parsed.netloc) for p in self.JD_API_PATTERNS)
        if not is_jd_api:
            return None

        api = DiscoveredAPI(
            url=url,
            method=method,
            host=parsed.netloc,
            path=parsed.path,
            response_status=response_status,
            response_size=response_size,
        )

        # 解析 URL 参数
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        for name, values in query_params.items():
            value = values[0] if values else ""
            param_type = self.classify_param(name, value)
            api.params[name] = param_type

        # 解析 POST 数据
        if post_data:
            try:
                post_params = parse_qs(post_data, keep_blank_values=True)
                for name, values in post_params.items():
                    value = values[0] if values else ""
                    param_type = self.classify_param(name, value)
                    api.params[name] = param_type
            except Exception:
                pass

        # 判断是否需要逆向
        sig_params = [
            name
            for name, ptype in api.params.items()
            if ptype == ParamType.SIGNATURE
        ]
        if sig_params:
            api.needs_reverse = True
            api.reverse_target = ",".join(sig_params)
            api.tags.append("needs_reverse")

        # 添加标签
        if api.response_status == 200:
            api.tags.append("success")
        elif api.response_status in (403, 429):
            api.tags.append("rate_limited")
        elif api.response_status >= 400:
            api.tags.append("error")

        if "h5st" in api.params:
            api.tags.append("h5st_required")
        if "functionId" in api.params:
            api.tags.append("gateway_api")

        logger.debug(
            f"嗅探到 API: {api.host}{api.path} "
            f"params={len(api.params)} reverse={api.needs_reverse}"
        )

        return api

    def start_sniff(self) -> None:
        """开始嗅探"""
        self._captured_requests.clear()
        self._start_time = time.time()
        self._is_sniffing = True
        logger.info("开始 API 嗅探...")

    def capture_request(self, request_data: Dict) -> None:
        """
        捕获一个请求（由外部 CDP/MCP 调用）

        Args:
            request_data: 请求数据字典
        """
        if not self._is_sniffing:
            return

        self._captured_requests.append(request_data)

    def stop_sniff(self) -> SniffResult:
        """
        停止嗅探并生成报告

        Returns:
            SniffResult 嗅探结果
        """
        self._is_sniffing = False
        duration = time.time() - self._start_time

        result = SniffResult(
            total_requests=len(self._captured_requests),
            sniff_duration=duration,
        )

        # 分析所有捕获的请求
        seen_urls = set()
        for req in self._captured_requests:
            api = self.analyze_request(
                url=req.get("url", ""),
                method=req.get("method", "GET"),
                post_data=req.get("postData"),
                response_status=req.get("responseStatus", 0),
                response_size=req.get("responseSize", 0),
            )

            if api and api.url not in seen_urls:
                seen_urls.add(api.url)
                result.apis.append(api)

                # 收集签名参数
                for name, ptype in api.params.items():
                    if ptype == ParamType.SIGNATURE and name not in result.signature_params:
                        result.signature_params.append(name)

                # 收集逆向目标
                if api.needs_reverse and api.reverse_target not in result.reverse_targets:
                    result.reverse_targets.append(api.reverse_target)

        result.api_count = len(result.apis)

        logger.info(
            f"嗅探完成: {result.total_requests} 个请求 → "
            f"{result.api_count} 个 API, "
            f"{len(result.signature_params)} 个签名参数, "
            f"{len(result.reverse_targets)} 个逆向目标, "
            f"耗时 {duration:.1f}s"
        )

        return result

    def generate_report(self, result: SniffResult) -> str:
        """
        生成嗅探报告（Markdown 格式）

        Args:
            result: 嗅探结果

        Returns:
            Markdown 格式报告
        """
        lines = [
            "# 京东 API 嗅探报告",
            "",
            f"**嗅探时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**耗时**: {result.sniff_duration:.1f} 秒",
            f"**总请求数**: {result.total_requests}",
            f"**去重 API 数**: {result.api_count}",
            "",
            "## 签名参数",
            "",
        ]

        if result.signature_params:
            for p in result.signature_params:
                lines.append(f"- `{p}` — 需要逆向")
        else:
            lines.append("无签名参数")

        lines.extend(["", "## 逆向目标", ""])
        if result.reverse_targets:
            for t in result.reverse_targets:
                lines.append(f"- `{t}`")
        else:
            lines.append("无需逆向的接口")

        lines.extend(["", "## API 列表", ""])
        lines.append("| # | Host | Path | 参数数 | 需逆向 | 标签 |")
        lines.append("|---|------|------|--------|--------|------|")

        for i, api in enumerate(result.apis, 1):
            reverse = "是" if api.needs_reverse else "否"
            tags = ", ".join(api.tags[:3])
            lines.append(
                f"| {i} | {api.host} | {api.path[:40]} | "
                f"{len(api.params)} | {reverse} | {tags} |"
            )

        return "\n".join(lines)
