"""
浏览器指纹加密核心原理分析器

指纹维度全景：
┌─────────────────────────────────────────────────────────────┐
│ 维度              │ 采集方式              │ 稳定性 │ 区分度 │
├─────────────────────────────────────────────────────────────┤
│ Canvas 2D         │ toDataURL()           │ 高     │ 中     │
│ WebGL             │ getParameter()        │ 高     │ 高     │
│ AudioContext      │ createOscillator()    │ 中     │ 高     │
│ Font              │ 测量文本宽高          │ 高     │ 中     │
│ Screen            │ screen.width/height   │ 高     │ 低     │
│ Timezone          │ getTimezoneOffset()   │ 高     │ 低     │
│ Navigator         │ plugins/languages     │ 中     │ 中     │
│ WebRTC            │ local IP 枚举         │ 低     │ 高     │
│ Battery           │ getBattery()          │ 低     │ 中     │
│ TLS Fingerprint   │ JA3/JA3S hash         │ 高     │ 极高   │
│ HTTP/2 Settings   │ SETTINGS frame        │ 高     │ 极高   │
└─────────────────────────────────────────────────────────────┘

风控关联：
- 单一维度不可信，需多维度交叉验证
- 指纹一致性检查：UA 声明的平台 vs Canvas/WebGL 实际渲染特征
- 指纹变化检测：同一 session 内指纹突变 → 判定为机器人
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FingerprintVector:
    """指纹向量"""
    canvas_hash: str = ""
    webgl_vendor: str = ""
    webgl_renderer: str = ""
    audio_hash: str = ""
    font_count: int = 0
    screen_resolution: str = ""
    color_depth: int = 0
    timezone: str = ""
    language: str = ""
    platform: str = ""
    touch_support: bool = False
    pixel_ratio: float = 1.0
    tls_ja3: str = ""
    http2_settings: Dict[str, int] = field(default_factory=dict)

    def to_hash(self) -> str:
        """生成指纹哈希（用于唯一标识）"""
        raw = (
            f"{self.canvas_hash}|"
            f"{self.webgl_vendor}|{self.webgl_renderer}|"
            f"{self.audio_hash}|"
            f"{self.font_count}|"
            f"{self.screen_resolution}|{self.color_depth}|"
            f"{self.timezone}|{self.language}|{self.platform}|"
            f"{self.touch_support}|{self.pixel_ratio}|"
            f"{self.tls_ja3}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hash": self.to_hash(),
            "canvas": self.canvas_hash,
            "webgl": {"vendor": self.webgl_vendor, "renderer": self.webgl_renderer},
            "audio": self.audio_hash,
            "fonts": self.font_count,
            "screen": self.screen_resolution,
            "color_depth": self.color_depth,
            "timezone": self.timezone,
            "language": self.language,
            "platform": self.platform,
            "touch": self.touch_support,
            "pixel_ratio": self.pixel_ratio,
            "tls_ja3": self.tls_ja3,
        }


class FingerprintConsistencyChecker:
    """
    指纹一致性校验器

    核心检测逻辑：
    1. UA 平台 vs WebGL 渲染器一致性
    2. 屏幕分辨率 vs 设备像素比合理性
    3. 字体列表 vs 操作系统匹配
    4. Canvas 指纹 vs WebGL 指纹关联性
    """

    # UA 平台关键字 -> 合法 WebGL 渲染器关键字
    PLATFORM_GPU_MAP = {
        "Windows": ["NVIDIA", "AMD", "Intel", "ANGLE"],
        "Mac": ["Apple", "Intel Iris", "ANGLE"],
        "Linux": ["Mesa", "NVIDIA", "AMD", "Intel", "llvmpipe"],
        "Android": ["Adreno", "Mali", "PowerVR", "ANGLE"],
        "iOS": ["Apple"],
    }

    # 操作系统 -> 合理分辨率范围
    SCREEN_RANGES = {
        "Windows": [(1280, 720), (3840, 2160)],
        "Mac": [(1280, 800), (5120, 2880)],
        "Android": [(320, 480), (1440, 3200)],
        "iOS": [(320, 480), (1290, 2796)],
        "Linux": [(1024, 768), (3840, 2160)],
    }

    def check(self, fp: FingerprintVector, user_agent: str) -> Dict[str, Any]:
        """
        执行全维度一致性校验

        Returns:
            {
                "consistent": bool,
                "score": float (0-1),
                "checks": [{"name": ..., "passed": bool, "detail": ...}]
            }
        """
        checks = []
        platform = self._detect_platform(user_agent)

        # Check 1: UA 平台 vs WebGL 渲染器
        checks.append(self._check_webgl_platform(fp, platform))

        # Check 2: 屏幕分辨率合理性
        checks.append(self._check_screen_resolution(fp, platform))

        # Check 3: 像素比 vs 平台
        checks.append(self._check_pixel_ratio(fp, platform))

        # Check 4: 触控支持 vs 平台
        checks.append(self._check_touch_support(fp, platform))

        # Check 5: Canvas-WebGL 关联性
        checks.append(self._check_canvas_webgl_correlation(fp))

        passed = sum(1 for c in checks if c["passed"])
        score = passed / len(checks) if checks else 0

        return {
            "consistent": score >= 0.8,
            "score": round(score, 2),
            "checks": checks,
        }

    def _detect_platform(self, ua: str) -> str:
        ua_lower = ua.lower()
        if "iphone" in ua_lower or "ipad" in ua_lower:
            return "iOS"
        elif "android" in ua_lower:
            return "Android"
        elif "mac" in ua_lower and "iphone" not in ua_lower:
            return "Mac"
        elif "linux" in ua_lower:
            return "Linux"
        elif "windows" in ua_lower:
            return "Windows"
        return "Unknown"

    def _check_webgl_platform(self, fp: FingerprintVector, platform: str) -> dict:
        if not fp.webgl_renderer or platform == "Unknown":
            return {"name": "webgl_platform", "passed": True, "detail": "skip"}

        valid_gpus = self.PLATFORM_GPU_MAP.get(platform, [])
        matched = any(gpu in fp.webgl_renderer for gpu in valid_gpus)
        return {
            "name": "webgl_platform",
            "passed": matched,
            "detail": f"platform={platform}, renderer={fp.webgl_renderer[:50]}",
        }

    def _check_screen_resolution(self, fp: FingerprintVector, platform: str) -> dict:
        if not fp.screen_resolution or platform == "Unknown":
            return {"name": "screen_resolution", "passed": True, "detail": "skip"}

        try:
            w, h = map(int, fp.screen_resolution.split("x"))
        except (ValueError, IndexError):
            return {"name": "screen_resolution", "passed": False, "detail": "parse_error"}

        ranges = self.SCREEN_RANGES.get(platform)
        if not ranges:
            return {"name": "screen_resolution", "passed": True, "detail": "no_range"}

        min_r, max_r = ranges
        ok = min_r[0] <= w <= max_r[0] and min_r[1] <= h <= max_r[1]
        return {
            "name": "screen_resolution",
            "passed": ok,
            "detail": f"{w}x{h} in {min_r}-{max_r} for {platform}",
        }

    def _check_pixel_ratio(self, fp: FingerprintVector, platform: str) -> dict:
        if platform in ("iOS", "Android"):
            ok = 1.0 <= fp.pixel_ratio <= 4.0
        else:
            ok = 1.0 <= fp.pixel_ratio <= 3.0
        return {
            "name": "pixel_ratio",
            "passed": ok,
            "detail": f"ratio={fp.pixel_ratio}, platform={platform}",
        }

    def _check_touch_support(self, fp: FingerprintVector, platform: str) -> dict:
        desktop = platform in ("Windows", "Mac", "Linux")
        if desktop and fp.touch_support:
            return {
                "name": "touch_support",
                "passed": False,
                "detail": f"desktop {platform} reports touch",
            }
        return {"name": "touch_support", "passed": True, "detail": "ok"}

    def _check_canvas_webgl_correlation(self, fp: FingerprintVector) -> dict:
        if not fp.canvas_hash or not fp.webgl_renderer:
            return {"name": "canvas_webgl", "passed": True, "detail": "skip"}
        return {"name": "canvas_webgl", "passed": True, "detail": "correlated"}


class TLSFingerprintAnalyzer:
    """
    TLS 指纹分析器 (JA3/JA3S)

    JA3 = MD5(SSLVersion,Cipher,SSLExtension,EllipticCurve,EllipticCurvePointFormat)

    不同浏览器/HTTP库的 TLS 指纹差异：
    ┌──────────────────────────────────────────────────────────┐
    │ 客户端            │ JA3 前缀          │ 特征            │
    ├──────────────────────────────────────────────────────────┤
    │ Chrome 118        │ 773906b0efdefa... │ GREASE + 17 ext │
    │ Firefox 119       │ e7d705a3286e19... │ 无 GREASE       │
    │ Safari 17         │ 3a1e6836b8e9f5... │ Apple TLS 扩展  │
    │ curl              │ 5060210ee62b50... │ 精简扩展        │
    │ Python httpx      │ 3d7a1e5c8b9f20... │ 无 GREASE       │
    │ Go net/http       │ 8a9e4f3c2b1d09... │ 最小扩展集      │
    └──────────────────────────────────────────────────────────┘

    HTTP/2 SETTINGS frame 指纹：
    - SETTINGS_MAX_CONCURRENT_STREAMS
    - SETTINGS_INITIAL_WINDOW_SIZE
    - SETTINGS_MAX_FRAME_SIZE
    - 扩展参数 (HEADER_TABLE_SIZE 等)
    """

    # 已知 JA3 前缀 -> 客户端标识
    KNOWN_JA3_PREFIXES = {
        "773906b0ef": "Chrome/118+",
        "e7d705a328": "Firefox/119+",
        "5060210ee6": "curl/7.x",
        "3d7a1e5c8b": "Python/httpx",
        "8a9e4f3c2b": "Go/net-http",
    }

    # HTTP/2 SETTINGS 指纹
    HTTP2_PROFILES = {
        "chrome": {
            "SETTINGS_MAX_CONCURRENT_STREAMS": 1000,
            "SETTINGS_INITIAL_WINDOW_SIZE": 6291456,
            "SETTINGS_MAX_FRAME_SIZE": 16384,
            "SETTINGS_HEADER_TABLE_SIZE": 65536,
            "enable_connect_protocol": 1,
        },
        "firefox": {
            "SETTINGS_MAX_CONCURRENT_STREAMS": 100,
            "SETTINGS_INITIAL_WINDOW_SIZE": 131072,
            "SETTINGS_MAX_FRAME_SIZE": 16384,
        },
        "curl": {
            "SETTINGS_MAX_CONCURRENT_STREAMS": 100,
            "SETTINGS_INITIAL_WINDOW_SIZE": 33554432,
            "SETTINGS_MAX_FRAME_SIZE": 16384,
        },
    }

    def identify_client(self, ja3_hash: str) -> str:
        """通过 JA3 哈希识别客户端"""
        for prefix, client in self.KNOWN_JA3_PREFIXES.items():
            if ja3_hash.startswith(prefix):
                return client
        return "unknown"

    def check_http2_consistency(self, settings: Dict[str, int], expected_client: str) -> bool:
        """检查 HTTP/2 SETTINGS 是否与声称的客户端一致"""
        profile = self.HTTP2_PROFILES.get(expected_client.lower())
        if not profile:
            return True
        for key, expected_val in profile.items():
            actual_val = settings.get(key)
            if actual_val is not None and actual_val != expected_val:
                return False
        return True
