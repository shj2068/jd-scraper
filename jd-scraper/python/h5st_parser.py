"""
h5st 签名结构解析与版本检测模块

深度解析京东 h5st 签名参数结构，自动识别版本号并推荐最优策略。
h5st 格式: 版本.时间戳.随机串.签名段.校验段

文档参考: AI-JS逆向京东工业招商网数据采集实战指南 - 第二章
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .utils import setup_logger

logger = setup_logger(__name__)


class H5stVersion(str, Enum):
    """h5st 版本枚举"""

    V1 = "v1"  # MD5 简单拼接，可纯算
    V2 = "v2"  # 轻度混淆+多参数，推荐 JSRPC
    V3 = "v3"  # VMP 字节码级，需 Playwright 兜底
    UNKNOWN = "unknown"


class SignStrategy(str, Enum):
    """签名策略枚举"""

    PURE_PYTHON = "pure_python"  # 纯 Python 算（v1）
    JSRPC = "jsrpc"  # JSRPC 远程调用（v2，推荐）
    PLAYWRIGHT_FALLBACK = "playwright"  # Playwright 兜底（v3）


# h5st 版本 → 推荐策略映射
VERSION_STRATEGY_MAP: Dict[H5stVersion, SignStrategy] = {
    H5stVersion.V1: SignStrategy.PURE_PYTHON,
    H5stVersion.V2: SignStrategy.JSRPC,
    H5stVersion.V3: SignStrategy.PLAYWRIGHT_FALLBACK,
    H5stVersion.UNKNOWN: SignStrategy.JSRPC,  # 默认走 JSRPC
}

# 版本特征正则
# v1: 2020/2021 开头，4 段结构
# v2: 2022/2023 开头，5 段结构
# v3: 2024+ 开头，6 段以上或含 VMP 标记
H5ST_V1_PATTERN = re.compile(r"^202[01]\.\d{2}\.\d{2}\.")
H5ST_V2_PATTERN = re.compile(r"^202[23]\.\d{2}\.\d{2}\.")
H5ST_V3_PATTERN = re.compile(r"^202[4-6]\.\d{2}\.\d{2}\.")


@dataclass
class H5stStructure:
    """h5st 签名解析结构"""

    raw: str
    version: H5stVersion = H5stVersion.UNKNOWN
    version_date: str = ""  # 如 "2022.11.29"
    timestamp: str = ""  # 13 位毫秒时间戳
    random_str: str = ""  # 8-12 位随机字符
    signature: str = ""  # 核心签名段
    checksum: str = ""  # 防篡改校验段
    extra_segments: List[str] = field(default_factory=list)  # 额外段
    segment_count: int = 0
    is_valid: bool = False
    parse_error: str = ""

    @property
    def recommended_strategy(self) -> SignStrategy:
        """根据版本推荐签名策略"""
        return VERSION_STRATEGY_MAP.get(self.version, SignStrategy.JSRPC)

    @property
    def age_seconds(self) -> float:
        """h5st 的存活时间（秒）"""
        if not self.timestamp:
            return -1.0
        try:
            ts = int(self.timestamp)
            return time.time() - ts / 1000.0
        except (ValueError, OSError):
            return -1.0

    @property
    def is_fresh(self) -> bool:
        """h5st 是否仍然新鲜（< 60 秒）"""
        age = self.age_seconds
        return 0 <= age < 60.0

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "raw": self.raw,
            "version": self.version.value,
            "version_date": self.version_date,
            "timestamp": self.timestamp,
            "random_str": self.random_str,
            "signature": self.signature,
            "checksum": self.checksum,
            "extra_segments": self.extra_segments,
            "segment_count": self.segment_count,
            "is_valid": self.is_valid,
            "recommended_strategy": self.recommended_strategy.value,
            "age_seconds": round(self.age_seconds, 2),
            "is_fresh": self.is_fresh,
        }


def parse_h5st(h5st_str: str) -> H5stStructure:
    """
    解析 h5st 签名字符串

    Args:
        h5st_str: h5st 签名字符串

    Returns:
        H5stStructure 解析结果

    Example:
        >>> result = parse_h5st("2022.11.29.1669718400000.abc123xy.sighash.checksum")
        >>> result.version
        <H5stVersion.V2: 'v2'>
        >>> result.recommended_strategy
        <SignStrategy.JSRPC: 'jsrpc'>
    """
    if not h5st_str or not isinstance(h5st_str, str):
        return H5stStructure(
            raw=h5st_str or "",
            is_valid=False,
            parse_error="h5st 为空或类型错误",
        )

    result = H5stStructure(raw=h5st_str)

    # 按点号分割
    segments = h5st_str.split(".")
    result.segment_count = len(segments)

    if len(segments) < 3:
        result.parse_error = f"段数不足: {len(segments)} < 3"
        result.is_valid = False
        logger.warning(f"h5st 解析失败: {result.parse_error}")
        return result

    # 提取版本日期段（前三段）
    result.version_date = ".".join(segments[:3])

    # 检测版本
    result.version = _detect_version(h5st_str)

    # 提取时间戳（第 4 段，13 位数字）
    if len(segments) >= 4:
        result.timestamp = segments[3]

    # 提取随机串（第 5 段）
    if len(segments) >= 5:
        result.random_str = segments[4]

    # 提取核心签名（第 6 段）
    if len(segments) >= 6:
        result.signature = segments[5]

    # 提取校验段（第 7 段）
    if len(segments) >= 7:
        result.checksum = segments[6]

    # 额外段
    if len(segments) > 7:
        result.extra_segments = segments[7:]

    result.is_valid = True
    logger.debug(
        f"h5st 解析成功: version={result.version.value}, "
        f"segments={result.segment_count}, strategy={result.recommended_strategy.value}"
    )

    return result


def _detect_version(h5st_str: str) -> H5stVersion:
    """检测 h5st 版本号"""
    if H5ST_V3_PATTERN.match(h5st_str):
        return H5stVersion.V3
    if H5ST_V2_PATTERN.match(h5st_str):
        return H5stVersion.V2
    if H5ST_V1_PATTERN.match(h5st_str):
        return H5stVersion.V1

    # 通过段数推断
    segments = h5st_str.split(".")
    if len(segments) >= 7:
        return H5stVersion.V3
    if len(segments) >= 5:
        return H5stVersion.V2

    return H5stVersion.UNKNOWN


def detect_version_from_samples(samples: List[str]) -> H5stVersion:
    """
    从多个 h5st 样本中统计版本号（多数投票法）

    Args:
        samples: h5st 样本列表

    Returns:
        最常见的版本号
    """
    if not samples:
        return H5stVersion.UNKNOWN

    version_counts: Dict[H5stVersion, int] = {}
    for sample in samples:
        v = _detect_version(sample)
        version_counts[v] = version_counts.get(v, 0) + 1

    # 返回出现最多的版本
    most_common = max(version_counts, key=version_counts.get)  # type: ignore
    logger.info(
        f"h5st 版本检测: {most_common.value} "
        f"(样本数={len(samples)}, 分布={dict(version_counts)})"
    )
    return most_common


def validate_h5st_freshness(h5st_str: str, max_age_seconds: float = 60.0) -> Tuple[bool, str]:
    """
    验证 h5st 是否仍然新鲜

    Args:
        h5st_str: h5st 字符串
        max_age_seconds: 最大允许存活时间（秒）

    Returns:
        (是否新鲜, 原因描述)
    """
    parsed = parse_h5st(h5st_str)

    if not parsed.is_valid:
        return False, f"解析失败: {parsed.parse_error}"

    age = parsed.age_seconds
    if age < 0:
        return False, "无法提取时间戳"

    if age > max_age_seconds:
        return False, f"已过期: {age:.1f}s > {max_age_seconds}s"

    return True, f"新鲜: {age:.1f}s"


def get_strategy_recommendation(version: H5stVersion) -> Dict:
    """
    获取版本对应的策略推荐详情

    Args:
        version: h5st 版本号

    Returns:
        策略推荐字典
    """
    recommendations = {
        H5stVersion.V1: {
            "strategy": SignStrategy.PURE_PYTHON.value,
            "reliability": "high",
            "maintenance_cost": "low",
            "description": "MD5 简单拼接，可直接 Python 纯算",
            "notes": "可长期稳定使用，无需浏览器实例",
        },
        H5stVersion.V2: {
            "strategy": SignStrategy.JSRPC.value,
            "reliability": "high",
            "maintenance_cost": "medium",
            "description": "轻度混淆+多参数，推荐 JSRPC 调用浏览器生成",
            "notes": "浏览器自动加载新 JS，无需手动更新算法；并发建议 ≤5",
        },
        H5stVersion.V3: {
            "strategy": SignStrategy.PLAYWRIGHT_FALLBACK.value,
            "reliability": "medium",
            "maintenance_cost": "high",
            "description": "VMP 字节码虚拟机，必须 Playwright 兜底",
            "notes": "性能换稳定；建议签名预生成+缓存；单 Chrome 实例复用",
        },
        H5stVersion.UNKNOWN: {
            "strategy": SignStrategy.JSRPC.value,
            "reliability": "medium",
            "maintenance_cost": "medium",
            "description": "版本未知，默认走 JSRPC 方案",
            "notes": "建议采集样本后重新检测版本",
        },
    }

    return recommendations.get(version, recommendations[H5stVersion.UNKNOWN])
