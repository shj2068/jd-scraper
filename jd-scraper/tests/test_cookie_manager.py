"""
Cookie 管理器单元测试
"""

import json
import time
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from python.cookie_manager import CookieManager, JD_CRITICAL_COOKIES
from python.models import CookieJar, CookieEntry


class TestCookieJar:
    """CookieJar 模型测试"""

    def test_set_and_get(self):
        """测试设置和获取 Cookie"""
        jar = CookieJar()
        jar.set("test", "value")
        assert jar.get("test") == "value"

    def test_get_nonexistent(self):
        """测试获取不存在的 Cookie"""
        jar = CookieJar()
        assert jar.get("nonexistent") is None

    def test_remove(self):
        """测试移除 Cookie"""
        jar = CookieJar()
        jar.set("test", "value")
        assert jar.remove("test") is True
        assert jar.get("test") is None

    def test_remove_nonexistent(self):
        """测试移除不存在的 Cookie"""
        jar = CookieJar()
        assert jar.remove("nonexistent") is False

    def test_expired_cookie(self):
        """测试过期 Cookie"""
        jar = CookieJar()
        jar.set("test", "value", expires=time.time() - 100)  # 已过期
        assert jar.get("test") is None

    def test_valid_cookie(self):
        """测试有效 Cookie"""
        jar = CookieJar()
        jar.set("test", "value", expires=time.time() + 3600)  # 1小时后过期
        assert jar.get("test") == "value"

    def test_clear_expired(self):
        """测试清理过期 Cookie"""
        jar = CookieJar()
        jar.set("valid", "value1", expires=time.time() + 3600)
        jar.set("expired", "value2", expires=time.time() - 100)

        count = jar.clear_expired()
        assert count == 1
        assert jar.get("valid") == "value1"
        assert jar.get("expired") is None

    def test_to_header_string(self):
        """测试转换为 Cookie 头字符串"""
        jar = CookieJar()
        jar.set("a", "1")
        jar.set("b", "2")

        header = jar.to_header_string()
        assert "a=1" in header
        assert "b=2" in header
        assert "; " in header

    def test_to_dict(self):
        """测试转换为字典"""
        jar = CookieJar()
        jar.set("a", "1")
        jar.set("b", "2")

        d = jar.to_dict()
        assert d == {"a": "1", "b": "2"}

    def test_count(self):
        """测试 Cookie 计数"""
        jar = CookieJar()
        jar.set("a", "1")
        jar.set("b", "2")
        assert jar.count == 2

    def test_valid_count(self):
        """测试有效 Cookie 计数"""
        jar = CookieJar()
        jar.set("valid", "1", expires=time.time() + 3600)
        jar.set("expired", "2", expires=time.time() - 100)

        assert jar.valid_count == 1


class TestCookieEntry:
    """CookieEntry 模型测试"""

    def test_not_expired(self):
        """测试未过期条目"""
        entry = CookieEntry(name="test", value="val", expires=time.time() + 3600)
        assert entry.is_expired is False

    def test_expired(self):
        """测试已过期条目"""
        entry = CookieEntry(name="test", value="val", expires=time.time() - 100)
        assert entry.is_expired is True

    def test_no_expiry(self):
        """测试永不过期"""
        entry = CookieEntry(name="test", value="val", expires=-1)
        assert entry.is_expired is False
        assert entry.ttl == float("inf")

    def test_ttl(self):
        """测试剩余有效时间"""
        future = time.time() + 3600
        entry = CookieEntry(name="test", value="val", expires=future)
        assert 3500 < entry.ttl < 3700


class TestCookieManager:
    """CookieManager 测试"""

    def test_set_and_get_cookie(self, temp_dir):
        """测试设置和获取 Cookie"""
        manager = CookieManager(storage_dir=str(temp_dir), auto_save=False)
        manager.set_cookie("test", "value")
        assert manager.get_cookie("test") == "value"

    def test_set_cookies_batch(self, temp_dir, sample_cookies_dict):
        """测试批量设置 Cookie"""
        manager = CookieManager(storage_dir=str(temp_dir), auto_save=False)
        manager.set_cookies(sample_cookies_dict)

        for name, value in sample_cookies_dict.items():
            assert manager.get_cookie(name) == value

    def test_get_all_cookies(self, temp_dir, sample_cookies_dict):
        """测试获取所有 Cookie"""
        manager = CookieManager(storage_dir=str(temp_dir), auto_save=False)
        manager.set_cookies(sample_cookies_dict)

        all_cookies = manager.get_all_cookies()
        assert len(all_cookies) == len(sample_cookies_dict)

    def test_remove_cookie(self, temp_dir):
        """测试移除 Cookie"""
        manager = CookieManager(storage_dir=str(temp_dir), auto_save=False)
        manager.set_cookie("test", "value")
        assert manager.remove_cookie("test") is True
        assert manager.get_cookie("test") is None

    def test_cookie_header_string(self, temp_dir, sample_cookies_dict):
        """测试 Cookie 头字符串"""
        manager = CookieManager(storage_dir=str(temp_dir), auto_save=False)
        manager.set_cookies(sample_cookies_dict)

        header = manager.get_cookie_header()
        assert isinstance(header, str)
        assert "__jda=" in header

    def test_check_critical_cookies(self, temp_dir):
        """测试关键 Cookie 检查"""
        manager = CookieManager(storage_dir=str(temp_dir), auto_save=False)
        manager.set_cookie("__jda", "value")

        status = manager.check_critical_cookies()
        assert status["__jda"] is True
        assert status["pt_key"] is False  # 未设置

    def test_get_status(self, temp_dir, sample_cookies_dict):
        """测试状态摘要"""
        manager = CookieManager(storage_dir=str(temp_dir), auto_save=False)
        manager.set_cookies(sample_cookies_dict)

        status = manager.get_status()
        assert status["total_cookies"] == len(sample_cookies_dict)
        assert status["valid_cookies"] == len(sample_cookies_dict)
        assert isinstance(status["critical_cookies"], dict)

    def test_switch_account(self, temp_dir):
        """测试切换账号"""
        manager = CookieManager(storage_dir=str(temp_dir), auto_save=False)
        manager.set_cookie("test", "value1", account_id="account1")
        manager.set_cookie("test", "value2", account_id="account2")

        manager.switch_account("account1")
        assert manager.get_cookie("test") == "value1"

        manager.switch_account("account2")
        assert manager.get_cookie("test") == "value2"

    def test_list_accounts(self, temp_dir):
        """测试列出账号"""
        manager = CookieManager(storage_dir=str(temp_dir), auto_save=False)
        manager.set_cookie("test", "v1", account_id="acc1")
        manager.set_cookie("test", "v2", account_id="acc2")

        accounts = manager.list_accounts()
        assert "acc1" in accounts
        assert "acc2" in accounts

    def test_persistence(self, temp_dir):
        """测试 Cookie 持久化"""
        # 写入
        manager1 = CookieManager(storage_dir=str(temp_dir), auto_save=True)
        manager1.set_cookie("persistent", "value", account_id="test_acc")

        # 重新加载
        manager2 = CookieManager(storage_dir=str(temp_dir), auto_save=False)
        manager2.switch_account("test_acc")
        assert manager2.get_cookie("persistent") == "value"

    def test_clear_all(self, temp_dir):
        """测试清空所有 Cookie"""
        manager = CookieManager(storage_dir=str(temp_dir), auto_save=False)
        manager.set_cookie("a", "1")
        manager.set_cookie("b", "2")

        manager.clear_all()
        assert manager.get_cookie("a") is None
        assert manager.get_cookie("b") is None
