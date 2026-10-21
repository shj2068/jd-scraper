"""
京东工业招商网数据采集工具库 (jd-scraper)

基于 JSRPC 架构的京东 API 数据采集工具，用于技术学习与研究。

合规警示：本工具仅用于技术学习与研究目的，未经授权批量采集可能违反相关法律法规。

v2.0 新增模块：
- h5st_parser: h5st 签名结构解析与版本检测
- monitor: 生产环境监控（签名失败率/Cookie 过期/IP 封禁）
- api_sniffer: MCP 智能 API 嗅探器

v2.1 新增模块（自进化系统）：
- evolution_engine: 反爬自进化引擎（Detect→Classify→Adapt→Validate→Learn）
- strategy_pool: 策略池与 Thompson Sampling 多臂赌博机选型
- request_mutator: 请求变异器（Header/Timing/Fingerprint/Param 四维度）
- experience_store: 经验记忆存储（跨会话学习）
"""

__version__ = "2.1.0"
__author__ = "jd-scraper"

from .models import SignParams, JDRequest, SignResponse, CookieJar
from .sign import generate_sign
from .request_builder import RequestBuilder
from .jsrpc_client import JSRPCClient
from .cookie_manager import CookieManager
from .fingerprint import FingerprintGenerator
from .anti_detect import AntiDetect
from .h5st_parser import (
    H5stVersion,
    SignStrategy,
    H5stStructure,
    parse_h5st,
    detect_version_from_samples,
    validate_h5st_freshness,
    get_strategy_recommendation,
)
from .monitor import ProductionMonitor, MonitorConfig, AlertLevel, AlertEvent
from .api_sniffer import APISniffer, DiscoveredAPI, SniffResult, ParamType
from .evolution_engine import (
    EvolutionEngine,
    EvolutionConfig,
    EvolutionResult,
    EvolutionPhase,
)
from .strategy_pool import StrategyPool, StrategyVariant
from .request_mutator import RequestMutator
from .experience_store import (
    ExperienceStore,
    Experience,
    AntiCrawlType,
    TriggerSnapshot,
    StrategyRecord,
    OutcomeRecord,
)

__all__ = [
    # 核心模型
    "SignParams",
    "JDRequest",
    "SignResponse",
    "CookieJar",
    # 核心引擎
    "generate_sign",
    "RequestBuilder",
    "JSRPCClient",
    "CookieManager",
    "FingerprintGenerator",
    "AntiDetect",
    # h5st 解析器 (v2.0)
    "H5stVersion",
    "SignStrategy",
    "H5stStructure",
    "parse_h5st",
    "detect_version_from_samples",
    "validate_h5st_freshness",
    "get_strategy_recommendation",
    # 生产监控 (v2.0)
    "ProductionMonitor",
    "MonitorConfig",
    "AlertLevel",
    "AlertEvent",
    # API 嗅探器 (v2.0)
    "APISniffer",
    "DiscoveredAPI",
    "SniffResult",
    "ParamType",
    # 自进化系统 (v2.1)
    "EvolutionEngine",
    "EvolutionConfig",
    "EvolutionResult",
    "EvolutionPhase",
    "StrategyPool",
    "StrategyVariant",
    "RequestMutator",
    "ExperienceStore",
    "Experience",
    "AntiCrawlType",
    "TriggerSnapshot",
    "StrategyRecord",
    "OutcomeRecord",
]
