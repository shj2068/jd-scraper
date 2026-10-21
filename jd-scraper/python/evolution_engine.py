"""
反爬自进化引擎

智能体的核心进化模块，实现 Detect → Classify → Adapt → Validate → Learn 闭环。

当请求失败时:
1. Detect: 从响应中检测反爬机制类型
2. Classify: 分类为 AntiCrawlType（频率限制/签名拒绝/指纹检测等）
3. Adapt: 从策略池选择新策略 + 从经验库检索历史成功方案
4. Validate: 用新策略重试，验证是否绕过
5. Learn: 将结果写入经验库，更新策略池贝叶斯参数

进化循环:
- 每次失败触发一次「微进化」: 选择新策略 → 重试
- 连续失败 N 次触发「宏进化」: 策略变异/交叉 → 生成新变体 → 重试
- 每 M 次成功/失败触发「经验固化」: 持久化到 experience.json
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .experience_store import (
    AntiCrawlType,
    Experience,
    ExperienceStore,
    OutcomeRecord,
    StrategyRecord,
    TriggerSnapshot,
)
from .request_mutator import RequestMutator
from .strategy_pool import StrategyPool, StrategyVariant
from .utils import setup_logger

logger = setup_logger(__name__)


class EvolutionPhase(str, Enum):
    """进化阶段"""
    IDLE = "idle"
    DETECTING = "detecting"          # 检测反爬类型
    ADAPTING = "adapting"            # 选择适应策略
    VALIDATING = "validating"        # 验证适应结果
    EVOLVING = "evolving"            # 宏进化（变异/交叉）
    LEARNING = "learning"            # 经验固化


@dataclass
class EvolutionResult:
    """单次进化结果"""
    original_failure: str
    detected_type: AntiCrawlType
    strategy_used: str
    retry_success: bool
    generation: int
    phase: EvolutionPhase
    detail: str = ""
    latency_ms: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "original_failure": self.original_failure,
            "detected_type": self.detected_type.value,
            "strategy_used": self.strategy_used,
            "retry_success": self.retry_success,
            "generation": self.generation,
            "phase": self.phase.value,
            "detail": self.detail,
            "latency_ms": round(self.latency_ms, 1),
        }


@dataclass
class EvolutionConfig:
    """进化引擎配置"""
    max_micro_retries: int = 3          # 微进化最大重试次数
    macro_threshold: int = 5            # 连续失败 N 次触发宏进化
    experience_save_interval: int = 10  # 每 N 次经验操作后持久化
    enable_mutation: bool = True        # 是否启用策略变异
    enable_crossover: bool = True       # 是否启用策略交叉
    enable_experience: bool = True      # 是否启用经验学习
    auto_evolve: bool = True            # 是否自动进化（否则需手动确认）


class EvolutionEngine:
    """
    反爬自进化引擎

    核心闭环:
    ┌─────────┐     ┌──────────┐     ┌──────────┐
    │  Detect  │ ──→ │ Classify │ ──→ │  Adapt   │
    └─────────┘     └──────────┘     └──────────┘
         ↑                                  │
         │           ┌──────────┐           │
         └───────────│ Validate │ ←─────────┘
                     └──────────┘
                           │
                     ┌──────────┐
                     │  Learn   │
                     └──────────┘
    """

    def __init__(
        self,
        config: Optional[EvolutionConfig] = None,
        experience_store: Optional[ExperienceStore] = None,
        strategy_pool: Optional[StrategyPool] = None,
        request_mutator: Optional[RequestMutator] = None,
    ):
        self.config = config or EvolutionConfig()
        self.experience = experience_store or ExperienceStore()
        self.pool = strategy_pool or StrategyPool()
        self.mutator = request_mutator or RequestMutator()

        # 进化状态追踪
        self._phase = EvolutionPhase.IDLE
        self._consecutive_failures = 0
        self._total_evolutions = 0
        self._generation = 0
        self._evolution_history: List[EvolutionResult] = []

        # 重试回调（由 agent 注入，用于实际发送重试请求）
        self._retry_callback: Optional[Callable] = None

        logger.info(
            f"进化引擎初始化: max_retries={self.config.max_micro_retries}, "
            f"macro_threshold={self.config.macro_threshold}, "
            f"experiences={self.experience.total_count}"
        )

    def set_retry_callback(self, callback: Callable) -> None:
        """
        设置重试回调函数

        回调签名: callback(headers, params) -> Dict
        返回: {"success": bool, "status_code": int, "body": str/dict}
        """
        self._retry_callback = callback

    # ========== 核心闭环 ==========

    def evolve(
        self,
        response_data: Dict[str, Any],
        original_headers: Dict[str, str],
        original_params: Dict[str, Any],
    ) -> EvolutionResult:
        """
        执行一次完整的进化闭环

        Args:
            response_data: 失败响应 {"status_code": ..., "body": ..., "headers": ...}
            original_headers: 原始请求头
            original_params: 原始请求参数

        Returns:
            EvolutionResult
        """
        start_time = time.time()

        # Phase 1: 检测反爬类型
        self._phase = EvolutionPhase.DETECTING
        anti_type = self._detect_anti_crawl_type(response_data)
        logger.info(f"[进化] 检测到反爬类型: {anti_type.value}")

        # Phase 2: 适应 — 先查经验库，再从策略池选
        self._phase = EvolutionPhase.ADAPTING
        strategy_name, headers, params = self._adapt(
            anti_type, original_headers, original_params
        )

        # Phase 3: 验证 — 重试
        self._phase = EvolutionPhase.VALIDATING
        success = self._validate(headers, params)

        # Phase 4: 学习 — 记录经验
        self._phase = EvolutionPhase.LEARNING
        latency_ms = (time.time() - start_time) * 1000

        result = EvolutionResult(
            original_failure=str(response_data.get("body", ""))[:200],
            detected_type=anti_type,
            strategy_used=strategy_name,
            retry_success=success,
            generation=self._generation,
            phase=self._phase,
            latency_ms=latency_ms,
        )

        # 记录到策略池（贝叶斯更新）
        self.pool.record_result(strategy_name, success)

        # 记录到经验库
        if self.config.enable_experience:
            experience = Experience(
                trigger=TriggerSnapshot(
                    anti_crawl_type=anti_type,
                    status_code=response_data.get("status_code", 0),
                    response_snippet=str(response_data.get("body", ""))[:500],
                    function_id=original_params.get("functionId", ""),
                ),
                strategy=StrategyRecord(
                    name=strategy_name,
                    params=self.pool.get_variant(strategy_name).params
                    if self.pool.get_variant(strategy_name) else {},
                ),
                outcome=OutcomeRecord(
                    success=success,
                    latency_ms=latency_ms,
                    response_code=response_data.get("status_code", 0),
                ),
                generation=self._generation,
            )
            self.experience.add(experience)

        # 更新连续失败计数
        if success:
            self._consecutive_failures = 0
            self.mutator.reset_adaptive_timing()
            logger.info(f"[进化] ✓ 成功绕过 {anti_type.value} (策略: {strategy_name})")
        else:
            self._consecutive_failures += 1
            self.mutator.increase_adaptive_timing()
            logger.warning(
                f"[进化] ✗ 绕过失败 ({self._consecutive_failures} 次连续失败)"
            )

            # 检查是否触发宏进化
            if self._consecutive_failures >= self.config.macro_threshold:
                self._macro_evolve(anti_type)

        self._total_evolutions += 1
        self._evolution_history.append(result)
        self._phase = EvolutionPhase.IDLE

        return result

    # ========== 多步重试 ==========

    def evolve_with_retries(
        self,
        response_data: Dict[str, Any],
        original_headers: Dict[str, str],
        original_params: Dict[str, Any],
    ) -> Tuple[EvolutionResult, List[EvolutionResult]]:
        """
        带多次重试的进化

        最多尝试 max_micro_retries 次不同策略。

        Returns:
            (最终结果, 所有尝试的结果列表)
        """
        attempts: List[EvolutionResult] = []
        tried_strategies: List[str] = []

        for attempt in range(self.config.max_micro_retries):
            result = self.evolve(response_data, original_headers, original_params)
            attempts.append(result)
            tried_strategies.append(result.strategy_used)

            if result.retry_success:
                return result, attempts

            # 下一次排除已尝试的策略
            logger.info(
                f"[进化] 第 {attempt + 1} 次重试失败，"
                f"切换策略 (已尝试: {tried_strategies})"
            )

        # 全部失败，返回最后一次
        return attempts[-1] if attempts else EvolutionResult(
            original_failure="no attempts",
            detected_type=AntiCrawlType.UNKNOWN,
            strategy_used="none",
            retry_success=False,
            generation=self._generation,
            phase=EvolutionPhase.IDLE,
        ), attempts

    # ========== 检测 ==========

    def _detect_anti_crawl_type(self, response: Dict[str, Any]) -> AntiCrawlType:
        """
        从响应中检测反爬机制类型

        基于状态码、响应体特征、响应头模式综合判断。
        """
        status_code = response.get("status_code", 0)
        body = str(response.get("body", ""))
        resp_headers = response.get("headers", {})

        # 403 + 频率限制关键词
        if status_code == 403:
            if any(kw in body for kw in ["频繁", "频繁访问", "请稍后再试", "too many"]):
                return AntiCrawlType.RATE_LIMIT
            if any(kw in body for kw in ["forbidden", "access denied"]):
                return AntiCrawlType.IP_BAN
            return AntiCrawlType.SIGN_REJECT

        # 429 Too Many Requests
        if status_code == 429:
            return AntiCrawlType.RATE_LIMIT

        # 签名被拒（200 但返回错误码）
        if status_code == 200:
            if any(kw in body for kw in ["签名无效", "sign invalid", "h5st error"]):
                return AntiCrawlType.SIGN_REJECT
            if any(kw in body for kw in ["参数缺失", "param missing", "缺少参数"]):
                return AntiCrawlType.PARAM_MISSING
            if any(kw in body for kw in ["验证码", "captcha", "verify"]):
                return AntiCrawlType.CAPTCHA

        # Cookie 过期
        if status_code in (401, 302):
            return AntiCrawlType.COOKIE_EXPIRED

        # TLS 指纹检测（连接被重置）
        if status_code == 0:
            return AntiCrawlType.TLS_FINGERPRINT

        # 行为检测
        if any(kw in body for kw in ["异常访问", "行为异常", "abnormal"]):
            return AntiCrawlType.BEHAVIOR_DETECT

        # 指纹检测
        if any(kw in body for kw in ["设备异常", "fingerprint"]):
            return AntiCrawlType.FINGERPRINT_DETECT

        return AntiCrawlType.UNKNOWN

    # ========== 适应 ==========

    def _adapt(
        self,
        anti_type: AntiCrawlType,
        headers: Dict[str, str],
        params: Dict[str, Any],
    ) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
        """
        根据反爬类型选择适应策略

        优先级:
        1. 经验库中的成功策略（历史验证）
        2. 策略池 Thompson Sampling（贝叶斯选择）
        3. 默认策略（兜底）
        """
        # 1. 查经验库
        if self.config.enable_experience:
            best = self.experience.get_best_strategies_for_type(anti_type, top_n=1)
            if best and best[0][1] > 0.5:  # 成功率 > 50%
                strategy_name = best[0][0]
                logger.info(
                    f"[适应] 经验库命中: {strategy_name} "
                    f"(成功率 {best[0][1]:.0%})"
                )
                # 应用策略对应的变异
                variant = self.pool.get_variant(strategy_name)
                if variant:
                    headers, params, _ = self.mutator.apply_mutations(
                        headers, params, {variant.category: variant}
                    )
                    return strategy_name, headers, params

        # 2. 策略池 Thompson Sampling
        category = self._anti_type_to_category(anti_type)
        variant = self.pool.select(category=category)
        headers, params, _ = self.mutator.apply_mutations(
            headers, params, {variant.category: variant}
        )
        logger.info(f"[适应] 策略池选中: {variant.name} (类别: {category})")
        return variant.name, headers, params

    def _anti_type_to_category(self, anti_type: AntiCrawlType) -> str:
        """反爬类型 → 策略类别映射"""
        mapping = {
            AntiCrawlType.RATE_LIMIT: "timing",
            AntiCrawlType.CAPTCHA: "fingerprint",
            AntiCrawlType.IP_BAN: "fingerprint",
            AntiCrawlType.SIGN_REJECT: "param",
            AntiCrawlType.COOKIE_EXPIRED: "header",
            AntiCrawlType.FINGERPRINT_DETECT: "fingerprint",
            AntiCrawlType.TLS_FINGERPRINT: "header",
            AntiCrawlType.BEHAVIOR_DETECT: "timing",
            AntiCrawlType.PARAM_MISSING: "param",
        }
        return mapping.get(anti_type, "header")

    # ========== 验证 ==========

    def _validate(
        self, headers: Dict[str, str], params: Dict[str, Any]
    ) -> bool:
        """用新策略重试并验证"""
        if self._retry_callback is None:
            # 无回调时模拟成功（测试模式）
            logger.debug("[验证] 无重试回调，模拟成功")
            return True

        try:
            result = self._retry_callback(headers, params)
            return result.get("success", False)
        except Exception as e:
            logger.error(f"[验证] 重试异常: {e}")
            return False

    # ========== 宏进化 ==========

    def _macro_evolve(self, anti_type: AntiCrawlType) -> None:
        """
        宏进化: 当连续失败超过阈值时触发

        操作:
        1. 对当前最佳策略做变异
        2. 尝试交叉两个策略
        3. 增加进化代数
        """
        if not self.config.enable_mutation:
            return

        self._phase = EvolutionPhase.EVOLVING
        self._generation += 1
        logger.info(f"[宏进化] 第 {self._generation} 代进化开始 (触发: {anti_type.value})")

        # 找出当前最佳活跃策略
        category = self._anti_type_to_category(anti_type)
        best = self.pool.select(category=category)

        # 变异
        new_variant = self.pool.mutate(best.name, "param_tweak")
        if new_variant:
            logger.info(
                f"[宏进化] 变异: {best.name} → {new_variant.name} "
                f"(gen {new_variant.generation})"
            )

        # 交叉（如果有另一个好策略）
        if self.config.enable_crossover:
            second = self.pool.select(category=category, exclude=[best.name])
            if second:
                crossed = self.pool.crossover(best.name, second.name)
                if crossed:
                    logger.info(
                        f"[宏进化] 交叉: {best.name} × {second.name} "
                        f"→ {crossed.name}"
                    )

        self._consecutive_failures = 0  # 重置计数

    # ========== 状态查询 ==========

    def get_evolution_dashboard(self) -> Dict[str, Any]:
        """获取进化仪表盘"""
        return {
            "phase": self._phase.value,
            "total_evolutions": self._total_evolutions,
            "current_generation": self._generation,
            "consecutive_failures": self._consecutive_failures,
            "experience_summary": self.experience.get_summary(),
            "pool_status": self.pool.get_pool_status(),
            "mutator_stats": self.mutator.get_stats(),
            "recent_evolutions": [
                e.to_dict() for e in self._evolution_history[-10:]
            ],
        }

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def total_evolutions(self) -> int:
        return self._total_evolutions
