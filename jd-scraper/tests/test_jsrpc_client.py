"""
JSRPC 客户端单元测试（使用 Mock）
"""

import json
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from python.jsrpc_client import JSRPCClient
from python.models import SignResponse


class TestJSRPCClient:
    """JSRPCClient 测试"""

    @pytest.fixture
    def client(self):
        """创建测试用客户端"""
        return JSRPCClient(
            server_url="http://localhost:3001",
            timeout=5.0,
            max_retries=1,
            enable_fallback=True,
        )

    @pytest.fixture
    def mock_response(self):
        """模拟成功响应"""
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = {
            "code": 0,
            "h5st": "2.8.0_mock_h5st_value",
            "t": "1700000000000",
        }
        mock.raise_for_status = MagicMock()
        return mock

    @pytest.fixture
    def mock_error_response(self):
        """模拟错误响应"""
        mock = MagicMock()
        mock.status_code = 500
        mock.json.return_value = {
            "code": -1,
            "error": "Internal Server Error",
        }
        mock.raise_for_status = MagicMock()
        return mock

    def test_get_h5st_success(self, client, mock_response):
        """测试成功获取 h5st"""
        with patch.object(client, '_get_session') as mock_session:
            mock_session.return_value.post.return_value = mock_response

            result = client.get_h5st(
                function_id="bizSearchCategoryList",
                body='{"cid":"0"}',
                uuid="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
                t="1700000000000",
            )

            assert result.is_success
            assert result.h5st == "2.8.0_mock_h5st_value"

    def test_get_h5st_fallback_on_failure(self, client):
        """测试 JSRPC 失败时降级"""
        with patch.object(client, '_get_session') as mock_session:
            mock_session.return_value.post.side_effect = Exception("Connection refused")

            result = client.get_h5st(
                function_id="bizSearchCategoryList",
                body='{"cid":"0"}',
                uuid="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            )

            # 降级模式返回本地 sign（无 h5st）
            assert result.code == 0
            assert result.h5st == ""
            assert result.sign != ""

    def test_check_health_success(self, client):
        """测试健康检查成功"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok"}

        with patch.object(client, '_get_session') as mock_session:
            mock_session.return_value.get.return_value = mock_resp

            assert client.check_health() is True

    def test_check_health_failure(self, client):
        """测试健康检查失败"""
        with patch.object(client, '_get_session') as mock_session:
            mock_session.return_value.get.side_effect = Exception("Connection refused")

            assert client.check_health() is False

    def test_inject_cookies(self, client):
        """测试 Cookie 注入"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 0}

        with patch.object(client, '_get_session') as mock_session:
            mock_session.return_value.post.return_value = mock_resp

            result = client.inject_cookies({"__jda": "value"})
            assert result is True

    def test_close(self, client):
        """测试关闭客户端"""
        client._session = MagicMock()
        client.close()
        assert client._session is None

    def test_context_manager(self):
        """测试上下文管理器"""
        with JSRPCClient() as client:
            assert client is not None


class TestSignResponse:
    """SignResponse 模型测试"""

    def test_from_dict_success(self):
        """测试从字典创建成功响应"""
        data = {"code": 0, "h5st": "test_h5st", "t": "1700000000000"}
        resp = SignResponse.from_dict(data)

        assert resp.is_success
        assert resp.h5st == "test_h5st"

    def test_from_dict_error(self):
        """测试从字典创建错误响应"""
        data = {"code": -1, "error": "something went wrong"}
        resp = SignResponse.from_dict(data)

        assert not resp.is_success
        assert resp.error == "something went wrong"

    def test_from_dict_empty(self):
        """测试从空字典创建"""
        data = {}
        resp = SignResponse.from_dict(data)

        assert not resp.is_success
        assert resp.code == -1
