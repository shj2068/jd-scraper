"""
代理池管理模块

支持多代理配置、健康检查、自动轮换、失败切换。
"""

from __future__ import annotations

import random
import time
import threading
from dataclasses import dataclass, field
from typing import Optional

from .utils import setup_logger

logger = setup_logger(__name__)


@dataclass
class ProxyEntry:
    """单个代理条目"""
    url: str
    protocol: str = "http"
    username: Optional[str] = None
    password: Optional[str] = None
    success_count: int = 0
    failure_count: int = 0
    last_used: float = 0.0
    last_check: float = 0.0
    is_healthy: bool = True
    response_time_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 1.0
        return self.success_count / total

    @property
    def full_url(self) -> str:
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.url.replace(f'{self.protocol}://', '')}"
        return f"{self.protocol}://{self.url.replace(f'{self.protocol}://', '')}"

    def record_success(self, response_time_ms: float = 0.0) -> None:
        self.success_count += 1
        self.last_used = time.time()
        self.is_healthy = True
        if response_time_ms > 0:
            self.response_time_ms = response_time_ms

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_used = time.time()
        if self.success_rate < 0.3 and (self.success_count + self.failure_count) >= 5:
            self.is_healthy = False
            logger.warning(f"代理 {self.url} 成功率过低 ({self.success_rate:.0%})，标记为不健康")


class ProxyPool:
    """代理池管理器"""

    def __init__(
        self,
        proxies: Optional[list[dict]] = None,
        health_check_interval: float = 60.0,
        max_failures: int = 5,
        rotation_strategy: str = "round_robin",
    ):
        self._proxies: list[ProxyEntry] = []
        self._lock = threading.Lock()
        self._index = 0
        self._health_check_interval = health_check_interval
        self._max_failures = max_failures
        self._rotation_strategy = rotation_strategy
        self._health_check_thread: Optional[threading.Thread] = None
        self._shutdown = False

        if proxies:
            for p in proxies:
                self.add_proxy(
                    url=p.get("url", ""),
                    protocol=p.get("protocol", "http"),
                    username=p.get("username"),
                    password=p.get("password"),
                )

        if self._proxies:
            logger.info(f"代理池初始化: {len(self._proxies)} 个代理, 策略={rotation_strategy}")

    def add_proxy(
        self,
        url: str,
        protocol: str = "http",
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        entry = ProxyEntry(url=url, protocol=protocol, username=username, password=password)
        with self._lock:
            self._proxies.append(entry)

    def remove_proxy(self, url: str) -> bool:
        with self._lock:
            before = len(self._proxies)
            self._proxies = [p for p in self._proxies if p.url != url]
            return len(self._proxies) < before

    def get_proxy(self) -> Optional[ProxyEntry]:
        with self._lock:
            healthy = [p for p in self._proxies if p.is_healthy]
            if not healthy:
                if self._proxies:
                    logger.warning("所有代理不健康，重置状态")
                    for p in self._proxies:
                        p.is_healthy = True
                        p.failure_count = 0
                    healthy = self._proxies[:]
                else:
                    return None

            if self._rotation_strategy == "random":
                return random.choice(healthy)
            elif self._rotation_strategy == "fastest":
                return min(healthy, key=lambda p: p.response_time_ms if p.response_time_ms > 0 else float('inf'))
            elif self._rotation_strategy == "best":
                return max(healthy, key=lambda p: p.success_rate)
            else:
                self._index = (self._index) % len(healthy)
                proxy = healthy[self._index]
                self._index += 1
                return proxy

    def get_proxy_url(self) -> Optional[str]:
        entry = self.get_proxy()
        return entry.full_url if entry else None

    def record_success(self, url: str, response_time_ms: float = 0.0) -> None:
        with self._lock:
            for p in self._proxies:
                if p.url == url:
                    p.record_success(response_time_ms)
                    break

    def record_failure(self, url: str) -> None:
        with self._lock:
            for p in self._proxies:
                if p.url == url:
                    p.record_failure()
                    break

    def start_health_check(self, check_fn=None) -> None:
        if self._health_check_thread is not None:
            return

        def _loop():
            while not self._shutdown:
                time.sleep(self._health_check_interval)
                if self._shutdown:
                    break
                self._run_health_check(check_fn)

        self._health_check_thread = threading.Thread(target=_loop, daemon=True)
        self._health_check_thread.start()

    def stop_health_check(self) -> None:
        self._shutdown = True
        if self._health_check_thread:
            self._health_check_thread.join(timeout=5)
            self._health_check_thread = None

    def _run_health_check(self, check_fn=None) -> None:
        import httpx

        with self._lock:
            proxies_to_check = [p for p in self._proxies if not p.is_healthy or (time.time() - p.last_check > self._health_check_interval)]

        for proxy in proxies_to_check:
            try:
                start = time.time()
                if check_fn:
                    ok = check_fn(proxy.full_url)
                else:
                    r = httpx.get(
                        "https://api.m.jd.com/",
                        proxies={"https": proxy.full_url},
                        timeout=10,
                    )
                    ok = r.status_code < 500

                elapsed = (time.time() - start) * 1000
                proxy.last_check = time.time()

                if ok:
                    proxy.record_success(elapsed)
                    proxy.is_healthy = True
                else:
                    proxy.record_failure()
            except Exception as e:
                proxy.last_check = time.time()
                proxy.record_failure()
                logger.debug(f"代理健康检查失败 {proxy.url}: {e}")

    def status(self) -> dict:
        with self._lock:
            return {
                "total": len(self._proxies),
                "healthy": sum(1 for p in self._proxies if p.is_healthy),
                "unhealthy": sum(1 for p in self._proxies if not p.is_healthy),
                "proxies": [
                    {
                        "url": p.url,
                        "healthy": p.is_healthy,
                        "success_rate": f"{p.success_rate:.0%}",
                        "success": p.success_count,
                        "failure": p.failure_count,
                        "response_time_ms": round(p.response_time_ms, 1),
                    }
                    for p in self._proxies
                ],
            }

    @classmethod
    def from_config(cls, config: dict) -> "ProxyPool":
        proxy_config = config.get("proxy", {})
        if not proxy_config.get("enabled", False):
            return cls()

        proxies = []
        http_proxy = proxy_config.get("http")
        https_proxy = proxy_config.get("https")

        if http_proxy:
            proxies.append({"url": http_proxy, "protocol": "http"})
        if https_proxy and https_proxy != http_proxy:
            proxies.append({"url": https_proxy, "protocol": "https"})

        proxy_list = proxy_config.get("pool", [])
        proxies.extend(proxy_list)

        return cls(
            proxies=proxies,
            health_check_interval=proxy_config.get("health_check_interval", 60),
            rotation_strategy=proxy_config.get("rotation_strategy", "round_robin"),
        )
