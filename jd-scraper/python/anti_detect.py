"""
反检测工具模块

提供 User-Agent 轮换、请求头标准化、请求间隔随机化等反检测功能。

v2.0 增强（文档第四章 4.2 节）：
- Sec-CH-UA 版本与 UA 字符串自动一致性校验
- Sec-CH-UA-Platform 与 UA 平台信息匹配
- Sec-Fetch-* 头完整模拟
"""

from __future__ import annotations

import random
import re
import time
from typing import Dict, List, Optional, Tuple

from .utils import setup_logger

logger = setup_logger(__name__)

# 标准请求头模板
STANDARD_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "X-Requested-With": "XMLHttpRequest",
}

# Referer/Origin 模板
JD_REFERER_TEMPLATES = [
    "https://zhaoshang.jd.com/",
    "https://zhaoshang.jd.com/category-h5/",
    "https://zhaoshang.jd.com/category-h5/list",
]

JD_ORIGIN = "https://zhaoshang.jd.com"


class AntiDetect:
    """反检测工具类"""

    def __init__(
        self,
        ua_pool: Optional[List[str]] = None,
        random_delay_range: Tuple[float, float] = (1.0, 5.0),
        enable_ua_rotation: bool = True,
    ):
        """
        初始化反检测工具

        Args:
            ua_pool: 自定义 User-Agent 池（为空则使用内置池）
            random_delay_range: 请求间隔随机范围 (min, max) 秒
            enable_ua_rotation: 是否启用 UA 轮换
        """
        self.ua_pool = ua_pool or self._default_ua_pool()
        self.random_delay_range = random_delay_range
        self.enable_ua_rotation = enable_ua_rotation
        self._current_ua_index = 0

    def _default_ua_pool(self) -> List[str]:
        """默认 User-Agent 池（多平台混合）"""
        return [
            # iOS Safari
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
            # Android Chrome
            "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36",
            # Desktop Chrome
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        ]

    def get_user_agent(self) -> str:
        """
        获取 User-Agent（支持轮换）

        Returns:
            User-Agent 字符串
        """
        if not self.enable_ua_rotation:
            return self.ua_pool[0]

        ua = self.ua_pool[self._current_ua_index]
        self._current_ua_index = (self._current_ua_index + 1) % len(
            self.ua_pool
        )
        return ua

    def get_random_user_agent(self) -> str:
        """随机获取 User-Agent"""
        return random.choice(self.ua_pool)

    def build_headers(
        self,
        referer: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        include_cookie: bool = True,
    ) -> Dict[str, str]:
        """
        构建标准化请求头

        Args:
            referer: 自定义 Referer（为空则随机选择）
            extra_headers: 额外请求头
            include_cookie: 是否包含 Cookie 相关头

        Returns:
            请求头字典
        """
        headers = STANDARD_HEADERS.copy()

        # User-Agent
        headers["User-Agent"] = self.get_user_agent()

        # Referer / Origin
        if referer is None:
            referer = random.choice(JD_REFERER_TEMPLATES)
        headers["Referer"] = referer
        headers["Origin"] = JD_ORIGIN

        # 合并额外请求头
        if extra_headers:
            headers.update(extra_headers)

        logger.debug(f"构建请求头: UA={headers['User-Agent'][:50]}...")
        return headers

    def build_stealth_headers(self) -> Dict[str, str]:
        """
        构建隐身请求头（模拟真实浏览器完整头）

        v2.0: Sec-CH-UA 版本与 UA 字符串自动一致性（文档第四章 4.2 节）

        Returns:
            完整请求头字典
        """
        headers = self.build_headers()

        # 从当前 UA 动态提取 Chrome 版本，生成匹配的 Sec-CH-UA
        ua = headers.get("User-Agent", "")
        sec_ch_ua, sec_ch_ua_mobile, sec_ch_ua_platform = self._build_sec_ch_ua(ua)

        # 添加完整浏览器特征头
        headers.update(
            {
                "Sec-Ch-Ua": sec_ch_ua,
                "Sec-Ch-Ua-Mobile": sec_ch_ua_mobile,
                "Sec-Ch-Ua-Platform": sec_ch_ua_platform,
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }
        )

        return headers

    def _build_sec_ch_ua(self, user_agent: str) -> Tuple[str, str, str]:
        """
        从 User-Agent 字符串动态提取并生成匹配的 Sec-CH-UA 头

        文档第四章 4.2 节：Sec-CH-UA 版本必须与 UA 中的 Chrome 版本一致，
        否则会被京东风控识别为异常请求。

        Args:
            user_agent: User-Agent 字符串

        Returns:
            (Sec-CH-UA, Sec-CH-UA-Mobile, Sec-CH-UA-Platform) 三元组
        """
        # 提取 Chrome 主版本号
        chrome_match = re.search(r"Chrome/(\d+)", user_agent)
        chrome_version = chrome_match.group(1) if chrome_match else "118"

        # 判断是否为移动端
        is_mobile = "Mobile" in user_agent or "Android" in user_agent
        is_ios = "iPhone" in user_agent or "iPad" in user_agent

        # 判断平台
        if is_ios:
            platform = '"iOS"'
        elif "Android" in user_agent:
            platform = '"Android"'
        elif "Windows" in user_agent:
            platform = '"Windows"'
        elif "Macintosh" in user_agent or "Mac OS X" in user_agent:
            platform = '"macOS"'
        elif "Linux" in user_agent:
            platform = '"Linux"'
        else:
            platform = '"Windows"'

        # 构建 Sec-CH-UA（包含 Chromium 和 Chrome 两个品牌）
        sec_ch_ua = f'"Chromium";v="{chrome_version}", "Google Chrome";v="{chrome_version}", "Not=A?Brand";v="99"'

        # Sec-CH-UA-Mobile
        sec_ch_ua_mobile = "?1" if is_mobile else "?0"

        logger.debug(
            f"Sec-CH-UA 一致性: Chrome/{chrome_version}, "
            f"platform={platform}, mobile={sec_ch_ua_mobile}"
        )

        return sec_ch_ua, sec_ch_ua_mobile, platform

    def validate_sec_ch_ua_consistency(self, user_agent: str, sec_ch_ua: str) -> bool:
        """
        校验 Sec-CH-UA 与 UA 的版本一致性

        Args:
            user_agent: User-Agent 字符串
            sec_ch_ua: Sec-CH-UA 头字符串

        Returns:
            是否一致
        """
        ua_match = re.search(r"Chrome/(\d+)", user_agent)
        if not ua_match:
            return True  # 非 Chrome UA，跳过校验

        ua_version = ua_match.group(1)

        # 检查 Sec-CH-UA 中是否包含相同版本
        return f'v="{ua_version}"' in sec_ch_ua

    def random_delay(self) -> float:
        """
        执行随机延迟

        Returns:
            实际延迟秒数
        """
        delay = random.uniform(
            self.random_delay_range[0], self.random_delay_range[1]
        )
        logger.debug(f"随机延迟: {delay:.2f}s")
        time.sleep(delay)
        return delay

    def simulate_human_timing(self) -> None:
        """模拟人类操作时序（包含短停顿和长停顿）"""
        # 70% 概率短停顿 (0.5-2s)，30% 概率长停顿 (2-5s)
        if random.random() < 0.7:
            delay = random.uniform(0.5, 2.0)
        else:
            delay = random.uniform(2.0, self.random_delay_range[1])

        time.sleep(delay)
        logger.debug(f"人类时序模拟: {delay:.2f}s")

    def add_jitter(self, value: float, jitter_range: float = 0.1) -> float:
        """
        为数值添加微小抖动（模拟测量误差）

        Args:
            value: 原始值
            jitter_range: 抖动范围（百分比）

        Returns:
            抖动后的值
        """
        jitter = value * jitter_range
        return value + random.uniform(-jitter, jitter)

    @staticmethod
    def is_valid_referer(referer: str) -> bool:
        """验证 Referer 是否为京东域名"""
        jd_domains = [
            "jd.com",
            "jd.cn",
            "360buy.com",
            "jdcloud.com",
        ]
        return any(domain in referer for domain in jd_domains)
