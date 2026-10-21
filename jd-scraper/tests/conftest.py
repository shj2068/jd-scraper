"""
pytest 配置与公共 fixtures
"""

import sys
import os
import tempfile
from pathlib import Path

import pytest

# 将项目根目录加入 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_uuid():
    """示例 UUID（32位十六进制）"""
    return "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"


@pytest.fixture
def sample_function_id():
    """示例 functionId"""
    return "bizSearchCategoryList"


@pytest.fixture
def sample_body():
    """示例请求体"""
    return '{"cid":"0"}'


@pytest.fixture
def sample_timestamp():
    """示例时间戳"""
    return "1700000000000"


@pytest.fixture
def temp_dir():
    """临时目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_cookies_dict():
    """示例 Cookie 字典"""
    return {
        "__jda": "12222222.1234567890.1700000000.1700000000.1700000000.1",
        "__jdv": "12222222.1234567890",
        "jd-uuid": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "eid": "eid123456",
        "fp": "fp123456",
    }
