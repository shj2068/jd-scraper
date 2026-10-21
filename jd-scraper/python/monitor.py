"""
生产环境监控模块

监控签名失败率、Cookie 过期、IP 封禁率、h5st 版本变化等关键指标，
支持告警阈值配置和回调通知。

文档参考: AI-JS逆向京东工业招商网数据采集实战指南 - 第六章 6.2 节
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional

from .utils import setup_logger

logger = setup_logger(__name__)


class AlertLevel(str, Enum):
    """告警级别"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AlertEvent:
    """告警事件"""

    level: AlertLevel
    metric_name: str
    message: str
    value: float
    threshold: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "level": self.level.value,
            "metric_name": self.metric_name,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "timestamp": self.timestamp,
        }


@dataclass
class MonitorConfig:
    """监控配置"""

    # 签名失败率阈值（超过则告警）
    sign_failure_threshold: float = 0.1  # 10%
    # Cookie 过期提前告警时间（秒）
    cookie_expiry_warning_seconds: float = 600.0  # 10 分钟
    # IP 封禁率阈值
    ip_ban_rate_threshold: float = 0.2  # 20%
    # h5st 版本变化检测
    h5st_version_change_alert: bool = True
    # 滑动窗口大小（最近 N 次请求）
    window_size: int = 100
    # 告警回调函数
    alert_callback: Optional[Callable[[AlertEvent], None]] = None


