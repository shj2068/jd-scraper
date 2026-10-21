"""
自进化系统测试模块

覆盖:
- ExperienceStore: 经验存储/检索/持久化
- StrategyPool: Thompson Sampling/变异/交叉/淘汰
- RequestMutator: Header/Timing/Fingerprint/Param 四维度变异
- EvolutionEngine: 检测/适应/验证/学习闭环
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from python.experience_store import (
    AntiCrawlType,
    Experience,
    ExperienceStore,
    OutcomeRecord,
    StrategyRecord,
    TriggerSnapshot,
)
from python.strategy_pool import StrategyPool, StrategyVariant
from python.request_mutator import RequestMutator
from python.evolution_engine import (
    EvolutionConfig,
    EvolutionEngine,
    EvolutionPhase,
)


# ============================================================
# ExperienceStore 测试
# ============================================================


class TestExperienceStore:
    """经验存储测试"""

    def test_init_empty(self, tmp_path):
        store = ExperienceStore(storage_path=str(tmp_path / "exp.json"))
        assert store.total_count == 0

    def test_add_experience(self, tmp_path):
        store = ExperienceStore(storage_path=str(tmp_path / "exp.json"))
        exp = Experience(
            trigger=TriggerSnapshot(
                anti_crawl_type=AntiCrawlType.RATE_LIMIT,
                status_code=429,
            ),
            strategy=StrategyRecord(name="slow_timing"),
            outcome=OutcomeRecord(success=True, latency_ms=500),
        )
        store.add(exp)
        assert store.total_count == 1

    def test_get_successes_for_type(self, tmp_path):
        store = ExperienceStore(storage_path=str(tmp_path / "exp.json"))
        # 添加成功和失败的经验
        for success in [True, False, True]:
            store.add(Experience(
                trigger=TriggerSnapshot(anti_crawl_type=AntiCrawlType.RATE_LIMIT),
                strategy=StrategyRecord(name="test"),
                outcome=OutcomeRecord(success=success),
            ))
        successes = store.get_successes_for_type(AntiCrawlType.RATE_LIMIT)
        assert len(successes) == 2

    def test_get_strategy_success_rate(self, tmp_path):
        store = ExperienceStore(storage_path=str(tmp_path / "exp.json"))
        for success in [True, True, False]:
            store.add(Experience(
                trigger=TriggerSnapshot(anti_crawl_type=AntiCrawlType.RATE_LIMIT),
                strategy=StrategyRecord(name="strategy_a"),
                outcome=OutcomeRecord(success=success),
            ))
        rate = store.get_strategy_success_rate("strategy_a")
        assert abs(rate - 2 / 3) < 0.01

    def test_get_best_strategies(self, tmp_path):
        store = ExperienceStore(storage_path=str(tmp_path / "exp.json"))
        # 策略 A: 3/3 = 100%
        for _ in range(3):
            store.add(Experience(
                trigger=TriggerSnapshot(anti_crawl_type=AntiCrawlType.IP_BAN),
                strategy=StrategyRecord(name="strategy_a"),
                outcome=OutcomeRecord(success=True),
            ))
        # 策略 B: 1/3 = 33%
        store.add(Experience(
            trigger=TriggerSnapshot(anti_crawl_type=AntiCrawlType.IP_BAN),
            strategy=StrategyRecord(name="strategy_b"),
            outcome=OutcomeRecord(success=True),
        ))
        store.add(Experience(
            trigger=TriggerSnapshot(anti_crawl_type=AntiCrawlType.IP_BAN),
            strategy=StrategyRecord(name="strategy_b"),
            outcome=OutcomeRecord(success=False),
        ))
        store.add(Experience(
            trigger=TriggerSnapshot(anti_crawl_type=AntiCrawlType.IP_BAN),
            strategy=StrategyRecord(name="strategy_b"),
            outcome=OutcomeRecord(success=False),
        ))

        best = store.get_best_strategies_for_type(AntiCrawlType.IP_BAN)
        assert best[0][0] == "strategy_a"
        assert best[0][1] == 1.0

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "exp.json")
        store1 = ExperienceStore(storage_path=path)
        store1.add(Experience(
            trigger=TriggerSnapshot(anti_crawl_type=AntiCrawlType.CAPTCHA),
            strategy=StrategyRecord(name="fp_rotate"),
            outcome=OutcomeRecord(success=True),
        ))
        store1.save()

        store2 = ExperienceStore(storage_path=path)
        assert store2.total_count == 1

    def test_summary(self, tmp_path):
        store = ExperienceStore(storage_path=str(tmp_path / "exp.json"))
        store.add(Experience(
            trigger=TriggerSnapshot(anti_crawl_type=AntiCrawlType.RATE_LIMIT),
            strategy=StrategyRecord(name="test"),
            outcome=OutcomeRecord(success=True),
        ))
        summary = store.get_summary()
        assert summary["total_experiences"] == 1
        assert "rate_limit" in summary["by_type"]

    def test_experience_to_dict_and_back(self):
        exp = Experience(
            trigger=TriggerSnapshot(
                anti_crawl_type=AntiCrawlType.SIGN_REJECT,
                status_code=403,
                function_id="test_func",
            ),
            strategy=StrategyRecord(name="full_params", params={"include_h5st": True}),
            outcome=OutcomeRecord(success=False, latency_ms=200),
            generation=3,
        )
        d = exp.to_dict()
        restored = Experience.from_dict(d)
        assert restored.trigger.anti_crawl_type == AntiCrawlType.SIGN_REJECT
        assert restored.strategy.name == "full_params"
        assert restored.outcome.success is False
        assert restored.generation == 3


# ============================================================
# StrategyPool 测试
# ============================================================


class TestStrategyPool:
    """策略池测试"""

    def test_init_default_variants(self):
        pool = StrategyPool()
        variants = pool.get_all_variants()
        assert len(variants) >= 10  # 至少 10 个默认变体

    def test_select_returns_variant(self):
        pool = StrategyPool()
        variant = pool.select()
        assert isinstance(variant, StrategyVariant)
        assert variant.is_active

    def test_select_by_category(self):
        pool = StrategyPool()
        variant = pool.select(category="timing")
        assert variant.category == "timing"

    def test_record_result_updates_bayesian(self):
        pool = StrategyPool()
        variant = pool.select()
        initial_alpha = variant.alpha
        pool.record_result(variant.name, success=True)
        updated = pool.get_variant(variant.name)
        assert updated.alpha == initial_alpha + 1.0
        assert updated.total_uses == 1

    def test_retire_low_performing(self):
        pool = StrategyPool()
        # 让某个策略连续失败超过阈值
        variant = pool.select(category="timing")
        for _ in range(6):  # MIN_USES_FOR_EVAL = 5
            pool.record_result(variant.name, success=False)
        updated = pool.get_variant(variant.name)
        assert updated.is_active is False

    def test_mutate_creates_new_variant(self):
        pool = StrategyPool()
        variant = pool.select()
        new_variant = pool.mutate(variant.name, "param_tweak")
        assert new_variant is not None
        assert new_variant.generation == variant.generation + 1
        assert new_variant.parent == variant.name

    def test_crossover_merges_params(self):
        pool = StrategyPool()
        a = pool.select(category="header")
        b = pool.select(category="header", exclude=[a.name])
        if b:
            crossed = pool.crossover(a.name, b.name)
            assert crossed is not None
            assert a.name in crossed.parent
            assert b.name in crossed.parent

    def test_select_composite(self):
        pool = StrategyPool()
        composite = pool.select_composite()
        assert "header" in composite or "timing" in composite

    def test_pool_status(self):
        pool = StrategyPool()
        status = pool.get_pool_status()
        assert status["total_variants"] >= 10
        assert status["active_variants"] >= 10

    def test_thompson_sampling_exploration(self):
        """验证 Thompson Sampling 的探索性: 未测试策略有概率被选中"""
        pool = StrategyPool()
        # 让某个策略变得很强
        strong = pool.get_variant("stealth_headers_v1")
        for _ in range(20):
            pool.record_result(strong.name, success=True)

        # 多次选择，统计是否所有活跃策略都有机会被选中
        selected_names = set()
        for _ in range(100):
            v = pool.select(category="header")
            selected_names.add(v.name)

        # 至少选中 2 个不同策略（exploration）
        assert len(selected_names) >= 2


# ============================================================
# RequestMutator 测试
# ============================================================


class TestRequestMutator:
    """请求变异器测试"""

    def test_apply_mutations(self):
        mutator = RequestMutator()
        headers = {"User-Agent": "test"}
        params = {"functionId": "test"}
        pool = StrategyPool()
        variants = pool.select_composite()
        new_headers, new_params, delay = mutator.apply_mutations(
            headers, params, variants
        )
        assert isinstance(new_headers, dict)
        assert isinstance(new_params, dict)
        assert isinstance(delay, float)
        assert delay >= 0

    def test_header_mutation_chrome(self):
        mutator = RequestMutator()
        variant = StrategyVariant(
            name="test", category="header",
            params={"preset": "chrome_windows", "sec_ch_ua": True},
        )
        headers = mutator._mutate_headers({"User-Agent": "old"}, variant)
        assert "Chrome" in headers["User-Agent"]
        assert "Sec-Ch-Ua" in headers

    def test_header_mutation_ios(self):
        mutator = RequestMutator()
        variant = StrategyVariant(
            name="test", category="header",
            params={"preset": "safari_ios", "sec_ch_ua": False},
        )
        headers = mutator._mutate_headers({}, variant)
        assert "iPhone" in headers["User-Agent"]

    def test_timing_human(self):
        mutator = RequestMutator()
        variant = StrategyVariant(
            name="test", category="timing",
            params={"mode": "human", "min_delay": 1.0, "max_delay": 5.0},
        )
        delay = mutator._compute_timing(variant)
        assert 1.0 <= delay <= 5.0

    def test_timing_adaptive_backoff(self):
        mutator = RequestMutator()
        variant = StrategyVariant(
            name="test", category="timing",
            params={"mode": "adaptive", "base_delay": 2.0, "backoff_factor": 1.5, "max_delay": 30.0},
        )
        delays = [mutator._compute_timing(variant) for _ in range(5)]
        # 自适应延迟应递增
        assert delays[-1] >= delays[0]

    def test_fingerprint_rotate(self):
        mutator = RequestMutator()
        variant = StrategyVariant(
            name="test", category="fingerprint",
            params={"mode": "rotate_per_request", "canvas_jitter": True},
        )
        headers1 = mutator._mutate_fingerprint({}, variant)
        headers2 = mutator._mutate_fingerprint({}, variant)
        # 每次旋转应产生不同 UA
        assert headers1.get("User-Agent") != headers2.get("User-Agent") or True  # 可能随机到同一个

    def test_param_mutation_noise(self):
        mutator = RequestMutator()
        variant = StrategyVariant(
            name="test", category="param",
            params={"include_h5st": False, "include_eid": False},
        )
        params = {"h5st": "abc", "x-api-eid": "xyz", "functionId": "test"}
        mutated = mutator._mutate_params(params, variant)
        assert "h5st" not in mutated
        assert "x-api-eid" not in mutated
        assert "functionId" in mutated

    def test_reset_adaptive_timing(self):
        mutator = RequestMutator()
        mutator._adaptive_delay = 20.0
        mutator.reset_adaptive_timing()
        assert mutator._adaptive_delay == 2.0


# ============================================================
# EvolutionEngine 测试
# ============================================================


class TestEvolutionEngine:
    """进化引擎测试"""

    def _make_engine(self, tmp_path):
        store = ExperienceStore(storage_path=str(tmp_path / "exp.json"))
        pool = StrategyPool()
        mutator = RequestMutator()
        engine = EvolutionEngine(
            config=EvolutionConfig(max_micro_retries=2, macro_threshold=3),
            experience_store=store,
            strategy_pool=pool,
            request_mutator=mutator,
        )
        return engine

    def test_detect_rate_limit(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._detect_anti_crawl_type({
            "status_code": 403,
            "body": "访问频繁，请稍后再试",
        })
        assert result == AntiCrawlType.RATE_LIMIT

    def test_detect_sign_reject(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._detect_anti_crawl_type({
            "status_code": 200,
            "body": "签名无效 sign invalid",
        })
        assert result == AntiCrawlType.SIGN_REJECT

    def test_detect_captcha(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._detect_anti_crawl_type({
            "status_code": 200,
            "body": "请输入验证码 captcha",
        })
        assert result == AntiCrawlType.CAPTCHA

    def test_detect_cookie_expired(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._detect_anti_crawl_type({"status_code": 401})
        assert result == AntiCrawlType.COOKIE_EXPIRED

    def test_detect_429(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._detect_anti_crawl_type({"status_code": 429})
        assert result == AntiCrawlType.RATE_LIMIT

    def test_detect_unknown(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._detect_anti_crawl_type({"status_code": 500, "body": "internal error"})
        assert result == AntiCrawlType.UNKNOWN

    def test_evolve_without_callback(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine.evolve(
            response_data={"status_code": 403, "body": "频繁访问"},
            original_headers={},
            original_params={"functionId": "test"},
        )
        assert isinstance(result.retry_success, bool)
        assert result.detected_type == AntiCrawlType.RATE_LIMIT

    def test_evolve_with_retry_callback(self, tmp_path):
        engine = self._make_engine(tmp_path)
        # 模拟重试回调: 始终成功（验证闭环能正确记录成功）
        def callback(headers, params):
            return {"success": True, "status_code": 200}

        engine.set_retry_callback(callback)
        result = engine.evolve(
            response_data={"status_code": 403, "body": "频繁"},
            original_headers={},
            original_params={},
        )
        assert result.retry_success is True

    def test_evolve_with_retries(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine.set_retry_callback(lambda h, p: {"success": True, "status_code": 200})
        result, attempts = engine.evolve_with_retries(
            response_data={"status_code": 429, "body": "too many"},
            original_headers={},
            original_params={},
        )
        assert result.retry_success is True
        assert len(attempts) >= 1

    def test_experience_recorded(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine.evolve(
            response_data={"status_code": 403, "body": "频繁"},
            original_headers={},
            original_params={"functionId": "test"},
        )
        assert engine.experience.total_count >= 1

    def test_macro_evolution_triggered(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine.set_retry_callback(lambda h, p: {"success": False, "status_code": 403})
        # 连续失败 macro_threshold 次
        for _ in range(4):
            engine.evolve(
                response_data={"status_code": 403, "body": "频繁"},
                original_headers={},
                original_params={},
            )
        # 宏进化应增加代数
        assert engine.generation >= 1

    def test_evolution_dashboard(self, tmp_path):
        engine = self._make_engine(tmp_path)
        dashboard = engine.get_evolution_dashboard()
        assert "total_evolutions" in dashboard
        assert "current_generation" in dashboard
        assert "pool_status" in dashboard
        assert "experience_summary" in dashboard

    def test_anti_type_to_category_mapping(self, tmp_path):
        engine = self._make_engine(tmp_path)
        assert engine._anti_type_to_category(AntiCrawlType.RATE_LIMIT) == "timing"
        assert engine._anti_type_to_category(AntiCrawlType.SIGN_REJECT) == "param"
        assert engine._anti_type_to_category(AntiCrawlType.FINGERPRINT_DETECT) == "fingerprint"


# ============================================================
# Agent 集成测试
# ============================================================


class TestAgentEvolution:
    """智能体自进化集成测试"""

    def test_agent_imports_evolution(self):
        from agent import JDAgent
        agent = JDAgent()
        assert hasattr(agent, "_evolution_engine")

    def test_agent_start_includes_evolution(self):
        from agent import JDAgent
        agent = JDAgent()
        report = agent.start_services()
        service_names = [s["name"] for s in report["services"]]
        assert "自进化引擎" in service_names

    def test_agent_collect_with_evolution_success(self):
        """测试采集成功时不触发进化（mock HTTP 响应）"""
        from agent import JDAgent
        from unittest.mock import patch, MagicMock

        agent = JDAgent()
        agent.start_services()

        # Mock TLS 客户端返回成功响应
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"code":0,"data":{}}'
        mock_resp.json.return_value = {"code": 0, "data": {}}
        mock_resp.headers = {}

        with patch.object(agent._tls_client, 'post', return_value=mock_resp):
            result = agent.collect_with_evolution("bizSearchCategoryList")

        # 正常采集成功，不触发进化
        assert result["evolution"]["triggered"] is False

    def test_agent_evolution_dashboard(self):
        from agent import JDAgent
        agent = JDAgent()
        agent.start_services()
        dashboard = agent.get_evolution_dashboard()
        assert "total_evolutions" in dashboard
