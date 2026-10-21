"""
sign 签名模块单元测试
"""

import hashlib
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from python.sign import (
    generate_sign,
    generate_sign_from_params,
    verify_sign,
    create_sign_params,
    DEFAULT_CLIENT,
    DEFAULT_CLIENT_VERSION,
    DEFAULT_APPID,
)
from python.models import SignParams


class TestGenerateSign:
    """generate_sign 函数测试"""

    def test_basic_sign_generation(self, sample_function_id, sample_body, sample_uuid):
        """测试基础签名生成"""
        sign, t = generate_sign(
            function_id=sample_function_id,
            body=sample_body,
            uuid=sample_uuid,
            t="1700000000000",
        )

        assert isinstance(sign, str)
        assert len(sign) == 32  # MD5 哈希长度
        assert t == "1700000000000"

    def test_sign_deterministic(self, sample_function_id, sample_body, sample_uuid):
        """测试签名确定性（相同输入产生相同输出）"""
        sign1, t1 = generate_sign(
            function_id=sample_function_id,
            body=sample_body,
            uuid=sample_uuid,
            t="1700000000000",
        )

        sign2, t2 = generate_sign(
            function_id=sample_function_id,
            body=sample_body,
            uuid=sample_uuid,
            t="1700000000000",
        )

        assert sign1 == sign2
        assert t1 == t2

    def test_sign_changes_with_different_body(self, sample_function_id, sample_uuid):
        """测试不同 body 产生不同签名"""
        sign1, _ = generate_sign(
            function_id=sample_function_id,
            body='{"cid":"0"}',
            uuid=sample_uuid,
            t="1700000000000",
        )

        sign2, _ = generate_sign(
            function_id=sample_function_id,
            body='{"cid":"1"}',
            uuid=sample_uuid,
            t="1700000000000",
        )

        assert sign1 != sign2

    def test_sign_auto_timestamp(self, sample_function_id, sample_body, sample_uuid):
        """测试自动生成时间戳"""
        sign, t = generate_sign(
            function_id=sample_function_id,
            body=sample_body,
            uuid=sample_uuid,
        )

        assert isinstance(t, str)
        assert len(t) == 13  # 毫秒时间戳长度

    def test_sign_with_token(self, sample_function_id, sample_body, sample_uuid):
        """测试带 token 的签名"""
        sign1, _ = generate_sign(
            function_id=sample_function_id,
            body=sample_body,
            uuid=sample_uuid,
            token="",
            t="1700000000000",
        )

        sign2, _ = generate_sign(
            function_id=sample_function_id,
            body=sample_body,
            uuid=sample_uuid,
            token="some_token",
            t="1700000000000",
        )

        assert sign1 != sign2

    def test_sign_matches_manual_calculation(self, sample_function_id, sample_body, sample_uuid, sample_timestamp):
        """测试签名与手动计算结果一致"""
        sign, _ = generate_sign(
            function_id=sample_function_id,
            body=sample_body,
            uuid=sample_uuid,
            t=sample_timestamp,
        )

        # 手动计算
        raw = (
            f"functionId={sample_function_id}"
            f"&body={sample_body}"
            f"&uuid={sample_uuid}"
            f"&client={DEFAULT_CLIENT}"
            f"&clientVersion={DEFAULT_CLIENT_VERSION}"
            f"&t={sample_timestamp}"
            f"&appid={DEFAULT_APPID}"
            f"&token="
        )
        expected = hashlib.md5(raw.encode("utf-8")).hexdigest()

        assert sign == expected


class TestVerifySign:
    """verify_sign 函数测试"""

    def test_verify_correct_sign(self, sample_function_id, sample_body, sample_uuid, sample_timestamp):
        """测试验证正确签名"""
        sign, _ = generate_sign(
            function_id=sample_function_id,
            body=sample_body,
            uuid=sample_uuid,
            t=sample_timestamp,
        )

        assert verify_sign(
            sign_hash=sign,
            function_id=sample_function_id,
            body=sample_body,
            uuid=sample_uuid,
            t=sample_timestamp,
        ) is True

    def test_verify_incorrect_sign(self, sample_function_id, sample_body, sample_uuid, sample_timestamp):
        """测试验证错误签名"""
        assert verify_sign(
            sign_hash="wrong_sign_value_000000000000",
            function_id=sample_function_id,
            body=sample_body,
            uuid=sample_uuid,
            t=sample_timestamp,
        ) is False


class TestSignParams:
    """SignParams 模型测试"""

    def test_sign_params_creation(self, sample_function_id, sample_body, sample_uuid):
        """测试 SignParams 创建"""
        params = SignParams(
            function_id=sample_function_id,
            body=sample_body,
            uuid=sample_uuid,
        )

        assert params.function_id == sample_function_id
        assert params.body == sample_body
        assert params.uuid == sample_uuid
        assert params.client == "h5"
        assert params.appid == "ebf5a3c8"

    def test_sign_params_to_sign_string(self, sample_function_id, sample_body, sample_uuid, sample_timestamp):
        """测试签名字符串生成"""
        params = SignParams(
            function_id=sample_function_id,
            body=sample_body,
            uuid=sample_uuid,
            t=sample_timestamp,
        )

        sign_string = params.to_sign_string()
        assert "functionId=" in sign_string
        assert "body=" in sign_string
        assert "uuid=" in sign_string

    def test_generate_sign_from_params(self, sample_function_id, sample_body, sample_uuid, sample_timestamp):
        """测试从 SignParams 生成签名"""
        params = SignParams(
            function_id=sample_function_id,
            body=sample_body,
            uuid=sample_uuid,
            t=sample_timestamp,
        )

        sign, t = generate_sign_from_params(params)
        assert isinstance(sign, str)
        assert len(sign) == 32


class TestCreateSignParams:
    """create_sign_params 工厂函数测试"""

    def test_create_with_defaults(self, sample_function_id, sample_body, sample_uuid):
        """测试使用默认值创建"""
        params = create_sign_params(
            function_id=sample_function_id,
            body=sample_body,
            uuid=sample_uuid,
        )

        assert params.client == "h5"
        assert params.appid == "ebf5a3c8"

    def test_create_with_custom_values(self, sample_function_id, sample_body, sample_uuid):
        """测试使用自定义值创建"""
        params = create_sign_params(
            function_id=sample_function_id,
            body=sample_body,
            uuid=sample_uuid,
            client="pc",
            appid="custom_appid",
        )

        assert params.client == "pc"
        assert params.appid == "custom_appid"
