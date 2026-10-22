"""
Cookie 池管理模块

管理京东风控相关的 Cookie 参数，支持持久化、多账号轮换、过期检测。

v2.0 增强（文档第五章 5.3 节）：
- Cookie 自动刷新机制（thor/ctoken 2h 过期，提前 10min 触发刷新）
- 后台监控线程，定期检查关键 Cookie 健康状态
- 刷新回调钩子，支持自定义刷新逻辑
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .models import CookieEntry, CookieJar
from .utils import ensure_dir, setup_logger

logger = setup_logger(__name__)

# 京东关键 Cookie 名称
JD_CRITICAL_COOKIES = [
    "__jda",
    "__jdv",
    "__jdu",
    "pt_key",
    "pt_pin",
    "thor",
    "shshshfpa",
    "eid",
    "fp",
    "jd-uuid",
]

# 短生命周期 Cookie（需要自动刷新）
# 文档第五章 5.3 节：thor/ctoken 有效期约 2h，需提前刷新
JD_SHORT_LIVED_COOKIES = {
    "thor": 7200,       # 2h
    "ctoken": 7200,     # 2h
    "pt_key": 86400,    # 24h
    "__jdu": 15552000,  # 180d
}

# 默认提前刷新时间（秒）
DEFAULT_REFRESH_AHEAD = 600  # 10 分钟


class CookieManager:
    """Cookie 池管理器

    v2.0: 支持后台监控线程自动检测并刷新即将过期的 Cookie。
    """

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        auto_save: bool = True,
        auto_refresh: bool = False,
        refresh_callback: Optional[Callable[[str, str], Optional[str]]] = None,
        refresh_check_interval: float = 60.0,
        refresh_ahead_seconds: float = DEFAULT_REFRESH_AHEAD,
    ):
        """
        初始化 Cookie 管理器

        Args:
            storage_dir: Cookie 持久化目录（为空则使用默认）
            auto_save: 是否自动保存
            auto_refresh: 是否启用自动刷新（文档第五章 5.3 节）
            refresh_callback: 刷新回调函数 (cookie_name, account_id) -> new_value
            refresh_check_interval: 刷新检查间隔（秒）
            refresh_ahead_seconds: 提前多少秒触发刷新
        """
        if storage_dir is None:
            from .utils import PROJECT_ROOT

            storage_dir = str(PROJECT_ROOT / "data" / "cookies")

        self.storage_dir = Path(storage_dir)
        self.auto_save = auto_save
        self._jars: Dict[str, CookieJar] = {}  # account_id -> CookieJar
        self._current_account: str = "default"

        # 自动刷新配置（v2.0）
        self.auto_refresh = auto_refresh
        self.refresh_callback = refresh_callback
        self.refresh_check_interval = refresh_check_interval
        self.refresh_ahead_seconds = refresh_ahead_seconds
        self._refresh_thread: Optional[threading.Thread] = None
        self._refresh_stop_event = threading.Event()

        # 确保存储目录存在
        ensure_dir(self.storage_dir)

        # 加载已有 Cookie
        self._load_all()
        
        # 设置当前账号为第一个加载的账号
        if self._jars and self._current_account == "default":
            self._current_account = next(iter(self._jars.keys()))

        # 启动自动刷新线程
        if self.auto_refresh and self.refresh_callback:
            self._start_auto_refresh()

    def _get_jar(self, account_id: Optional[str] = None) -> CookieJar:
        """获取指定账号的 CookieJar"""
        aid = account_id or self._current_account
        if aid not in self._jars:
            self._jars[aid] = CookieJar(account_id=aid)
        return self._jars[aid]

    def set_cookie(
        self,
        name: str,
        value: str,
        expires: float = -1.0,
        account_id: Optional[str] = None,
    ) -> None:
        """
        设置 Cookie

        Args:
            name: Cookie 名称
            value: Cookie 值
            expires: 过期时间戳（-1 表示永不过期）
            account_id: 账号 ID
        """
        jar = self._get_jar(account_id)
        jar.set(name, value, expires)

        if self.auto_save:
            self._save(account_id)

        logger.debug(
            f"设置 Cookie: {name}={value[:20]}... (account={jar.account_id})"
        )

    def get_cookie(
        self, name: str, account_id: Optional[str] = None
    ) -> Optional[str]:
        """
        获取 Cookie 值

        Args:
            name: Cookie 名称
            account_id: 账号 ID

        Returns:
            Cookie 值（不存在或已过期返回 None）
        """
        jar = self._get_jar(account_id)
        return jar.get(name)

    def set_cookies(
        self,
        cookies: Dict[str, str],
        account_id: Optional[str] = None,
    ) -> None:
        """批量设置 Cookie"""
        jar = self._get_jar(account_id)
        for name, value in cookies.items():
            jar.set(name, value)

        if self.auto_save:
            self._save(account_id)

        logger.debug(f"批量设置 {len(cookies)} 个 Cookie")

    def get_all_cookies(
        self, account_id: Optional[str] = None
    ) -> Dict[str, str]:
        """获取所有有效 Cookie"""
        jar = self._get_jar(account_id)
        return jar.to_dict()

    def get_cookie_header(
        self, account_id: Optional[str] = None
    ) -> str:
        """获取 Cookie 头字符串"""
        jar = self._get_jar(account_id)
        return jar.to_header_string()

    def remove_cookie(
        self, name: str, account_id: Optional[str] = None
    ) -> bool:
        """移除指定 Cookie"""
        jar = self._get_jar(account_id)
        result = jar.remove(name)

        if result and self.auto_save:
            self._save(account_id)

        return result

    def clear_expired(
        self, account_id: Optional[str] = None
    ) -> int:
        """清理过期 Cookie"""
        jar = self._get_jar(account_id)
        count = jar.clear_expired()

        if count > 0 and self.auto_save:
            self._save(account_id)

        logger.info(f"清理 {count} 个过期 Cookie")
        return count

    def switch_account(self, account_id: str) -> None:
        """切换当前账号"""
        self._current_account = account_id
        logger.info(f"切换到账号: {account_id}")

    def list_accounts(self) -> List[str]:
        """列出所有账号"""
        return list(self._jars.keys())

    def check_critical_cookies(
        self, account_id: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        检查关键 Cookie 是否存在

        Returns:
            {cookie_name: exists} 字典
        """
        jar = self._get_jar(account_id)
        return {name: jar.get(name) is not None for name in JD_CRITICAL_COOKIES}

    def get_status(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """获取 Cookie 状态摘要"""
        jar = self._get_jar(account_id)
        critical = self.check_critical_cookies(account_id)

        return {
            "account_id": jar.account_id,
            "total_cookies": jar.count,
            "valid_cookies": jar.valid_count,
            "critical_cookies": critical,
            "all_critical_present": all(critical.values()),
        }

    # ========== 持久化方法 ==========

    def _get_file_path(self, account_id: Optional[str] = None) -> Path:
        """获取 Cookie 文件路径"""
        aid = account_id or self._current_account
        return self.storage_dir / f"{aid}.json"

    def _save(self, account_id: Optional[str] = None) -> None:
        """保存 Cookie 到文件"""
        jar = self._get_jar(account_id)
        file_path = self._get_file_path(account_id)

        data = {
            "account_id": jar.account_id,
            "cookies": {
                name: {
                    "name": entry.name,
                    "value": entry.value,
                    "domain": entry.domain,
                    "path": entry.path,
                    "expires": entry.expires,
                    "created_at": entry.created_at,
                }
                for name, entry in jar.cookies.items()
            },
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.debug(f"保存 Cookie 到: {file_path}")

    def _load(self, account_id: str) -> Optional[CookieJar]:
        """从文件加载 Cookie"""
        file_path = self._get_file_path(account_id)

        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            jar = CookieJar(account_id=data.get("account_id", account_id))
            cookies_raw = data.get("cookies", {})
            if isinstance(cookies_raw, list):
                cookies_dict = {c.get("name", f"cookie_{i}"): c for i, c in enumerate(cookies_raw)}
            else:
                cookies_dict = cookies_raw
            for name, cookie_data in cookies_dict.items():
                jar.cookies[name] = CookieEntry(
                    name=cookie_data["name"],
                    value=cookie_data["value"],
                    domain=cookie_data.get("domain", ".jd.com"),
                    path=cookie_data.get("path", "/"),
                    expires=cookie_data.get("expires", -1.0),
                    created_at=cookie_data.get("created_at", time.time()),
                )

            logger.debug(
                f"加载 {jar.count} 个 Cookie (account={account_id})"
            )
            return jar

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"加载 Cookie 文件失败: {e}")
            return None

    def _load_all(self) -> None:
        """加载所有账号的 Cookie"""
        if not self.storage_dir.exists():
            return

        for file_path in self.storage_dir.glob("*.json"):
            account_id = file_path.stem
            jar = self._load(account_id)
            if jar:
                self._jars[account_id] = jar

        if self._jars:
            logger.info(f"加载 {len(self._jars)} 个账号的 Cookie")

    def save_all(self) -> None:
        """保存所有账号的 Cookie"""
        for account_id in self._jars:
            self._save(account_id)

    def clear_all(self, account_id: Optional[str] = None) -> None:
        """清空 Cookie"""
        if account_id:
            self._jars.pop(account_id, None)
            file_path = self._get_file_path(account_id)
            if file_path.exists():
                file_path.unlink()
        else:
            self._jars.clear()
            for file_path in self.storage_dir.glob("*.json"):
                file_path.unlink()

        logger.info("清空所有 Cookie")

    # ========== 自动刷新机制（v2.0） ==========

    def _start_auto_refresh(self) -> None:
        """启动后台自动刷新线程"""
        if self._refresh_thread and self._refresh_thread.is_alive():
            return

        self._refresh_stop_event.clear()
        self._refresh_thread = threading.Thread(
            target=self._auto_refresh_loop,
            daemon=True,
            name="cookie-auto-refresh",
        )
        self._refresh_thread.start()
        logger.info(
            f"Cookie 自动刷新线程已启动 "
            f"(检查间隔={self.refresh_check_interval}s, "
            f"提前刷新={self.refresh_ahead_seconds}s)"
        )

    def _stop_auto_refresh(self) -> None:
        """停止自动刷新线程"""
        self._refresh_stop_event.set()
        if self._refresh_thread and self._refresh_thread.is_alive():
            self._refresh_thread.join(timeout=5)
        logger.info("Cookie 自动刷新线程已停止")

    def _auto_refresh_loop(self) -> None:
        """后台自动刷新循环"""
        while not self._refresh_stop_event.is_set():
            try:
                self._check_and_refresh_expiring_cookies()
            except Exception as e:
                logger.error(f"Cookie 自动刷新异常: {e}")

            # 等待下一次检查
            self._refresh_stop_event.wait(self.refresh_check_interval)

    def _check_and_refresh_expiring_cookies(self) -> None:
        """检查并刷新即将过期的 Cookie"""
        now = time.time()

        for account_id, jar in self._jars.items():
            for cookie_name in JD_SHORT_LIVED_COOKIES:
                entry = jar.cookies.get(cookie_name)
                if not entry:
                    continue

                remaining = entry.ttl
                if remaining <= 0:
                    # 已过期，尝试刷新
                    logger.warning(
                        f"Cookie '{cookie_name}' 已过期 (account={account_id})，尝试刷新..."
                    )
                    self._try_refresh_cookie(cookie_name, account_id)
                elif remaining < self.refresh_ahead_seconds:
                    # 即将过期，提前刷新
                    logger.info(
                        f"Cookie '{cookie_name}' 将在 {remaining:.0f}s 后过期，"
                        f"提前刷新 (account={account_id})"
                    )
                    self._try_refresh_cookie(cookie_name, account_id)

    def _try_refresh_cookie(self, cookie_name: str, account_id: str) -> bool:
        """
        尝试刷新单个 Cookie

        Args:
            cookie_name: Cookie 名称
            account_id: 账号 ID

        Returns:
            是否刷新成功
        """
        if not self.refresh_callback:
            logger.warning(f"未配置刷新回调，无法刷新 '{cookie_name}'")
            return False

        try:
            new_value = self.refresh_callback(cookie_name, account_id)
            if new_value:
                # 计算新的过期时间
                default_ttl = JD_SHORT_LIVED_COOKIES.get(cookie_name, 7200)
                new_expires = time.time() + default_ttl

                self.set_cookie(cookie_name, new_value, new_expires, account_id)
                logger.info(f"Cookie '{cookie_name}' 刷新成功 (account={account_id})")
                return True
            else:
                logger.warning(f"Cookie '{cookie_name}' 刷新回调返回空值")
                return False
        except Exception as e:
            logger.error(f"Cookie '{cookie_name}' 刷新失败: {e}")
            return False

    def get_expiring_cookies(
        self,
        threshold_seconds: Optional[float] = None,
        account_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取即将过期的 Cookie 列表

        Args:
            threshold_seconds: 阈值（秒），默认使用 refresh_ahead_seconds
            account_id: 账号 ID

        Returns:
            [{name, expires_at, remaining_seconds, account_id}]
        """
        threshold = threshold_seconds or self.refresh_ahead_seconds
        now = time.time()
        result = []

        jars_to_check = (
            {account_id: self._jars[account_id]}
            if account_id and account_id in self._jars
            else self._jars
        )

        for aid, jar in jars_to_check.items():
            for name, entry in jar.cookies.items():
                remaining = entry.ttl
                if remaining < threshold:
                    result.append(
                        {
                            "name": name,
                            "expires_at": entry.expires,
                            "remaining_seconds": max(0, remaining),
                            "account_id": aid,
                            "is_expired": remaining <= 0,
                        }
                    )

        return result

    def shutdown(self) -> None:
        """关闭管理器，停止自动刷新线程"""
        self._stop_auto_refresh()
        self.save_all()
