"""
系统集成测试（端到端）

测试完整流程：签名生成 -> 请求构造 -> 参数完整性验证。
不依赖外部服务（Node.js 签名服务使用 Mock）。
"""

import json
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from python.sign import generate_sign, verify_sign
from python.models import JDRequest, SignResponse, SignParams
from python.request_builder import RequestBuilder
from python.cookie_manager import CookieManager
from python.fingerprint import FingerprintGenerator
from python.anti_detect import AntiDetect
from python.jsrpc_client import JSRPCClient


class TestEndToEndSignFlow:
    """端到端签名流程测试"""

    def test_full_sign_flow_without_h5st(self, sample_function_id, sample_uuid):
        """测试完整签名流程（不含 h5st）"""
        # 1. 生成签名
        body = '{"cid":"0"}'
        sign, t = generate_sign(
            function_id=sample_function_id,
            body=body,
            uuid=sample_uuid,
        )

        # 2. 验证签名
        assert verify_sign(
            sign_hash=sign,
            function_id=sample_function_id,
            body=body,
            uuid=sample_uuid,
            t=t,
        )

        # 3. 构建请求
        request = JDRequest(
            function_id=sample_function_id,
            body={"cid": "0"},
            uuid=sample_uuid,
            sign=sign,
            t=t,
        )

        # 4. 验证请求参数完整性
        params = request.to_params()
        assert params["functionId"] == sample_function_id
        assert params["sign"] == sign
        assert params["t"] == t
        assert params["uuid"] == sample_uuid
        assert "body" in params

    def test_full_sign_flow_with_mock_jsrpc(self, sample_function_id, sample_uuid):
        """测试完整签名流程（Mock JSRPC）"""
        # 1. Mock JSRPC 响应
        mock_jsrpc = MagicMock(spec=JSRPCClient)
        mock_jsrpc.get_h5st.return_value = SignResponse(
            code=0,
            h5st="2.8.0_mock_h5st_test_value",
            t="1700000000000",
        )

        # 2. 构建请求（带 h5st）
        builder = RequestBuilder(
            jsrpc_client=mock_jsrpc,
            cookie_manager=None,
        )

        request = builder.build_request(
            function_id=sample_function_id,
            body={"cid": "0"},
            include_h5st=True,
        )

        # 3. 验证
        assert request.h5st == "2.8.0_mock_h5st_test_value"
        assert request.sign != ""
        assert request.function_id == sample_function_id

        # 4. 验证 JSRPC 被正确调用
        mock_jsrpc.get_h5st.assert_called_once()


class TestRequestBuilderIntegration:
    """RequestBuilder 集成测试"""

    @pytest.fixture
    def full_builder(self, temp_dir):
        """创建完整配置的 RequestBuilder"""
        cookie_manager = CookieManager(
            storage_dir=str(temp_dir),
            auto_save=False,
        )
        cookie_manager.set_cookies({
            "__jda": "test_jda_value",
            "jd-uuid": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        })

        anti_detect = AntiDetect(
            random_delay_range=(0.01, 0.02),  # 测试用极短延迟
            enable_ua_rotation=True,
        )

        fingerprint = FingerprintGenerator(platform="mobile")

        return RequestBuilder(
            jsrpc_client=None,
            cookie_manager=cookie_manager,
            anti_detect=anti_detect,
            fingerprint=fingerprint,
        )

    def test_builder_with_cookies(self, full_builder, sample_function_id):
        """测试带 Cookie 的请求构建"""
        request = full_builder.build_request(
            function_id=sample_function_id,
            body={"cid": "0"},
            include_h5st=False,
            include_cookies=True,
        )

        assert len(request.cookies) > 0
        assert "__jda" in request.cookies

    def test_builder_without_cookies(self, full_builder, sample_function_id):
        """测试不带 Cookie 的请求构建"""
        request = full_builder.build_request(
            function_id=sample_function_id,
            body={"cid": "0"},
            include_h5st=False,
            include_cookies=False,
        )

        assert len(request.cookies) == 0

    def test_builder_multiple_requests(self, full_builder):
        """测试连续构建多个请求"""
        functions = [
            "bizSearchCategoryList",
            "supplierServiceProviderList",
            "jd_industry_news_list",
        ]

        requests = []
        for func_id in functions:
            req = full_builder.build_request(
                function_id=func_id,
                body={},
                include_h5st=False,
            )
            requests.append(req)

        assert len(requests) == 3
        # 每个请求的 functionId 不同
        assert requests[0].function_id != requests[1].function_id


class TestFingerprintIntegration:
    """指纹生成集成测试"""

    def test_fingerprint_to_request(self, sample_function_id):
        """测试指纹生成 -> 请求构建"""
        gen = FingerprintGenerator(platform="mobile")
        uuid = gen.get_or_create_uuid()

        # 使用生成的 UUID 构建请求
        request = JDRequest(
            function_id=sample_function_id,
            body={"cid": "0"},
            uuid=uuid,
        )

        params = request.to_params()
        assert params["uuid"] == uuid
        assert len(uuid) == 32


class TestAntiDetectIntegration:
    """反检测集成测试"""

    def test_headers_applied_to_request(self, sample_function_id):
        """测试反检测请求头应用"""
        anti_detect = AntiDetect(enable_ua_rotation=True)
        headers = anti_detect.build_stealth_headers()

        assert "User-Agent" in headers
        assert "Referer" in headers
        assert "Origin" in headers
        assert "X-Requested-With" in headers
        assert headers["Origin"] == "https://zhaoshang.jd.com"


class TestDegradationFlow:
    """降级流程测试"""

    def test_jsrpc_fallback_to_local_sign(self, sample_function_id, sample_uuid):
        """测试 JSRPC 降级到本地签名"""
        # Mock JSRPC 失败
        mock_jsrpc = MagicMock(spec=JSRPCClient)
        mock_jsrpc.get_h5st.side_effect = Exception("Service unavailable")
        mock_jsrpc.enable_fallback = True

        # 创建带降级的客户端
        client = JSRPCClient(
            server_url="http://localhost:9999",  # 不存在的端口
            enable_fallback=True,
            max_retries=0,
        )

        result = client.get_h5st(
            function_id=sample_function_id,
            body='{"cid":"0"}',
            uuid=sample_uuid,
        )

        # 降级结果：有 sign 无 h5st
        assert result.code == 0
        assert result.h5st == ""
        assert result.sign != ""

    def test_degradation_levels(self, sample_function_id, sample_body, sample_uuid):
        """测试三级降级策略"""
        # 一级：JSRPC（Mock 成功）
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 0, "h5st": "mock_h5st"}
        mock_resp.raise_for_status = MagicMock()

        # 二级：本地签名
        sign, t = generate_sign(
            function_id=sample_function_id,
            body=sample_body,
            uuid=sample_uuid,
        )
        assert sign != ""

        # 三级：直接请求（无签名）
        request = JDRequest(
            function_id=sample_function_id,
            body={"cid": "0"},
            uuid=sample_uuid,
        )
        params = request.to_params()
        assert params["functionId"] == sample_function_id


class TestConfigLoading:
    """配置加载测试"""

    def test_load_settings(self):
        """测试加载配置文件"""
        from python.utils import load_config

        config_path = Path(__file__).parent.parent / "config" / "settings.yaml"
        if config_path.exists():
            config = load_config(str(config_path))
            assert "api" in config
            assert "jsrpc" in config
            assert "browser_pool" in config
            assert "anti_detect" in config
            assert "degradation" in config
