"""
策略池与多臂赌博机选型模块

维护多个反爬策略变体，使用 Thompson Sampling（汤普森采样）
自动选择最优策略。每次策略执行后更新贝叶斯后验，
让选择越来越精准。

策略变体维度:
- header_variants: 请求头组合变体
- timing_variants: 请求时序变体
- fingerprint_variants: 指纹变体
- param_variants: 参数注入变体
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .utils import setup_logger

logger = setup_logger(__name__)


@dataclass
class StrategyVariant:
    """策略变体"""

    name: str
    category: str  # header / timing / fingerprint / param / composite
    params: Dict[str, Any] = field(default_factory=dict)
    # 贝叶斯参数 (Beta 分布)
    alpha: float = 1.0  # 成功次数 + 1
    beta: float = 1.0   # 失败次数 + 1
    # 统计
    total_uses: int = 0
    total_successes: int = 0
    last_used: float = 0.0
    # 进化元数据
    generation: int = 1
    parent: Optional[str] = None  # 父策略名称
    is_active: bool = True

    @property
    def success_rate(self) -> float:
        if self.total_uses == 0:
            return 0.0
        return self.total_successes / self.total_uses

    @property
    def expected_value(self) -> float:
        """Beta 分布期望值 = alpha / (alpha + beta)"""
        return self.alpha / (self.alpha + self.beta)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "category": self.category,
            "params": self.params,
            "alpha": self.alpha,
            "beta": self.beta,
            "total_uses": self.total_uses,
            "total_successes": self.total_successes,
            "success_rate": round(self.success_rate, 4),
            "expected_value": round(self.expected_value, 4),
            "generation": self.generation,
            "parent": self.parent,
            "is_active": self.is_active,
        }


def _sample_beta(alpha: float, beta: float) -> float:
    """从 Beta(alpha, beta) 分布采样"""
    return random.betavariate(alpha, beta)


class StrategyPool:
    """
    策略池

    管理多类策略变体，使用 Thompson Sampling 自动选择。
    支持策略的创建、变异、淘汰和进化。
    """

    # 淘汰阈值
    MIN_USES_FOR_EVAL = 5       # 至少使用 N 次才评估
    RETIRE_THRESHOLD = 0.2      # 成功率 < 20% 淘汰
    MAX_VARIANTS_PER_CATEGORY = 10  # 每类最多变体数

    def __init__(self):
        self._variants: Dict[str, StrategyVariant] = {}
        self._init_default_variants()

    def _init_default_variants(self) -> None:
        """初始化默认策略变体"""
        # ---- Header 变体 ----
        self.add_variant(StrategyVariant(
            name="stealth_headers_v1",
            category="header",
            params={
                "preset": "chrome_windows",
                "sec_ch_ua": True,
                "sec_fetch": True,
            },
        ))
        self.add_variant(StrategyVariant(
            name="stealth_headers_v2",
            category="header",
            params={
                "preset": "chrome_android",
                "sec_ch_ua": True,
                "sec_fetch": True,
                "extra_headers": {"X-Requested-With": "XMLHttpRequest"},
            },
        ))
        self.add_variant(StrategyVariant(
            name="mobile_headers",
            category="header",
            params={
                "preset": "safari_ios",
                "sec_ch_ua": False,
                "sec_fetch": False,
            },
        ))

        # ---- Timing 变体 ----
        self.add_variant(StrategyVariant(
            name="human_timing",
            category="timing",
            params={
                "mode": "human",
                "min_delay": 1.0,
                "max_delay": 5.0,
                "burst_pause": 0.3,
            },
        ))
        self.add_variant(StrategyVariant(
            name="slow_timing",
            category="timing",
            params={
                "mode": "slow",
                "min_delay": 3.0,
                "max_delay": 10.0,
            },
        ))
        self.add_variant(StrategyVariant(
            name="adaptive_timing",
            category="timing",
            params={
                "mode": "adaptive",
                "base_delay": 2.0,
                "backoff_factor": 1.5,
                "max_delay": 30.0,
            },
        ))

        # ---- Fingerprint 变体 ----
        self.add_variant(StrategyVariant(
            name="fingerprint_rotate",
            category="fingerprint",
            params={
                "mode": "rotate_per_request",
                "canvas_jitter": True,
                "webgl_spoof": True,
            },
        ))
        self.add_variant(StrategyVariant(
            name="fingerprint_sticky",
            category="fingerprint",
            params={
                "mode": "sticky_session",
                "canvas_jitter": False,
                "webgl_spoof": True,
            },
        ))

        # ---- Param 变体 ----
        self.add_variant(StrategyVariant(
            name="full_params",
            category="param",
            params={
                "include_h5st": True,
                "include_eid": True,
                "include_request_id": True,
                "include_rp_client": True,
            },
        ))
        self.add_variant(StrategyVariant(
            name="minimal_params",
            category="param",
            params={
                "include_h5st": False,
                "include_eid": False,
                "include_request_id": True,
                "include_rp_client": True,
            },
        ))

        logger.info(f"策略池初始化: {len(self._variants)} 个默认变体")

    def add_variant(self, variant: StrategyVariant) -> None:
        """添加策略变体"""
        self._variants[variant.name] = variant

    def get_variant(self, name: str) -> Optional[StrategyVariant]:
        """获取指定变体"""
        return self._variants.get(name)

    # ========== Thompson Sampling 选择 ==========

    def select(
        self,
        category: Optional[str] = None,
        exclude: Optional[List[str]] = None,
    ) -> StrategyVariant:
        """
        Thompson Sampling 选择策略

        从 Beta(alpha, beta) 分布中采样，选择采样值最高的变体。
        这实现了 exploration-exploitation 的自然平衡：
        - 高成功率策略的 alpha 大，采样值倾向高位（exploitation）
        - 未充分测试的策略 alpha/beta 接近 1，采样值分布广（exploration）

        Args:
            category: 限定类别（None 表示全部）
            exclude: 排除的变体名称

        Returns:
            选中的策略变体
        """
        exclude = set(exclude or [])
        candidates = [
            v for v in self._variants.values()
            if v.is_active
            and v.name not in exclude
            and (category is None or v.category == category)
        ]

        if not candidates:
            # 无候选时返回默认
            logger.warning("无可用策略变体，返回默认")
            return self._variants.get("full_params", list(self._variants.values())[0])

        # Thompson Sampling: 从每个候选的 Beta 分布采样
        best = max(candidates, key=lambda v: _sample_beta(v.alpha, v.beta))
        logger.debug(
            f"Thompson Sampling 选中: {best.name} "
            f"(α={best.alpha:.1f}, β={best.beta:.1f}, E={best.expected_value:.3f})"
        )
        return best

    def select_composite(self) -> Dict[str, StrategyVariant]:
        """
        从每个类别各选一个，组成复合策略

        Returns:
            {category: selected_variant}
        """
        categories = set(v.category for v in self._variants.values() if v.is_active)
        return {cat: self.select(category=cat) for cat in categories}

    # ========== 反馈更新 ==========

    def record_result(self, variant_name: str, success: bool) -> None:
        """
        记录策略执行结果，更新贝叶斯后验

        Beta 分布更新规则:
        - 成功: alpha += 1
        - 失败: beta += 1

        Args:
            variant_name: 策略变体名称
            success: 是否成功
        """
        variant = self._variants.get(variant_name)
        if variant is None:
            logger.warning(f"未知策略变体: {variant_name}")
            return

        variant.total_uses += 1
        variant.last_used = time.time()

        if success:
            variant.alpha += 1.0
            variant.total_successes += 1
        else:
            variant.beta += 1.0

        logger.debug(
            f"策略更新: {variant_name} → "
            f"{'✓' if success else '✗'} "
            f"(α={variant.alpha:.1f}, β={variant.beta:.1f}, "
            f"rate={variant.success_rate:.1%})"
        )

        # 检查是否需要淘汰
        if variant.total_uses >= self.MIN_USES_FOR_EVAL:
            if variant.success_rate < self.RETIRE_THRESHOLD:
                self._retire_variant(variant_name)

    def _retire_variant(self, name: str) -> None:
        """淘汰低效策略"""
        variant = self._variants.get(name)
        if variant and variant.is_active:
            variant.is_active = False
            logger.info(
                f"策略淘汰: {name} (成功率 {variant.success_rate:.1%} "
                f"< {self.RETIRE_THRESHOLD:.0%})"
            )

    # ========== 进化操作 ==========

    def mutate(
        self,
        parent_name: str,
        mutation_type: str = "param_tweak",
    ) -> Optional[StrategyVariant]:
        """
        策略变异

        基于父策略生成新变体。

        Args:
            parent_name: 父策略名称
            mutation_type: 变异类型
                - "param_tweak": 参数微调
                - "crossover": 与另一策略交叉
                - "boost": 增强某维度

        Returns:
            新变体（如果成功）
        """
        parent = self._variants.get(parent_name)
        if parent is None:
            return None

        category_variants = [
            v for v in self._variants.values()
            if v.category == parent.category and v.is_active
        ]
        if len(category_variants) >= self.MAX_VARIANTS_PER_CATEGORY:
            logger.debug(f"类别 {parent.category} 变体已满，跳过变异")
            return None

        generation = parent.generation + 1
        new_name = f"{parent.name}_gen{generation}_{random.randint(1000, 9999)}"

        if mutation_type == "param_tweak":
            new_params = self._tweak_params(parent.params)
        elif mutation_type == "boost":
            new_params = self._boost_params(parent.params)
        else:
            new_params = parent.params.copy()

        new_variant = StrategyVariant(
            name=new_name,
            category=parent.category,
            params=new_params,
            alpha=parent.alpha,  # 继承贝叶斯先验
            beta=parent.beta,
            generation=generation,
            parent=parent_name,
        )

        self.add_variant(new_variant)
        logger.info(f"策略变异: {parent_name} → {new_name} (gen {generation})")
        return new_variant

    def crossover(
        self,
        name_a: str,
        name_b: str,
    ) -> Optional[StrategyVariant]:
        """
        策略交叉：合并两个策略的参数

        Args:
            name_a: 策略 A 名称
            name_b: 策略 B 名称

        Returns:
            新变体
        """
        a = self._variants.get(name_a)
        b = self._variants.get(name_b)
        if a is None or b is None:
            return None

        # 交叉合并参数（各取一半）
        merged_params = {**a.params}
        for key, value in b.params.items():
            if key not in merged_params or random.random() < 0.5:
                merged_params[key] = value

        new_name = f"crossover_{name_a}_{name_b}_{random.randint(1000, 9999)}"
        new_variant = StrategyVariant(
            name=new_name,
            category=a.category,
            params=merged_params,
            alpha=max(a.alpha, b.alpha),
            beta=min(a.beta, b.beta),
            generation=max(a.generation, b.generation) + 1,
            parent=f"{name_a}+{name_b}",
        )

        self.add_variant(new_variant)
        logger.info(f"策略交叉: {name_a} × {name_b} → {new_name}")
        return new_variant

    def _tweak_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """参数微调"""
        new_params = params.copy()
        for key, value in new_params.items():
            if isinstance(value, (int, float)):
                # 数值型：±20% 抖动
                jitter = value * 0.2
                new_params[key] = value + random.uniform(-jitter, jitter)
            elif isinstance(value, bool):
                # 布尔型：30% 概率翻转
                if random.random() < 0.3:
                    new_params[key] = not value
        return new_params

    def _boost_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """参数增强"""
        new_params = params.copy()
        for key, value in new_params.items():
            if isinstance(value, bool) and not value:
                # 把关闭的选项打开
                new_params[key] = True
            elif isinstance(value, (int, float)) and value > 0:
                # 数值增大 50%
                new_params[key] = value * 1.5
        return new_params

    # ========== 状态查询 ==========

    def get_pool_status(self) -> Dict[str, Any]:
        """获取策略池状态"""
        active = [v for v in self._variants.values() if v.is_active]
        retired = [v for v in self._variants.values() if not v.is_active]

        by_category: Dict[str, int] = {}
        for v in active:
            by_category[v.category] = by_category.get(v.category, 0) + 1

        return {
            "total_variants": len(self._variants),
            "active_variants": len(active),
            "retired_variants": len(retired),
            "by_category": by_category,
            "top_performers": [
                v.to_dict()
                for v in sorted(active, key=lambda x: -x.expected_value)[:5]
            ],
        }

    def get_all_variants(self) -> List[StrategyVariant]:
        return list(self._variants.values())

    def reset(self) -> None:
        """重置策略池"""
        self._variants.clear()
        self._init_default_variants()
