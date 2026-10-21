"""
工具函数集合

提供日志、配置加载、重试装饰器等通用工具。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypeVar

import yaml

T = TypeVar("T")

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """配置日志记录器"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """加载 YAML 配置文件"""
    if config_path is None:
        config_path = CONFIG_DIR / "settings.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def md5_hash(text: str) -> str:
    """计算 MD5 哈希值"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def sha256_hash(text: str) -> str:
    """计算 SHA256 哈希值"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def json_dumps_safe(obj: Any) -> str:
    """安全的 JSON 序列化（紧凑格式）"""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def random_delay(min_sec: float = 1.0, max_sec: float = 5.0) -> None:
    """随机延迟（模拟人类行为）"""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


def retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """重试装饰器（指数退避）"""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger = logging.getLogger(__name__)
                        logger.warning(
                            f"重试 {attempt + 1}/{max_retries}: {e}"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff

            raise last_exception  # type: ignore

        return wrapper

    return decorator


def validate_uuid(uuid: str) -> bool:
    """验证 UUID 格式（32位十六进制）"""
    if len(uuid) != 32:
        return False
    try:
        int(uuid, 16)
        return True
    except ValueError:
        return False


def timestamp_ms() -> str:
    """获取当前毫秒时间戳字符串"""
    return str(int(time.time() * 1000))


def ensure_dir(path: Path) -> Path:
    """确保目录存在"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_env_or_default(key: str, default: str) -> str:
    """从环境变量获取值，不存在则返回默认值"""
    return os.environ.get(key, default)


class RateLimiter:
    """简易速率限制器"""

    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls: list = []

    def acquire(self) -> None:
        """获取执行许可（阻塞直到可用）"""
        now = time.time()
        # 清理过期记录
        self.calls = [t for t in self.calls if now - t < self.period]

        if len(self.calls) >= self.max_calls:
            sleep_time = self.period - (now - self.calls[0])
            if sleep_time > 0:
                time.sleep(sleep_time)

        self.calls.append(time.time())
