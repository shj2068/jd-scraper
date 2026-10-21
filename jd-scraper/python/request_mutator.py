"""
请求变异器模块

根据策略池选中的变体，对请求参数、请求头、时序进行变异，
实现反爬规避。每次请求前由进化引擎调用，
将多个维度的变异叠加应用到最终请求上。

变异维度:
1. Header Mutation: 请求头替换/增强/注入
2. Timing Mutation: 请求间隔/顺序变化
3. Fingerprint Mutation: 设备指纹切换
4. Param Mutation: 参数增删/重排/填充
"""

from __future__ import annotations

import hashlib
import json
import random
import string
import time
from typing import Any, Dict, List, Optional, Tuple

from .anti_detect import AntiDetect
from .fingerprint import FingerprintGenerator
from .strategy_pool import StrategyVariant
from .utils import setup_logger

logger = setup_logger(__name__)


class RequestMutator:
    """
    请求变异器

    接收策略变体，对请求的各个维度进行变异。
    """

    def __init__(
        self,
        anti_detect: Optional[AntiDetect] = None,
        fingerprint: Optional[FingerprintGenerator] = None,
    ):
        self.anti_detect = anti_detect or AntiDetect()
        self.fingerprint = fingerprint or FingerprintGenerator()
        self._session_fingerprint = None  # sticky 模式下的固定指纹
        self._request_count = 0
        self._adaptive_delay = 2.0  # adaptive timing 的当前延迟

    def apply_mutations(
        self,
        headers: Dict[str, str],
        params: Dict[str, Any],
        variants: Dict[str, StrategyVariant],
    ) -> Tuple[Dict[str, str], Dict[str, Any], float]:
        """
        叠加应用所有维度的变异

        Args:
            headers: 原始请求头
            params: 原始请求参数
            variants: {category: StrategyVariant} 各维度的策略变体

        Returns:
            (变异后请求头, 变异后参数, 建议延迟秒数)
        """
        self._request_count += 1
        delay = 0.0

        # 1. Header 变异
        header_variant = variants.get("header")
        if header_variant:
            headers = self._mutate_headers(headers, header_variant)

        # 2. Timing 变异
        timing_variant = variants.get("timing")
        if timing_variant:
            delay = self._compute_timing(timing_variant)

        # 3. Fingerprint 变异
        fp_variant = variants.get("fingerprint")
        if fp_variant:
            headers = self._mutate_fingerprint(headers, fp_variant)

        # 4. Param 变异
        param_variant = variants.get("param")
        if param_variant:
            params = self._mutate_params(params, param_variant)

        logger.debug(
            f"变异应用完成: "
            f"variants={list(variants.keys())}, delay={delay:.2f}s"
        )

        return headers, params, delay

    # ========== Header 变异 ==========

    def _mutate_headers(
        self, headers: Dict[str, str], variant: StrategyVariant
    ) -> Dict[str, str]:
        """请求头变异"""
        headers = headers.copy()
        preset = variant.params.get("preset", "chrome_windows")

        if preset == "chrome_windows":
            headers.update(self._chrome_windows_headers())
        elif preset == "chrome_android":
            headers.update(self._chrome_android_headers())
        elif preset == "safari_ios":
            headers.update(self._safari_ios_headers())

        # 是否添加 Sec-CH-UA
        if variant.params.get("sec_ch_ua", True):
            ua = headers.get("User-Agent", "")
            sec_ch_ua, mobile, platform = self.anti_detect._build_sec_ch_ua(ua)
            headers["Sec-Ch-Ua"] = sec_ch_ua
            headers["Sec-Ch-Ua-Mobile"] = mobile
            headers["Sec-Ch-Ua-Platform"] = platform

        # 是否添加 Sec-Fetch-*
        if variant.params.get("sec_fetch", True):
            headers.update({
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            })

        # 额外请求头
        extra = variant.params.get("extra_headers", {})
        if extra:
            headers.update(extra)

        # 随机注入噪声头（5% 概率）
        if random.random() < 0.05:
            headers[f"X-Noise-{random.randint(100, 999)}"] = (
                random.choice(string.ascii_lowercase) * 8
            )

        return headers

    def _chrome_windows_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/118.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def _chrome_android_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 14; Pixel 7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/118.0.0.0 Mobile Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    def _safari_ios_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.0 Mobile/15E148 Safari/604.1"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
        }

    # ========== Timing 变异 ==========

    def _compute_timing(self, variant: StrategyVariant) -> float:
        """计算请求延迟"""
        mode = variant.params.get("mode", "human")

        if mode == "human":
            # 70% 短停顿，30% 长停顿
            min_d = variant.params.get("min_delay", 1.0)
            max_d = variant.params.get("max_delay", 5.0)
            if random.random() < 0.7:
                return random.uniform(min_d, min_d + (max_d - min_d) * 0.3)
            else:
                return random.uniform(min_d + (max_d - min_d) * 0.3, max_d)

        elif mode == "slow":
            return random.uniform(
                variant.params.get("min_delay", 3.0),
                variant.params.get("max_delay", 10.0),
            )

        elif mode == "adaptive":
            # 指数退避 + 随机抖动
            base = variant.params.get("base_delay", 2.0)
            factor = variant.params.get("backoff_factor", 1.5)
            max_d = variant.params.get("max_delay", 30.0)

            # 连续失败时 _adaptive_delay 会增大
            delay = min(self._adaptive_delay + random.uniform(-0.5, 0.5), max_d)
            self._adaptive_delay = min(self._adaptive_delay * factor, max_d)
            return max(delay, base)

        return random.uniform(1.0, 5.0)

    def reset_adaptive_timing(self) -> None:
        """重置自适应时序（成功时调用）"""
        self._adaptive_delay = 2.0

    def increase_adaptive_timing(self) -> None:
        """增大自适应时序（失败时调用）"""
        self._adaptive_delay = min(self._adaptive_delay * 1.5, 30.0)

    # ========== Fingerprint 变异 ==========

    def _mutate_fingerprint(
        self, headers: Dict[str, str], variant: StrategyVariant
    ) -> Dict[str, str]:
        """指纹变异"""
        headers = headers.copy()
        mode = variant.params.get("mode", "rotate_per_request")

        if mode == "rotate_per_request":
            # 每次请求换指纹
            new_fp = self.fingerprint.generate_fingerprint()
            headers["User-Agent"] = new_fp.user_agent

            # Canvas 指纹抖动
            if variant.params.get("canvas_jitter", True):
                canvas_val = hashlib.md5(
                    f"{time.time()}_{random.random()}".encode()
                ).hexdigest()[:16]
                headers["X-Canvas-Hash"] = canvas_val

        elif mode == "sticky_session":
            # 会话内固定指纹
            if self._session_fingerprint is None:
                fp = self.fingerprint.generate_fingerprint()
                self._session_fingerprint = fp
            headers["User-Agent"] = self._session_fingerprint.user_agent

        return headers

    def rotate_session_fingerprint(self) -> None:
        """强制轮换会话指纹"""
        self._session_fingerprint = None
        logger.debug("会话指纹已轮换")

    # ========== Param 变异 ==========

    def _mutate_params(
        self, params: Dict[str, Any], variant: StrategyVariant
    ) -> Dict[str, Any]:
        """参数变异"""
        params = params.copy()

        # 控制 h5st 注入
        if not variant.params.get("include_h5st", True):
            params.pop("h5st", None)

        # 控制隐秘参数
        if not variant.params.get("include_eid", True):
            params.pop("x-api-eid", None)
        if not variant.params.get("include_request_id", True):
            params.pop("x-request-id", None)
        if not variant.params.get("include_rp_client", True):
            params.pop("x-rp-client", None)

        # 参数顺序随机化（对 dict 做 shuffle）
        if random.random() < 0.3:
            keys = list(params.keys())
            random.shuffle(keys)
            params = {k: params[k] for k in keys}

        # 注入噪声参数（10% 概率）
        if random.random() < 0.1:
            noise_key = f"_t{random.randint(100, 999)}"
            params[noise_key] = str(int(time.time() * 1000))

        return params

    # ========== 工具方法 ==========

    def get_stats(self) -> Dict[str, Any]:
        """获取变异器统计"""
        return {
            "total_requests": self._request_count,
            "adaptive_delay": round(self._adaptive_delay, 2),
            "session_fingerprint_set": self._session_fingerprint is not None,
        }