class ProductionMonitor:
    """
    生产环境监控器

    监控指标：
    1. 签名失败率 - JSRPC 返回的 h5st 是否被服务端接受
    2. Cookie 过期 - thor/ctoken 有效期，提前刷新
    3. IP 封禁率 - 代理 IP 被封的比例
    4. h5st 版本变化 - 版本号变化时触发重新逆向告警
    """

    def __init__(self, config: Optional[MonitorConfig] = None):
        self.config = config or MonitorConfig()
        self._alert_history: Deque[AlertEvent] = deque(maxlen=1000)

        # 签名统计（滑动窗口）
        self._sign_total: Deque[bool] = deque(maxlen=self.config.window_size)
        self._sign_failure_count = 0

        # IP 封禁统计
        self._ip_requests: Deque[bool] = deque(maxlen=self.config.window_size)

        # h5st 版本追踪
        self._last_h5st_version: Optional[str] = None

        # Cookie 健康状态
        self._cookie_health: Dict[str, float] = {}  # cookie_name -> expires_timestamp

        logger.info("生产监控器初始化完成")

    # ========== 签名监控 ==========

    def record_sign_result(self, success: bool) -> None:
        """
        记录一次签名结果

        Args:
            success: 签名是否被服务端接受
        """
        self._sign_total.append(success)

        if not success:
            self._sign_failure_count += 1

        # 检查失败率
        failure_rate = self.get_sign_failure_rate()
        if failure_rate > self.config.sign_failure_threshold:
            self._emit_alert(
                AlertLevel.WARNING,
                "sign_failure_rate",
                f"签名失败率 {failure_rate:.1%} 超过阈值 {self.config.sign_failure_threshold:.1%}",
                failure_rate,
                self.config.sign_failure_threshold,
            )

    def get_sign_failure_rate(self) -> float:
        """获取当前签名失败率"""
        if not self._sign_total:
            return 0.0
        failures = sum(1 for s in self._sign_total if not s)
        return failures / len(self._sign_total)

    # ========== IP 封禁监控 ==========

    def record_ip_request(self, blocked: bool) -> None:
        """
        记录一次 IP 请求结果

        Args:
            blocked: 是否被封禁
        """
        self._ip_requests.append(blocked)

        ban_rate = self.get_ip_ban_rate()
        if ban_rate > self.config.ip_ban_rate_threshold:
            self._emit_alert(
                AlertLevel.CRITICAL,
                "ip_ban_rate",
                f"IP 封禁率 {ban_rate:.1%} 超过阈值 {self.config.ip_ban_rate_threshold:.1%}，建议切换代理",
                ban_rate,
                self.config.ip_ban_rate_threshold,
            )

    def get_ip_ban_rate(self) -> float:
        """获取当前 IP 封禁率"""
        if not self._ip_requests:
            return 0.0
        blocked = sum(1 for b in self._ip_requests if b)
        return blocked / len(self._ip_requests)

    # ========== Cookie 健康监控 ==========

    def update_cookie_health(self, cookie_name: str, expires_at: float) -> None:
        """
        更新 Cookie 过期时间

        Args:
            cookie_name: Cookie 名称
            expires_at: 过期时间戳
        """
        self._cookie_health[cookie_name] = expires_at

        # 检查是否即将过期
        remaining = expires_at - time.time()
        if 0 < remaining < self.config.cookie_expiry_warning_seconds:
            self._emit_alert(
                AlertLevel.WARNING,
                "cookie_expiring_soon",
                f"Cookie '{cookie_name}' 将在 {remaining:.0f} 秒后过期，请及时刷新",
                remaining,
                self.config.cookie_expiry_warning_seconds,
            )
        elif remaining <= 0:
            self._emit_alert(
                AlertLevel.CRITICAL,
                "cookie_expired",
                f"Cookie '{cookie_name}' 已过期！请立即刷新",
                0,
                self.config.cookie_expiry_warning_seconds,
            )

    def check_critical_cookies(
        self, critical_names: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        检查关键 Cookie 的健康状态

        Args:
            critical_names: 关键 Cookie 名称列表（默认 thor, ctoken）

        Returns:
            {cookie_name: {expires_at, remaining_seconds, is_healthy}}
        """
        if critical_names is None:
            critical_names = ["thor", "ctoken", "pt_key", "pt_pin"]

        now = time.time()
        result = {}
        for name in critical_names:
            expires_at = self._cookie_health.get(name, 0)
            remaining = expires_at - now if expires_at > 0 else -1
            result[name] = {
                "expires_at": expires_at,
                "remaining_seconds": remaining,
                "is_healthy": remaining > self.config.cookie_expiry_warning_seconds,
                "is_expiring": 0 < remaining <= self.config.cookie_expiry_warning_seconds,
                "is_expired": remaining <= 0 and expires_at > 0,
                "not_tracked": expires_at == 0,
            }

        return result

    # ========== h5st 版本监控 ==========

    def track_h5st_version(self, version: str) -> None:
        """
        追踪 h5st 版本号变化

        Args:
            version: h5st 版本号字符串
        """
        if self._last_h5st_version is None:
            self._last_h5st_version = version
            logger.info(f"h5st 版本追踪开始: {version}")
            return

        if version != self._last_h5st_version:
            old_version = self._last_h5st_version
            self._last_h5st_version = version

            if self.config.h5st_version_change_alert:
                self._emit_alert(
                    AlertLevel.CRITICAL,
                    "h5st_version_changed",
                    f"h5st 版本从 {old_version} 变更为 {version}，可能需要重新逆向！",
                    0,
                    0,
                )

    # ========== 综合状态 ==========

    def get_dashboard(self) -> Dict[str, Any]:
        """
        获取监控仪表盘数据

        Returns:
            综合状态字典
        """
        return {
            "sign": {
                "failure_rate": round(self.get_sign_failure_rate(), 4),
                "total_requests": len(self._sign_total),
                "window_size": self.config.window_size,
                "threshold": self.config.sign_failure_threshold,
                "is_healthy": self.get_sign_failure_rate() <= self.config.sign_failure_threshold,
            },
            "ip": {
                "ban_rate": round(self.get_ip_ban_rate(), 4),
                "total_requests": len(self._ip_requests),
                "threshold": self.config.ip_ban_rate_threshold,
                "is_healthy": self.get_ip_ban_rate() <= self.config.ip_ban_rate_threshold,
            },
            "cookies": self.check_critical_cookies(),
            "h5st_version": self._last_h5st_version,
            "alerts": {
                "total": len(self._alert_history),
                "recent": [a.to_dict() for a in list(self._alert_history)[-10:]],
            },
        }

    def get_recent_alerts(self, count: int = 10) -> List[Dict]:
        """获取最近的告警事件"""
        return [a.to_dict() for a in list(self._alert_history)[-count:]]

    # ========== 内部方法 ==========

    def _emit_alert(
        self,
        level: AlertLevel,
        metric_name: str,
        message: str,
        value: float,
        threshold: float,
    ) -> None:
        """触发告警"""
        event = AlertEvent(
            level=level,
            metric_name=metric_name,
            message=message,
            value=value,
            threshold=threshold,
        )

        self._alert_history.append(event)

        log_func = {
            AlertLevel.INFO: logger.info,
            AlertLevel.WARNING: logger.warning,
            AlertLevel.CRITICAL: logger.critical,
        }.get(level, logger.warning)

        log_func(f"[ALERT] {message}")

        # 调用回调
        if self.config.alert_callback:
            try:
                self.config.alert_callback(event)
            except Exception as e:
                logger.error(f"告警回调执行失败: {e}")

    def reset(self) -> None:
        """重置所有监控数据"""
        self._sign_total.clear()
        self._sign_failure_count = 0
        self._ip_requests.clear()
        self._alert_history.clear()
        self._cookie_health.clear()
        self._last_h5st_version = None
        logger.info("监控数据已重置")
