#!/usr/bin/env python3
"""
AI+JS逆向京东工业网数据采集智能体

基于 jd-scraper v2.0 架构，整合 h5st 解析、API 嗅探、生产监控、
降级策略等模块，提供端到端的智能采集编排能力。

合规警示: 本工具仅用于技术学习与研究目的。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# 项目路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from python.sign import generate_sign
from python.models import SignParams, JDRequest
from python.tls_client import TLSClient
from python.fingerprint import FingerprintGenerator
from python.anti_detect import AntiDetect
from python.cookie_manager import CookieManager
from python.request_builder import RequestBuilder
from python.jsrpc_client import JSRPCClient
from python.h5st_parser import (
    H5stVersion,
    SignStrategy,
    parse_h5st,
    detect_version_from_samples,
    get_strategy_recommendation,
)
from python.monitor import ProductionMonitor, MonitorConfig, AlertLevel
from python.api_sniffer import APISniffer, ParamType, SniffResult
from python.evolution_engine import (
    EvolutionEngine,
    EvolutionConfig,
    EvolutionPhase,
    EvolutionResult,
)
from python.strategy_pool import StrategyPool
from python.request_mutator import RequestMutator
from python.experience_store import ExperienceStore, AntiCrawlType
from python.utils import setup_logger

logger = setup_logger("agent")


# ============================================================
# 智能体状态
# ============================================================


class AgentPhase(str, Enum):
    """智能体工作阶段"""

    IDLE = "idle"
    DIAGNOSING = "diagnosing"  # Phase 1: 环境诊断
    STARTING = "starting"  # Phase 2: 服务启动
    SNIFFING = "sniffing"  # Phase 3: API 嗅探
    STRATEGY = "strategy"  # Phase 4: 签名策略选型
    COLLECTING = "collecting"  # Phase 5: 数据采集
    MONITORING = "monitoring"  # Phase 6: 持续监控
    ERROR = "error"
    COMPLETED = "completed"


@dataclass
class AgentState:
    """智能体运行状态"""

    phase: AgentPhase = AgentPhase.IDLE
    jsrpc_healthy: bool = False
    h5st_version: Optional[str] = None
    sign_strategy: Optional[str] = None
    total_requests: int = 0
    success_requests: int = 0
    failed_requests: int = 0
    alerts: List[Dict] = field(default_factory=list)
    discovered_apis: List[Dict] = field(default_factory=list)
    start_time: float = 0
    errors: List[str] = field(default_factory=list)
    # v2.1 自进化状态
    evolution_generation: int = 0
    evolution_count: int = 0
    last_evolution_type: Optional[str] = None

    @property
    def success_rate(self) -> float:
        total = self.success_requests + self.failed_requests
        return self.success_requests / total if total > 0 else 0.0

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time if self.start_time > 0 else 0.0

    def to_dict(self) -> Dict:
        return {
            "phase": self.phase.value,
            "jsrpc_healthy": self.jsrpc_healthy,
            "h5st_version": self.h5st_version,
            "sign_strategy": self.sign_strategy,
            "total_requests": self.total_requests,
            "success_rate": f"{self.success_rate:.1%}",
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "discovered_apis": len(self.discovered_apis),
            "alerts": len(self.alerts),
            "errors": self.errors[-5:],  # 最近 5 条
            "evolution_generation": self.evolution_generation,
            "evolution_count": self.evolution_count,
            "last_evolution_type": self.last_evolution_type,
        }


# ============================================================
# 智能体核心
# ============================================================


class JDAgent:
    """
    AI+JS逆向京东工业网数据采集智能体

    编排 jd-scraper v2.0 所有模块，提供 6 阶段工作流：
    环境诊断 → 服务启动 → API 嗅探 → 策略选型 → 数据采集 → 持续监控
    """

    def __init__(self, config_path: Optional[str] = None):
        self.state = AgentState()
        self.project_root = PROJECT_ROOT

        # 加载配置
        self._config: Dict[str, Any] = {}
        cfg_path = config_path or str(PROJECT_ROOT / "config" / "settings.yaml")
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}

        # 核心模块（延迟初始化）
        self._jsrpc_client: Optional[JSRPCClient] = None
        self._cookie_manager: Optional[CookieManager] = None
        self._fingerprint: Optional[FingerprintGenerator] = None
        self._anti_detect: Optional[AntiDetect] = None
        self._request_builder: Optional[RequestBuilder] = None
        self._monitor: Optional[ProductionMonitor] = None
        self._sniffer: Optional[APISniffer] = None
        # v2.1 自进化模块
        self._evolution_engine: Optional[EvolutionEngine] = None
        self._strategy_pool: Optional[StrategyPool] = None
        self._request_mutator: Optional[RequestMutator] = None
        self._experience_store: Optional[ExperienceStore] = None

        logger.info("JD 数据采集智能体初始化完成")

    # ============================================================
    # Phase 1: 环境诊断
    # ============================================================

    def diagnose_environment(self) -> Dict[str, Any]:
        """
        Phase 1: 诊断运行环境

        Returns:
            环境诊断报告
        """
        self.state.phase = AgentPhase.DIAGNOSING
        report: Dict[str, Any] = {"phase": "environment_diagnosis", "checks": []}

        # 1. Python 版本
        py_version = sys.version.split()[0]
        py_ok = sys.version_info >= (3, 10)
        report["checks"].append(
            {
                "name": "Python 版本",
                "value": py_version,
                "status": "ok" if py_ok else "error",
                "required": ">= 3.10",
            }
        )

        # 2. Node.js 版本
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            node_version = result.stdout.strip()
            node_ok = result.returncode == 0
        except Exception:
            node_version = "未安装"
            node_ok = False
        report["checks"].append(
            {
                "name": "Node.js",
                "value": node_version,
                "status": "ok" if node_ok else "error",
                "required": ">= 18.0",
            }
        )

        # 3. Python 依赖
        deps = {
            "yaml": "pyyaml",
            "requests": "requests",
            "httpx": "httpx",
            "curl_cffi": "curl_cffi",
        }
        missing_deps = []
        for module, package in deps.items():
            try:
                __import__(module)
                report["checks"].append(
                    {"name": f"Python: {package}", "status": "ok"}
                )
            except ImportError:
                missing_deps.append(package)
                report["checks"].append(
                    {"name": f"Python: {package}", "status": "missing"}
                )

        # 4. Node.js 依赖
        node_modules = self.project_root / "node" / "node_modules"
        node_deps_ok = node_modules.exists()
        report["checks"].append(
            {
                "name": "Node.js 依赖",
                "status": "ok" if node_deps_ok else "missing",
                "path": str(node_modules),
            }
        )

        # 5. 配置文件
        config_path = self.project_root / "config" / "settings.yaml"
        config_ok = config_path.exists()
        report["checks"].append(
            {
                "name": "配置文件",
                "status": "ok" if config_ok else "missing",
                "path": str(config_path),
            }
        )

        # 6. Playwright Chromium
        try:
            result = subprocess.run(
                ["npx", "playwright", "install", "--dry-run"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(self.project_root / "node"),
            )
            playwright_ok = result.returncode == 0
        except Exception:
            playwright_ok = False
        report["checks"].append(
            {
                "name": "Playwright Chromium",
                "status": "ok" if playwright_ok else "check_manual",
            }
        )

        # 汇总
        all_ok = all(
            c.get("status") == "ok" for c in report["checks"]
        )
        report["ready"] = all_ok
        report["missing"] = missing_deps

        if all_ok:
            logger.info("环境诊断通过 ✓")
        else:
            logger.warning(f"环境诊断存在问题: {missing_deps}")
            self.state.errors.append(f"缺失依赖: {missing_deps}")

        return report

    # ============================================================
    # Phase 2: 服务启动
    # ============================================================

    def start_services(self) -> Dict[str, Any]:
        """
        Phase 2: 启动所有服务

        Returns:
            启动报告
        """
        self.state.phase = AgentPhase.STARTING
        self.state.start_time = time.time()
        report: Dict[str, Any] = {"phase": "service_startup", "services": []}

        # 1. 初始化指纹生成器
        self._fingerprint = FingerprintGenerator()
        uuid = self._fingerprint.get_or_create_uuid()
        report["services"].append(
            {"name": "设备指纹", "status": "ok", "uuid": uuid}
        )

        # 2. 初始化反检测
        self._anti_detect = AntiDetect()
        report["services"].append({"name": "反检测模块", "status": "ok"})

        # 3. 初始化 Cookie 管理器
        self._cookie_manager = CookieManager()
        report["services"].append({"name": "Cookie 管理器", "status": "ok"})

        # 4. 初始化监控器
        self._monitor = ProductionMonitor(
            MonitorConfig(
                sign_failure_threshold=0.1,
                cookie_expiry_warning_seconds=600,
                ip_ban_rate_threshold=0.2,
                window_size=100,
            )
        )
        report["services"].append({"name": "生产监控器", "status": "ok"})

        # 5. 初始化 API 嗅探器
        self._sniffer = APISniffer()
        report["services"].append({"name": "API 嗅探器", "status": "ok"})

        # 6. 检查 JSRPC 服务
        jsrpc_url = self._config.get("jsrpc", {}).get("server_url", "http://localhost:3001")
        self._jsrpc_client = JSRPCClient(
            server_url=jsrpc_url, timeout=5.0
        )
        jsrpc_ok = self._jsrpc_client.check_health()
        self.state.jsrpc_healthy = jsrpc_ok
        report["services"].append(
            {
                "name": "JSRPC 签名服务",
                "status": "ok" if jsrpc_ok else "unavailable",
                "url": jsrpc_url,
                "hint": None if jsrpc_ok else "cd node && node server.js",
            }
        )

        # 7. 初始化请求构建器
        api_config = self._config.get("api", {})
        self._request_builder = RequestBuilder(
            jsrpc_client=self._jsrpc_client if jsrpc_ok else None,
            cookie_manager=self._cookie_manager,
            anti_detect=self._anti_detect,
            fingerprint=self._fingerprint,
            appid=api_config.get("appid", "search-pc-java"),
            client=api_config.get("client", "pc"),
            client_version=api_config.get("client_version", "1.0.0"),
        )
        report["services"].append({"name": "请求构建器", "status": "ok"})

        # 8. 初始化自进化引擎 (v2.1)
        self._experience_store = ExperienceStore()
        self._strategy_pool = StrategyPool()
        self._request_mutator = RequestMutator(
            anti_detect=self._anti_detect,
            fingerprint=self._fingerprint,
        )
        self._evolution_engine = EvolutionEngine(
            experience_store=self._experience_store,
            strategy_pool=self._strategy_pool,
            request_mutator=self._request_mutator,
        )
        report["services"].append({
            "name": "自进化引擎",
            "status": "ok",
        })

        # 9. 初始化 TLS 客户端（用于真实 HTTP 请求）
        self._tls_client = TLSClient(
            tls_preset=self._config.get("anti_detect", {}).get("tls_fingerprint", "chrome118"),
            timeout=30.0,
        )
        report["services"].append({"name": "TLS 客户端", "status": "ok"})

        return report

    # ============================================================
    # Phase 3: API 嗅探
    # ============================================================

    def sniff_api(self, requests_data: List[Dict]) -> Dict[str, Any]:
        """
        Phase 3: 分析 API 请求并生成嗅探报告

        Args:
            requests_data: 捕获的请求列表 [{"url": ..., "method": ..., ...}]

        Returns:
            嗅探报告
        """
        self.state.phase = AgentPhase.SNIFFING

        if not self._sniffer:
            self._sniffer = APISniffer()

        self._sniffer.start_sniff()

        for req in requests_data:
            self._sniffer.capture_request(req)

        result = self._sniffer.stop_sniff()

        # 更新状态
        self.state.discovered_apis = [api.to_dict() for api in result.apis]

        # 生成报告
        report = {
            "phase": "api_sniffing",
            "summary": {
                "total_requests": result.total_requests,
                "api_count": result.api_count,
                "sniff_duration": f"{result.sniff_duration:.1f}s",
                "signature_params": result.signature_params,
                "reverse_targets": result.reverse_targets,
            },
            "apis": [api.to_dict() for api in result.apis],
            "markdown_report": self._sniffer.generate_report(result),
        }

        logger.info(
            f"API 嗅探完成: {result.api_count} 个 API, "
            f"{len(result.reverse_targets)} 个逆向目标"
        )

        return report

    # ============================================================
    # Phase 4: 签名策略选型
    # ============================================================

    def select_strategy(self, h5st_samples: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Phase 4: 根据 h5st 版本选择最优签名策略

        Args:
            h5st_samples: h5st 样本列表（可选，用于版本检测）

        Returns:
            策略选型报告
        """
        self.state.phase = AgentPhase.STRATEGY

        if h5st_samples:
            version = detect_version_from_samples(h5st_samples)
        else:
            # 默认假设 v2
            version = H5stVersion.V2

        self.state.h5st_version = version.value
        recommendation = get_strategy_recommendation(version)
        self.state.sign_strategy = recommendation["strategy"]

        # 通知监控器版本变化
        if self._monitor:
            self._monitor.track_h5st_version(version.value)

        report = {
            "phase": "strategy_selection",
            "detected_version": version.value,
            "recommended_strategy": recommendation["strategy"],
            "reliability": recommendation["reliability"],
            "maintenance_cost": recommendation["maintenance_cost"],
            "description": recommendation["description"],
            "notes": recommendation["notes"],
        }

        logger.info(
            f"签名策略选型: {version.value} → {recommendation['strategy']} "
            f"(可靠性: {recommendation['reliability']})"
        )

        return report

    # ============================================================
    # Phase 5: 数据采集
    # ============================================================

    def collect(
        self,
        function_id: str,
        body: Optional[Dict] = None,
        use_jsrpc: bool = True,
    ) -> Dict[str, Any]:
        """
        Phase 5: 执行单次数据采集（含真实 HTTP 请求）

        Args:
            function_id: API functionId
            body: 业务参数
            use_jsrpc: 是否使用 JSRPC 签名

        Returns:
            采集结果（含真实响应数据）
        """
        self.state.phase = AgentPhase.COLLECTING
        self.state.total_requests += 1

        body = body or {}

        try:
            # 生成签名
            uuid = self._fingerprint.get_or_create_uuid() if self._fingerprint else "test-uuid"
            sign, t = generate_sign(
                function_id=function_id,
                body=json.dumps(body, ensure_ascii=False),
                uuid=uuid,
            )

            # 构造请求
            if self._request_builder:
                request = self._request_builder.build_request(
                    function_id=function_id,
                    body=body,
                    include_h5st=use_jsrpc and self.state.jsrpc_healthy,
                )
                params = request.to_params()
            else:
                params = {
                    "functionId": function_id,
                    "body": json.dumps(body),
                    "sign": sign,
                    "t": t,
                    "uuid": uuid,
                }

            # 发送真实 HTTP 请求
            api_url = self._config.get("api", {}).get("base_url", "https://api.m.jd.com/api")
            headers = self._anti_detect.build_headers() if self._anti_detect else {}
            headers["Referer"] = "https://search.jd.com/"
            headers["Origin"] = "https://search.jd.com"
            cookies = self._cookie_manager.get_all_cookies() if self._cookie_manager else {}

            import urllib.parse
            url_with_params = f"{api_url}?{urllib.parse.urlencode(params)}"

            resp = self._tls_client.get(
                url_with_params,
                headers=headers,
                cookies=cookies,
            )

            status_code = resp.status_code
            resp_body = resp.text

            # 解析响应判断成功/失败
            is_success = status_code == 200
            error_type = None

            if not is_success:
                if status_code == 403:
                    error_type = "ip_banned"
                elif status_code == 429:
                    error_type = "rate_limited"
                elif status_code >= 500:
                    error_type = "server_error"
                else:
                    error_type = f"http_{status_code}"

            # 检查响应体中的错误码
            if is_success:
                try:
                    resp_json = resp.json()
                    code = resp_json.get("code")
                    if code and code != 0:
                        is_success = False
                        msg = resp_json.get("msg", "")
                        if "验证码" in msg or "滑块" in msg:
                            error_type = "captcha"
                        elif "Cookie" in msg or "登录" in msg:
                            error_type = "cookie_expired"
                        else:
                            error_type = "api_error"
                except Exception:
                    pass

            if is_success:
                self.state.success_requests += 1
                if self._monitor:
                    self._monitor.record_sign_result(True)

                result = {
                    "phase": "collection",
                    "status": "success",
                    "function_id": function_id,
                    "params_count": len(params),
                    "sign": sign,
                    "timestamp": t,
                    "strategy": self.state.sign_strategy or "local_sign",
                    "response": {
                        "status_code": status_code,
                        "body": resp_body[:2000],  # 截断避免过大
                    },
                }

                logger.info(f"采集成功: {function_id}")
                return result
            else:
                self.state.failed_requests += 1
                self.state.errors.append(f"{error_type}: {resp_body[:200]}")

                if self._monitor:
                    self._monitor.record_sign_result(False)

                logger.warning(f"采集失败 [{error_type}]: {function_id}")
                return {
                    "phase": "collection",
                    "status": "error",
                    "function_id": function_id,
                    "error_type": error_type,
                    "error": resp_body[:500],
                    "response": {
                        "status_code": status_code,
                        "body": resp_body[:2000],
                        "headers": dict(resp.headers),
                    },
                }

        except Exception as e:
            self.state.failed_requests += 1
            self.state.errors.append(str(e))

            if self._monitor:
                self._monitor.record_sign_result(False)

            logger.error(f"采集异常: {function_id} → {e}")
            return {
                "phase": "collection",
                "status": "error",
                "function_id": function_id,
                "error_type": "exception",
                "error": str(e),
            }

    # ============================================================
    # Phase 5+: 自进化采集
    # ============================================================

    def collect_with_evolution(
        self,
        function_id: str,
        body: Optional[Dict] = None,
        simulated_response: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        带自进化能力的数据采集

        当采集失败时，自动触发进化闭环：
        检测反爬类型 → 选择适应策略 → 重试验证 → 经验学习

        Args:
            function_id: API functionId
            body: 业务参数
            simulated_response: 模拟的失败响应（用于测试）

        Returns:
            采集结果（含进化报告）
        """
        # 先尝试普通采集
        result = self.collect(function_id, body)

        if result["status"] == "success":
            result["evolution"] = {"triggered": False}
            return result

        # 采集失败，触发进化
        if not self._evolution_engine:
            result["evolution"] = {"triggered": False, "reason": "engine_not_initialized"}
            return result

        logger.info(f"[自进化] 采集失败，启动进化闭环: {function_id}")

        # 使用真实响应数据（来自 collect() 返回的 response）
        failure_response = result.get("response", {}) or {
            "status_code": 403,
            "body": result.get("error", "unknown error"),
            "headers": {},
        }

        # 设置重试回调
        def retry_callback(headers, params):
            """重试回调：用新策略重新采集"""
            retry_result = self.collect(function_id, body)
            return {
                "success": retry_result["status"] == "success",
                "status_code": 200 if retry_result["status"] == "success" else 403,
                "body": retry_result,
            }

        self._evolution_engine.set_retry_callback(retry_callback)

        # 执行带重试的进化
        evolution_result, attempts = self._evolution_engine.evolve_with_retries(
            response_data=failure_response,
            original_headers={},
            original_params={"functionId": function_id, "body": body or {}},
        )

        # 更新智能体状态
        self.state.evolution_generation = self._evolution_engine.generation
        self.state.evolution_count += 1
        self.state.last_evolution_type = evolution_result.detected_type.value

        result["evolution"] = {
            "triggered": True,
            "result": evolution_result.to_dict(),
            "attempts": len(attempts),
            "dashboard": self._evolution_engine.get_evolution_dashboard(),
        }

        if evolution_result.retry_success:
            self.state.success_requests += 1
            logger.info(
                f"[自进化] ✓ 进化成功: {function_id} "
                f"(策略: {evolution_result.strategy_used}, "
                f"代数: {evolution_result.generation})"
            )
        else:
            logger.warning(
                f"[自进化] ✗ 进化失败: {function_id} "
                f"({len(attempts)} 次尝试均失败)"
            )

        return result

    def get_evolution_dashboard(self) -> Dict[str, Any]:
        """获取自进化引擎仪表盘"""
        if not self._evolution_engine:
            return {"error": "evolution engine not initialized"}
        return self._evolution_engine.get_evolution_dashboard()

    # ============================================================
    # Phase 6: 监控仪表盘
    # ============================================================

    def get_dashboard(self) -> Dict[str, Any]:
        """
        Phase 6: 获取监控仪表盘

        Returns:
            综合仪表盘数据
        """
        self.state.phase = AgentPhase.MONITORING

        dashboard = {
            "agent": self.state.to_dict(),
            "monitor": self._monitor.get_dashboard() if self._monitor else None,
        }

        return dashboard

    # ============================================================
    # 全流程编排
    # ============================================================

    def run_full_pipeline(
        self,
        function_id: str = "bizSearchCategoryList",
        body: Optional[Dict] = None,
        h5st_samples: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        运行完整 6 阶段流水线

        Args:
            function_id: 目标 functionId
            body: 业务参数
            h5st_samples: h5st 样本列表

        Returns:
            全流程结果
        """
        results: Dict[str, Any] = {"pipeline": []}

        # Phase 1: 环境诊断
        logger.info("=" * 50)
        logger.info("Phase 1: 环境诊断")
        diagnosis = self.diagnose_environment()
        results["pipeline"].append({"phase": 1, "result": diagnosis})

        # Phase 2: 服务启动
        logger.info("Phase 2: 服务启动")
        startup = self.start_services()
        results["pipeline"].append({"phase": 2, "result": startup})

        # Phase 4: 策略选型（跳过 Phase 3 嗅探，因无实时流量）
        logger.info("Phase 4: 签名策略选型")
        strategy = self.select_strategy(h5st_samples)
        results["pipeline"].append({"phase": 4, "result": strategy})

        # Phase 5: 数据采集
        logger.info("Phase 5: 数据采集")
        collection = self.collect(function_id, body)
        results["pipeline"].append({"phase": 5, "result": collection})

        # Phase 6: 监控仪表盘
        logger.info("Phase 6: 监控仪表盘")
        dashboard = self.get_dashboard()
        results["pipeline"].append({"phase": 6, "result": dashboard})

        self.state.phase = AgentPhase.COMPLETED
        results["summary"] = self.state.to_dict()

        return results


# ============================================================
# CLI 入口
# ============================================================


def main():
    """智能体 CLI"""
    import argparse

    parser = argparse.ArgumentParser(
        description="AI+JS逆向京东工业网数据采集智能体",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
命令:
  diagnose     环境诊断
  start        启动服务
  strategy     签名策略选型
  collect      数据采集
  evolve       自进化采集（失败时自动触发进化闭环）
  dashboard    监控仪表盘
  evolution    进化引擎仪表盘
  pipeline     完整流水线

示例:
  python agent.py diagnose
  python agent.py pipeline --function-id bizSearchCategoryList
  python agent.py collect --function-id searchWareBusiness
  python agent.py evolve --function-id bizSearchCategoryList
  python agent.py evolution
        """,
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("diagnose", help="环境诊断")
    subparsers.add_parser("start", help="启动服务")
    subparsers.add_parser("dashboard", help="监控仪表盘")
    subparsers.add_parser("evolution", help="进化引擎仪表盘")

    strategy_parser = subparsers.add_parser("strategy", help="签名策略选型")
    strategy_parser.add_argument("--samples", nargs="*", help="h5st 样本列表")

    collect_parser = subparsers.add_parser("collect", help="数据采集")
    collect_parser.add_argument("--function-id", required=True, help="API functionId")
    collect_parser.add_argument("--body", type=json.loads, default=None, help="业务参数 JSON")

    evolve_parser = subparsers.add_parser("evolve", help="自进化采集")
    evolve_parser.add_argument("--function-id", required=True, help="API functionId")
    evolve_parser.add_argument("--body", type=json.loads, default=None, help="业务参数 JSON")
    evolve_parser.add_argument("--simulate-failure", action="store_true", help="模拟反爬失败场景")

    pipeline_parser = subparsers.add_parser("pipeline", help="完整流水线")
    pipeline_parser.add_argument("--function-id", default="bizSearchCategoryList", help="目标 functionId")
    pipeline_parser.add_argument("--body", type=json.loads, default=None, help="业务参数 JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    agent = JDAgent()

    print("=" * 60)
    print("  AI+JS逆向京东工业网数据采集智能体 v2.0")
    print("=" * 60)

    if args.command == "diagnose":
        result = agent.diagnose_environment()
        print(f"\n环境就绪: {'✓' if result['ready'] else '✗'}")
        for check in result["checks"]:
            status_icon = "✓" if check.get("status") == "ok" else "✗"
            print(f"  {status_icon} {check['name']}: {check.get('value', check.get('status', ''))}")

    elif args.command == "start":
        result = agent.start_services()
        print(f"\n服务启动报告:")
        for svc in result["services"]:
            status_icon = "✓" if svc.get("status") == "ok" else "✗"
            hint = f" ({svc['hint']})" if svc.get("hint") else ""
            print(f"  {status_icon} {svc['name']}: {svc['status']}{hint}")

    elif args.command == "strategy":
        result = agent.select_strategy(getattr(args, "samples", None))
        print(f"\n签名策略:")
        print(f"  版本: {result['detected_version']}")
        print(f"  策略: {result['recommended_strategy']}")
        print(f"  可靠性: {result['reliability']}")
        print(f"  说明: {result['description']}")

    elif args.command == "collect":
        agent.start_services()
        result = agent.collect(args.function_id, args.body)
        print(f"\n采集结果: {result['status']}")
        print(f"  functionId: {result['function_id']}")
        if result["status"] == "success":
            print(f"  sign: {result['sign']}")
            print(f"  策略: {result['strategy']}")

    elif args.command == "dashboard":
        agent.start_services()
        result = agent.get_dashboard()
        print(f"\n监控仪表盘:")
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    elif args.command == "pipeline":
        result = agent.run_full_pipeline(
            function_id=args.function_id,
            body=args.body,
        )
        print(f"\n流水线完成:")
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False))

    elif args.command == "evolve":
        agent.start_services()
        simulated = None
        if getattr(args, "simulate_failure", False):
            simulated = {
                "status_code": 403,
                "body": "访问频繁，请稍后再试",
                "headers": {},
            }
        result = agent.collect_with_evolution(
            args.function_id, args.body, simulated
        )
        print(f"\n自进化采集结果: {result['status']}")
        evo = result.get("evolution", {})
        if evo.get("triggered"):
            er = evo.get("result", {})
            print(f"  反爬类型: {er.get('detected_type', 'unknown')}")
            print(f"  采用策略: {er.get('strategy_used', 'none')}")
            print(f"  进化结果: {'✓ 成功' if er.get('retry_success') else '✗ 失败'}")
            print(f"  尝试次数: {evo.get('attempts', 0)}")
            print(f"  当前代数: {er.get('generation', 0)}")
        else:
            print("  未触发进化（采集成功或引擎未初始化）")

    elif args.command == "evolution":
        agent.start_services()
        dashboard = agent.get_evolution_dashboard()
        print(f"\n进化引擎仪表盘:")
        print(json.dumps(dashboard, indent=2, ensure_ascii=False, default=str))

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
