"""
设备指纹生成与管理模块

负责生成和管理浏览器设备指纹，包括 UUID、Canvas/WebGL 指纹参数等。
"""

from __future__ import annotations

import hashlib
import random
import uuid
from typing import Dict, List, Optional

from .models import BrowserFingerprint
from .utils import setup_logger

logger = setup_logger(__name__)

# 常见 User-Agent 列表（按平台分类）
USER_AGENTS_IOS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

USER_AGENTS_ANDROID = [
    "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36",
]

USER_AGENTS_DESKTOP = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
]

# WebGL 厂商与渲染器组合
WEBGL_PROFILES = [
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce GTX 1080 Direct3D11 vs_5_0 ps_5_0)", "Win32"),
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)", "Win32"),
    ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)", "Win32"),
    ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0)", "Win32"),
    ("Apple", "Apple GPU", "MacIntel"),
]


class FingerprintGenerator:
    """设备指纹生成器"""

    def __init__(self, platform: str = "mobile"):
        """
        初始化指纹生成器

        Args:
            platform: 平台类型 ("mobile" | "desktop" | "ios" | "android")
        """
        self.platform = platform
        self._cached_uuid: Optional[str] = None

    def generate_uuid(self) -> str:
        """
        生成京东设备 UUID（32位十六进制，无连字符）

        Returns:
            32位 UUID 字符串
        """
        raw_uuid = uuid.uuid4()
        clean_uuid = raw_uuid.hex  # 32位十六进制，无连字符
        logger.debug(f"生成 UUID: {clean_uuid}")
        return clean_uuid

    def get_or_create_uuid(self) -> str:
        """获取缓存的 UUID 或生成新的"""
        if self._cached_uuid is None:
            self._cached_uuid = self.generate_uuid()
        return self._cached_uuid

    def set_uuid(self, uuid_str: str) -> None:
        """手动设置 UUID"""
        if len(uuid_str) != 32:
            raise ValueError("UUID 必须为 32 位十六进制字符串")
        self._cached_uuid = uuid_str

    def generate_fingerprint(self) -> BrowserFingerprint:
        """
        生成完整的浏览器指纹

        Returns:
            BrowserFingerprint 对象
        """
        # 根据平台选择 UA
        if self.platform == "ios":
            ua = random.choice(USER_AGENTS_IOS)
            platform_str = "iPhone"
            screen_w, screen_h = 375, 812
            pixel_ratio = 3.0
        elif self.platform == "android":
            ua = random.choice(USER_AGENTS_ANDROID)
            platform_str = "Linux armv8l"
            screen_w, screen_h = 360, 800
            pixel_ratio = 3.0
        elif self.platform == "desktop":
            ua = random.choice(USER_AGENTS_DESKTOP)
            webgl_profile = random.choice(WEBGL_PROFILES)
            platform_str = webgl_profile[2]
            screen_w, screen_h = 1920, 1080
            pixel_ratio = 1.0
        else:  # mobile (default)
            ua = random.choice(USER_AGENTS_IOS)
            platform_str = "iPhone"
            screen_w, screen_h = 375, 812
            pixel_ratio = 3.0

        # WebGL 指纹
        if self.platform == "desktop":
            webgl_profile = random.choice(WEBGL_PROFILES)
            webgl_vendor = webgl_profile[0]
            webgl_renderer = webgl_profile[1]
        else:
            webgl_vendor = "Apple"
            webgl_renderer = "Apple GPU"

        # Canvas 指纹（模拟哈希）
        canvas_hash = self._generate_canvas_hash()

        fingerprint = BrowserFingerprint(
            user_agent=ua,
            platform=platform_str,
            language="zh-CN",
            languages=["zh-CN", "zh", "en"],
            hardware_concurrency=random.choice([4, 6, 8, 12]),
            device_memory=random.choice([4, 8, 16]),
            screen_width=screen_w,
            screen_height=screen_h,
            color_depth=24,
            pixel_ratio=pixel_ratio,
            timezone="Asia/Shanghai",
            canvas_hash=canvas_hash,
            webgl_vendor=webgl_vendor,
            webgl_renderer=webgl_renderer,
        )

        logger.debug(f"生成指纹: platform={platform_str}, ua={ua[:50]}...")
        return fingerprint

    def _generate_canvas_hash(self) -> str:
        """生成模拟的 Canvas 指纹哈希"""
        # 模拟 Canvas 渲染结果的哈希
        random_seed = random.random()
        hash_input = f"canvas_{random_seed}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]

    def generate_stealth_script(self) -> str:
        """
        生成用于 Playwright 的反检测注入脚本

        Returns:
            JavaScript 代码字符串
        """
        fp = self.generate_fingerprint()

        script = f"""
        () => {{
            // 覆盖 navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {{
                get: () => undefined
            }});

            // 覆盖 navigator.plugins
            Object.defineProperty(navigator, 'plugins', {{
                get: () => [1, 2, 3, 4, 5]
            }});

            // 覆盖 navigator.languages
            Object.defineProperty(navigator, 'languages', {{
                get: () => {fp.languages}
            }});

            // 注入 window.chrome
            window.chrome = {{
                runtime: {{}},
                loadTimes: function() {{}},
                csi: function() {{}},
            }};

            // 覆盖 navigator.platform
            Object.defineProperty(navigator, 'platform', {{
                get: () => '{fp.platform}'
            }});

            // 覆盖 navigator.hardwareConcurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {{
                get: () => {fp.hardware_concurrency}
            }});

            // 覆盖 screen 属性
            Object.defineProperty(screen, 'width', {{ get: () => {fp.screen_width} }});
            Object.defineProperty(screen, 'height', {{ get: () => {fp.screen_height} }});
            Object.defineProperty(screen, 'colorDepth', {{ get: () => {fp.color_depth} }});
        }}
        """
        return script

    def to_playwright_context_options(self) -> Dict:
        """
        转换为 Playwright BrowserContext 配置选项

        Returns:
            Playwright context 配置字典
        """
        fp = self.generate_fingerprint()

        return {
            "user_agent": fp.user_agent,
            "viewport": {
                "width": fp.screen_width,
                "height": fp.screen_height,
            },
            "locale": fp.language,
            "timezone_id": fp.timezone,
            "device_scale_factor": fp.pixel_ratio,
            "is_mobile": self.platform in ("mobile", "ios", "android"),
            "has_touch": self.platform in ("mobile", "ios", "android"),
            "color_scheme": "light",
        }
