"""
验证码逆向与反爬对抗工具包

模块：
- slider_trajectory: 滑块轨迹生成引擎（四阶段物理模型）
- fingerprint_analyzer: 浏览器指纹分析与一致性校验
- js_deobfuscator: JS 代码混淆反混淆引擎
"""

from .slider_trajectory import (
    SliderTrajectoryEngine,
    TrajectoryConfig,
    TrackPoint,
    BezierTrajectoryGenerator,
)
from .fingerprint_analyzer import (
    FingerprintVector,
    FingerprintConsistencyChecker,
    TLSFingerprintAnalyzer,
)
from .js_deobfuscator import (
    JSDeobfuscator,
    DeobfuscationResult,
    StringDecryptor,
    DeadCodeRemover,
    ControlFlowAnalyzer,
    AntiDebugRemover,
)

__all__ = [
    "SliderTrajectoryEngine",
    "TrajectoryConfig",
    "TrackPoint",
    "BezierTrajectoryGenerator",
    "FingerprintVector",
    "FingerprintConsistencyChecker",
    "TLSFingerprintAnalyzer",
    "JSDeobfuscator",
    "DeobfuscationResult",
    "StringDecryptor",
    "DeadCodeRemover",
    "ControlFlowAnalyzer",
    "AntiDebugRemover",
]
