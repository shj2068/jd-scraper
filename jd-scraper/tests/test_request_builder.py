"""
请求构造器单元测试
"""

import json
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from python.request_builder import RequestBuilder, JD_API_BASE_URL, FUNCTION_CONFIGS
from python.models import JDRequest


class TestRequestBuilder:
    """RequestBuilder 测试"""

    @pytest.fixture
    def builder(self):
        """创建不带外部依赖的 RequestBuilder"""
        return RequestBuilder(
            jsrpc_client=None,
            cookie_manager=None,
        )

    def test_build_request_basic(self, builder, sample_function_id, sample_uuid):
        """测试基础请求构建"""
        request = builder.build_request(
            function_id=sample_function_id,
            body={"cid": "0"},
            include_h5st=False,
        )

        assert isinstance(request, JDRequest)
        assert request.function_id == sample_function_id
        assert request.uuid is not None
        assert request.sign != ""
        assert request.t != ""

    def test_build_request_has_all_params(self, builder, sample_function_id):
        """测试请求包含所有必要参数"""
        request = builder.build_request(
            function_id=sample_function_id,
            body={"cid": "0"},
            include_h5st=False,
        )

        assert request.appid == "ebf5a3c8"
        assert request.client == "h5"
        assert request.client_version == "1.0.0"

    def test_build_request_to_params(self, builder, sample_function_id):
        """测试请求转 URL 参数"""
        request = builder.build_request(
            function_id=sample_function_id,
            body={"cid": "0"},
            include_h5st=False,
        )

        params = request.to_params()
        assert "functionId" in params
        assert "sign" in params
        assert "t" in params
        assert "uuid" in params
        assert "appid" in params

    def test_build_request_body_serialization(self, builder, sample_function_id):
        """测试 body 序列化"""
        body = {"cid": "0", "page": 1}
        request = builder.build_request(
            function_id=sample_function_id,
            body=body,
            include_h5st=False,
        )

        params = request.to_params()
        parsed_body = json.loads(params["body"])
        assert parsed_body == body

    def test_get_function_info_known(self, builder):
        """测试获取已知接口信息"""
        info = builder.get_function_info("bizSearchCategoryList")
        assert info["method"] == "GET"
        assert info["encryption_level"] == "medium"

    def test_get_function_info_unknown(self, builder):
        """测试获取未知接口信息"""
        info = builder.get_function_info("unknownFunction")
        assert info["method"] == "GET"
        assert info["encryption_level"] == "unknown"

    def test_list_supported_functions(self, builder):
        """测试列出支持的接口"""
        functions = builder.list_supported_functions()
        assert isinstance(functions, list)
        assert "bizSearchCategoryList" in functions
        assert len(functions) == len(FUNCTION_CONFIGS)


class TestJDRequest:
    """JDRequest 模型测试"""

    def test_to_params(self, sample_function_id, sample_uuid):
        """测试参数转换"""
        request = JDRequest(
            function_id=sample_function_id,
            body={"cid": "0"},
            uuid=sample_uuid,
            sign="abc123",
            t="1700000000000",
        )

        params = request.to_params()
        assert params["functionId"] == sample_function_id
        assert params["sign"] == "abc123"
        assert params["t"] == "1700000000000"

    def test_to_params_with_h5st(self, sample_function_id, sample_uuid):
        """测试带 h5st 的参数"""
        request = JDRequest(
            function_id=sample_function_id,
            body={},
            uuid=sample_uuid,
            h5st="some_h5st_value",
            sign="sign_value",
            t="1700000000000",
        )

        params = request.to_params()
        assert "h5st" in params
        assert params["h5st"] == "some_h5st_value"

    def test_to_params_without_h5st(self, sample_function_id, sample_uuid):
        """测试不带 h5st 的参数"""
        request = JDRequest(
            function_id=sample_function_id,
            body={},
            uuid=sample_uuid,
            t="1700000000000",
        )

        params = request.to_params()
        assert "h5st" not in params or params["h5st"] == ""

    def test_get_body_json(self, sample_function_id, sample_uuid):
        """测试 body JSON 序列化"""
        request = JDRequest(
            function_id=sample_function_id,
            body={"key": "value"},
            uuid=sample_uuid,
        )

        body_json = request.get_body_json()
        assert json.loads(body_json) == {"key": "value"}

    def test_auto_timestamp(self, sample_function_id, sample_uuid):
        """测试自动时间戳"""
        request = JDRequest(
            function_id=sample_function_id,
            body={},
            uuid=sample_uuid,
        )

        assert len(request.t) == 13  # 毫秒时间戳


class TestFunctionConfigs:
    """接口配置测试"""

    def test_all_functions_have_config(self):
        """测试所有接口都有配置"""
        required_keys = {"method", "encryption_level", "requires_h5st", "requires_login"}

        for func_id, config in FUNCTION_CONFIGS.items():
            assert set(config.keys()) == required_keys, f"{func_id} 缺少配置项"

    def test_method_values(self):
        """测试 HTTP 方法值有效"""
        valid_methods = {"GET", "POST"}

        for func_id, config in FUNCTION_CONFIGS.items():
            assert config["method"] in valid_methods, f"{func_id} 方法无效"
