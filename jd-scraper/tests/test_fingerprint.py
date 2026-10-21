"""
设备指纹模块单元测试
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from python.fingerprint import FingerprintGenerator
from python.models import BrowserFingerprint


class TestFingerprintGenerator:
    """FingerprintGenerator 测试"""

    def test_generate_uuid_format(self):
        """测试 UUID 格式（32位十六进制）"""
        gen = FingerprintGenerator()
        uuid = gen.generate_uuid()

        assert isinstance(uuid, str)
        assert len(uuid) == 32
        assert all(c in "0123456789abcdef" for c in uuid)

    def test_uuid_uniqueness(self):
        """测试 UUID 唯一性"""
        gen = FingerprintGenerator()
        uuids = [gen.generate_uuid() for _ in range(100)]
        assert len(set(uuids)) == 100  # 全部唯一

    def test_get_or_create_uuid_caching(self):
        """测试 UUID 缓存"""
        gen = FingerprintGenerator()
        uuid1 = gen.get_or_create_uuid()
        uuid2 = gen.get_or_create_uuid()
        assert uuid1 == uuid2

    def test_set_uuid(self):
        """测试手动设置 UUID"""
        gen = FingerprintGenerator()
        custom_uuid = "a" * 32
        gen.set_uuid(custom_uuid)
        assert gen.get_or_create_uuid() == custom_uuid

    def test_set_invalid_uuid(self):
        """测试设置无效 UUID"""
        gen = FingerprintGenerator()
        with pytest.raises(ValueError):
            gen.set_uuid("too_short")

    def test_generate_fingerprint_mobile(self):
        """测试移动端指纹生成"""
        gen = FingerprintGenerator(platform="mobile")
        fp = gen.generate_fingerprint()

        assert isinstance(fp, BrowserFingerprint)
        assert "iPhone" in fp.user_agent or "Android" in fp.user_agent
        assert fp.language == "zh-CN"
        assert fp.timezone == "Asia/Shanghai"

    def test_generate_fingerprint_ios(self):
        """测试 iOS 指纹"""
        gen = FingerprintGenerator(platform="ios")
        fp = gen.generate_fingerprint()

        assert "iPhone" in fp.user_agent
        assert fp.pixel_ratio == 3.0

    def test_generate_fingerprint_android(self):
        """测试 Android 指纹"""
        gen = FingerprintGenerator(platform="android")
        fp = gen.generate_fingerprint()

        assert "Android" in fp.user_agent

    def test_generate_fingerprint_desktop(self):
        """测试桌面端指纹"""
        gen = FingerprintGenerator(platform="desktop")
        fp = gen.generate_fingerprint()

        assert fp.screen_width == 1920
        assert fp.screen_height == 1080
        assert fp.pixel_ratio == 1.0

    def test_fingerprint_to_dict(self):
        """测试指纹转字典"""
        gen = FingerprintGenerator()
        fp = gen.generate_fingerprint()
        d = fp.to_dict()

        assert "userAgent" in d
        assert "platform" in d
        assert "language" in d
        assert "timezone" in d

    def test_generate_stealth_script(self):
        """测试反检测脚本生成"""
        gen = FingerprintGenerator()
        script = gen.generate_stealth_script()

        assert isinstance(script, str)
        assert "navigator" in script
        assert "webdriver" in script

    def test_to_playwright_context_options(self):
        """测试 Playwright context 选项"""
        gen = FingerprintGenerator(platform="mobile")
        options = gen.to_playwright_context_options()

        assert "user_agent" in options
        assert "viewport" in options
        assert "locale" in options
        assert options["is_mobile"] is True

    def test_canvas_hash_varies(self):
        """测试 Canvas 哈希每次不同"""
        gen = FingerprintGenerator()
        hashes = set()
        for _ in range(10):
            fp = gen.generate_fingerprint()
            hashes.add(fp.canvas_hash)

        # 至少部分不同（允许极小概率碰撞）
        assert len(hashes) > 1
