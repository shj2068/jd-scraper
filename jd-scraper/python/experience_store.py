"""
经验记忆存储模块

持久化存储反爬对抗经验，支持跨会话学习。
每次反爬对抗的 触发条件 → 采用策略 → 是否成功 三元组
被记录下来，供未来决策参考。

存储格式 (JSON):
{
  "experiences": [
    {
      "trigger": { "type": "rate_limit", "status_code": 403, ... },
      "strategy": { "name": "header_rotation", "params": {...} },
      "outcome": { "success": true, "latency_ms": 320 },
      "timestamp": 1696780000.0,
      "generation": 1
    }
  ],
  "meta": { "version": 1, "created_at": ..., "updated_at": ... }
}
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .utils import setup_logger

logger = setup_logger(__name__)


class AntiCrawlType(str, Enum):
    """反爬机制类型"""

    RATE_LIMIT = "rate_limit"              # 频率限制
    CAPTCHA = "captcha"                    # 验证码
    IP_BAN = "ip_ban"                      # IP 封禁
    SIGN_REJECT = "sign_reject"            # 签名被拒（h5st 无效）
    COOKIE_EXPIRED = "cookie_expired"      # Cookie 过期
    FINGERPRINT_DETECT = "fingerprint_detect"  # 指纹识别
    TLS_FINGERPRINT = "tls_fingerprint"    # TLS 指纹检测
    BEHAVIOR_DETECT = "behavior_detect"    # 行为检测（时序异常）
    PARAM_MISSING = "param_missing"        # 缺失关键参数
    UNKNOWN = "unknown"


@dataclass
class TriggerSnapshot:
    """触发条件快照"""

    anti_crawl_type: AntiCrawlType
    status_code: int = 0
    response_snippet: str = ""
    function_id: str = ""
    headers_sent: Dict[str, str] = field(default_factory=dict)
    params_sent: Dict[str, str] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["anti_crawl_type"] = self.anti_crawl_type.value
        return d


@dataclass
class StrategyRecord:
    """策略记录"""

    name: str
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class OutcomeRecord:
    """结果记录"""

    success: bool
    latency_ms: float = 0.0
    response_code: int = 0
    detail: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Experience:
    """一条完整经验"""

    trigger: TriggerSnapshot
    strategy: StrategyRecord
    outcome: OutcomeRecord
    timestamp: float = field(default_factory=time.time)
    generation: int = 1  # 进化代数

    def to_dict(self) -> Dict:
        return {
            "trigger": self.trigger.to_dict(),
            "strategy": self.strategy.to_dict(),
            "outcome": self.outcome.to_dict(),
            "timestamp": self.timestamp,
            "generation": self.generation,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> Experience:
        trigger = TriggerSnapshot(
            anti_crawl_type=AntiCrawlType(data["trigger"]["anti_crawl_type"]),
            status_code=data["trigger"].get("status_code", 0),
            response_snippet=data["trigger"].get("response_snippet", ""),
            function_id=data["trigger"].get("function_id", ""),
            headers_sent=data["trigger"].get("headers_sent", {}),
            params_sent=data["trigger"].get("params_sent", {}),
            context=data["trigger"].get("context", {}),
        )
        strategy = StrategyRecord(
            name=data["strategy"]["name"],
            params=data["strategy"].get("params", {}),
        )
        outcome = OutcomeRecord(
            success=data["outcome"]["success"],
            latency_ms=data["outcome"].get("latency_ms", 0),
            response_code=data["outcome"].get("response_code", 0),
            detail=data["outcome"].get("detail", ""),
        )
        return cls(
            trigger=trigger,
            strategy=strategy,
            outcome=outcome,
            timestamp=data.get("timestamp", 0),
            generation=data.get("generation", 1),
        )


class ExperienceStore:
    """
    经验记忆存储

    功能:
    1. 存储反爬对抗经验（触发 → 策略 → 结果）
    2. 按反爬类型检索成功经验
    3. 计算策略成功率
    4. 持久化到 JSON 文件
    """

    def __init__(self, storage_path: str = "./data/experience.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._experiences: List[Experience] = []
        self._load()

    def _load(self) -> None:
        """从文件加载经验"""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                self._experiences = [
                    Experience.from_dict(e) for e in data.get("experiences", [])
                ]
                logger.info(f"加载 {len(self._experiences)} 条经验")
            except Exception as e:
                logger.warning(f"经验文件加载失败: {e}")
                self._experiences = []
        else:
            self._experiences = []

    def save(self) -> None:
        """持久化到文件"""
        data = {
            "meta": {
                "version": 1,
                "created_at": self._experiences[0].timestamp if self._experiences else 0,
                "updated_at": time.time(),
                "total_count": len(self._experiences),
            },
            "experiences": [e.to_dict() for e in self._experiences],
        }
        self.storage_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.debug(f"保存 {len(self._experiences)} 条经验到 {self.storage_path}")

    def add(self, experience: Experience) -> None:
        """添加一条经验"""
        self._experiences.append(experience)
        # 每 10 条自动持久化
        if len(self._experiences) % 10 == 0:
            self.save()

    def get_successes_for_type(
        self, anti_crawl_type: AntiCrawlType
    ) -> List[Experience]:
        """获取某类反爬的成功经验"""
        return [
            e
            for e in self._experiences
            if e.trigger.anti_crawl_type == anti_crawl_type and e.outcome.success
        ]

    def get_strategy_success_rate(self, strategy_name: str) -> float:
        """计算某策略的历史成功率"""
        matching = [
            e for e in self._experiences if e.strategy.name == strategy_name
        ]
        if not matching:
            return 0.0
        successes = sum(1 for e in matching if e.outcome.success)
        return successes / len(matching)

    def get_best_strategies_for_type(
        self, anti_crawl_type: AntiCrawlType, top_n: int = 3
    ) -> List[tuple]:
        """
        获取某类反爬的最佳策略（按成功率排序）

        Returns:
            [(strategy_name, success_rate, sample_count), ...]
        """
        matching = [
            e for e in self._experiences
            if e.trigger.anti_crawl_type == anti_crawl_type
        ]
        if not matching:
            return []

        # 按策略分组统计
        strategy_stats: Dict[str, Dict] = {}
        for e in matching:
            name = e.strategy.name
            if name not in strategy_stats:
                strategy_stats[name] = {"success": 0, "total": 0}
            strategy_stats[name]["total"] += 1
            if e.outcome.success:
                strategy_stats[name]["success"] += 1

        # 按成功率排序
        results = []
        for name, stats in strategy_stats.items():
            rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
            results.append((name, rate, stats["total"]))

        results.sort(key=lambda x: (-x[1], -x[2]))
        return results[:top_n]

    def get_latest_generation(self) -> int:
        """获取最新进化代数"""
        if not self._experiences:
            return 0
        return max(e.generation for e in self._experiences)

    @property
    def total_count(self) -> int:
        return len(self._experiences)

    @property
    def all_experiences(self) -> List[Experience]:
        return list(self._experiences)

    def clear(self) -> None:
        """清空所有经验"""
        self._experiences.clear()
        self.save()

    def get_summary(self) -> Dict[str, Any]:
        """获取经验库摘要"""
        type_counts: Dict[str, int] = {}
        type_success: Dict[str, int] = {}
        for e in self._experiences:
            t = e.trigger.anti_crawl_type.value
            type_counts[t] = type_counts.get(t, 0) + 1
            if e.outcome.success:
                type_success[t] = type_success.get(t, 0) + 1

        return {
            "total_experiences": len(self._experiences),
            "generation": self.get_latest_generation(),
            "by_type": {
                t: {
                    "total": type_counts.get(t, 0),
                    "success": type_success.get(t, 0),
                    "rate": (
                        type_success.get(t, 0) / type_counts[t]
                        if type_counts.get(t, 0) > 0
                        else 0.0
                    ),
                }
                for t in [at.value for at in AntiCrawlType]
                if type_counts.get(t, 0) > 0
            },
        }
