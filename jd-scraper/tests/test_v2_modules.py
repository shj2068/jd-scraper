"""
v2.0 新增模块测试

覆盖：
- h5st_parser: h5st 签名结构解析与版本检测
- monitor: 生产环境监控
- api_sniffer: API 嗅探器参数分类
- anti_detect: Sec-CH-UA 一致性校验
- cookie_manager: 自动刷新机制
"""

import time
import pytest

from python.h5st_parser import (
    H5stVersion,
    SignStrategy,
    parse_h5st,
    detect_version_from_samples,
    validate_h5st_freshness,
    get_strategy_recommendation,
)
from python.monitor import (
    ProductionMonitor,
    MonitorConfig,
    AlertLevel,
    AlertEvent,
)
from python.api_sniffer import APISniffer, ParamType
from python.anti_detect import AntiDetect


# ========== h5st_parser 测试 ==========


class TestH5stParser:
    """h5st 签名解析器测试"""

    def test_parse_v2_h5st(self):
        """解析 v2 版本 h5st"""
        h5st_str = "2022.11.29.1669718400000.abc123xy.sighash.checksum"
        result = parse_h5st(h5st_str)

        assert result.is_valid is True
        assert result.version == H5stVersion.V2
        assert result.version_date == "2022.11.29"
        assert result.timestamp == "1669718400000"
        assert result.random_str == "abc123xy"
        assert result.signature == "sighash"
        assert result.checksum == "checksum"
        assert result.segment_count == 7

    def test_parse_v1_h5st(self):
        """解析 v1 版本 h5st"""
        h5st_str = "2020.05.12.1589000000000.rand.sig"
        result = parse_h5st(h5st_str)

        assert result.is_valid is True
        assert result.version == H5stVersion.V1
        assert result.recommended_strategy == SignStrategy.PURE_PYTHON

    def test_parse_v3_h5st(self):
        """解析 v3 版本 h5st"""
        h5st_str = "2024.01.15.1705300000000.rand.sig.check.extra"
        result = parse_h5st(h5st_str)

        assert result.is_valid is True
        assert result.version == H5stVersion.V3
        assert result.recommended_strategy == SignStrategy.PLAYWRIGHT_FALLBACK

    def test_parse_empty_h5st(self):
        """解析空 h5st"""
        result = parse_h5st("")
        assert result.is_valid is False

    def test_parse_invalid_h5st(self):
        """解析无效 h5st（段数不足）"""
        result = parse_h5st("2022.11")
        assert result.is_valid is False

    def test_parse_none_h5st(self):
        """解析 None"""
        result = parse_h5st(None)
        assert result.is_valid is False

    def test_version_strategy_mapping(self):
        """版本→策略映射正确性"""
        assert get_strategy_recommendation(H5stVersion.V1)["strategy"] == "pure_python"
        assert get_strategy_recommendation(H5stVersion.V2)["strategy"] == "jsrpc"
        assert get_strategy_recommendation(H5stVersion.V3)["strategy"] == "playwright"

    def test_detect_version_from_samples(self):
        """多样本投票法版本检测"""
        samples = [
            "2022.11.29.1669718400000.abc.sig.ck",
            "2022.12.01.1670000000000.def.sig.ck",
            "2022.11.30.1669800000000.ghi.sig.ck",
        ]
        version = detect_version_from_samples(samples)
        assert version == H5stVersion.V2

    def test_detect_version_empty_samples(self):
        """空样本列表"""
        version = detect_version_from_samples([])
        assert version == H5stVersion.UNKNOWN

    def test_validate_freshness_recent(self):
        """验证新鲜 h5st"""
        ts = str(int(time.time() * 1000))
        h5st_str = f"2022.11.29.{ts}.abc.sig.ck"
        is_fresh, reason = validate_h5st_freshness(h5st_str, max_age_seconds=60)
        assert is_fresh is True

    def test_validate_freshness_expired(self):
        """验证过期 h5st"""
        old_ts = str(int(time.time() * 1000) - 120000)  # 2 分钟前
        h5st_str = f"2022.11.29.{old_ts}.abc.sig.ck"
        is_fresh, reason = validate_h5st_freshness(h5st_str, max_age_seconds=60)
        assert is_fresh is False
        assert "过期" in reason

    def test_h5st_structure_to_dict(self):
        """H5stStructure 转字典"""
        result = parse_h5st("2022.11.29.1669718400000.abc.sighash.ck")
        d = result.to_dict()
        assert "version" in d
        assert "recommended_strategy" in d
        assert "is_fresh" in d
        assert d["version"] == "v2"

    def test_h5st_age_seconds(self):
        """h5st 存活时间计算"""
        ts = str(int(time.time() * 1000) - 30000)  # 30 秒前
        result = parse_h5st(f"2022.11.29.{ts}.abc.sig.ck")
        assert 29 <= result.age_seconds <= 35

    def test_h5st_age_no_timestamp(self):
        """无时间戳的 h5st"""
        result = parse_h5st("2022.11.29")
        assert result.age_seconds == -1.0


# ========== monitor 测试 ==========


class TestProductionMonitor:
    """生产监控器测试"""

    def test_init_default_config(self):
        """默认配置初始化"""
        monitor = ProductionMonitor()
        assert monitor.config.sign_failure_threshold == 0.1
        assert monitor.config.window_size == 100

    def test_record_sign_result(self):
        """记录签名结果"""
        monitor = ProductionMonitor()
        monitor.record_sign_result(True)
        monitor.record_sign_result(True)
        monitor.record_sign_result(False)
        rate = monitor.get_sign_failure_rate()
        assert abs(rate - 1 / 3) < 0.01

    def test_sign_failure_alert(self):
        """签名失败率告警"""
        alerts = []
        config = MonitorConfig(
            sign_failure_threshold=0.1,
            alert_callback=lambda e: alerts.append(e),
        )
        monitor = ProductionMonitor(config)

        # 连续失败超过 10%
        for _ in range(15):
            monitor.record_sign_result(False)

        assert len(alerts) > 0
        assert alerts[-1].level == AlertLevel.WARNING

    def test_ip_ban_rate(self):
        """IP 封禁率计算"""
        monitor = ProductionMonitor()
        monitor.record_ip_request(False)
        monitor.record_ip_request(False)
        monitor.record_ip_request(True)
        rate = monitor.get_ip_ban_rate()
        assert abs(rate - 1 / 3) < 0.01

    def test_cookie_health_check(self):
        """Cookie 健康检查"""
        monitor = ProductionMonitor()
        future = time.time() + 3600  # 1h 后
        monitor.update_cookie_health("thor", future)

        cookies = monitor.check_critical_cookies(["thor"])
        assert cookies["thor"]["is_healthy"] is True
        assert cookies["thor"]["is_expiring"] is False

    def test_cookie_expiring_warning(self):
        """Cookie 即将过期告警"""
        alerts = []
        config = MonitorConfig(
            cookie_expiry_warning_seconds=600,
            alert_callback=lambda e: alerts.append(e),
        )
        monitor = ProductionMonitor(config)

        # 5 分钟后过期（在 10 分钟预警窗口内）
        monitor.update_cookie_health("thor", time.time() + 300)
        assert len(alerts) > 0

    def test_cookie_expired_critical(self):
        """Cookie 已过期严重告警"""
        alerts = []
        config = MonitorConfig(
            cookie_expiry_warning_seconds=600,
            alert_callback=lambda e: alerts.append(e),
        )
        monitor = ProductionMonitor(config)
        monitor.update_cookie_health("thor", time.time() - 10)  # 已过期

        critical_alerts = [a for a in alerts if a.level == AlertLevel.CRITICAL]
        assert len(critical_alerts) > 0

    def test_h5st_version_change_alert(self):
        """h5st 版本变化告警"""
        alerts = []
        config = MonitorConfig(
            h5st_version_change_alert=True,
            alert_callback=lambda e: alerts.append(e),
        )
        monitor = ProductionMonitor(config)

        monitor.track_h5st_version("v2")
        monitor.track_h5st_version("v3")  # 版本变化

        version_alerts = [a for a in alerts if a.metric_name == "h5st_version_changed"]
        assert len(version_alerts) == 1
        assert version_alerts[0].level == AlertLevel.CRITICAL

    def test_dashboard(self):
        """监控仪表盘"""
        monitor = ProductionMonitor()
        monitor.record_sign_result(True)
        monitor.record_ip_request(False)

        dashboard = monitor.get_dashboard()
        assert "sign" in dashboard
        assert "ip" in dashboard
        assert "cookies" in dashboard
        assert "h5st_version" in dashboard
        assert "alerts" in dashboard

    def test_reset(self):
        """重置监控数据"""
        monitor = ProductionMonitor()
        monitor.record_sign_result(True)
        monitor.track_h5st_version("v2")
        monitor.reset()

        assert monitor.get_sign_failure_rate() == 0.0
        assert monitor._last_h5st_version is None


# ========== api_sniffer 测试 ==========


class TestAPISniffer:
    """API 嗅探器测试"""

    def test_classify_signature_param(self):
        """分类签名参数"""
        sniffer = APISniffer()
        assert sniffer.classify_param("h5st") == ParamType.SIGNATURE
        assert sniffer.classify_param("sign") == ParamType.SIGNATURE

    def test_classify_timestamp_param(self):
        """分类时间戳参数"""
        sniffer = APISniffer()
        assert sniffer.classify_param("t") == ParamType.TIMESTAMP
        assert sniffer.classify_param("timestamp") == ParamType.TIMESTAMP
        # 值特征推断：13 位数字
        assert sniffer.classify_param("custom_ts", "1669718400000") == ParamType.TIMESTAMP

    def test_classify_device_id_param(self):
        """分类设备标识参数"""
        sniffer = APISniffer()
        assert sniffer.classify_param("eid") == ParamType.DEVICE_ID
        assert sniffer.classify_param("fp") == ParamType.DEVICE_ID
        assert sniffer.classify_param("uuid") == ParamType.DEVICE_ID

    def test_classify_session_param(self):
        """分类会话参数"""
        sniffer = APISniffer()
        assert sniffer.classify_param("thor") == ParamType.SESSION
        assert sniffer.classify_param("ctoken") == ParamType.SESSION
        assert sniffer.classify_param("pt_key") == ParamType.SESSION

    def test_classify_business_param(self):
        """分类业务参数"""
        sniffer = APISniffer()
        assert sniffer.classify_param("keyword") == ParamType.BUSINESS
        assert sniffer.classify_param("page") == ParamType.BUSINESS
        assert sniffer.classify_param("pageSize") == ParamType.BUSINESS
        assert sniffer.classify_param("functionId") == ParamType.BUSINESS

    def test_classify_by_value_length(self):
        """通过值长度推断参数类型"""
        sniffer = APISniffer()
        # 长字符串 → 签名
        assert sniffer.classify_param("unknown", "x" * 200) == ParamType.SIGNATURE

    def test_analyze_jd_api_request(self):
        """分析京东 API 请求"""
        sniffer = APISniffer()
        api = sniffer.analyze_request(
            url="https://api.m.jd.com/?functionId=bizSearchCategoryList&h5st=abc&t=123&body=%7B%7D",
            method="GET",
            response_status=200,
        )

        assert api is not None
        assert api.host == "api.m.jd.com"
        assert api.needs_reverse is True
        assert "h5st_required" in api.tags
        assert "gateway_api" in api.tags

    def test_analyze_non_jd_request(self):
        """分析非京东请求（应返回 None）"""
        sniffer = APISniffer()
        api = sniffer.analyze_request(url="https://example.com/api/test")
        assert api is None

    def test_sniff_start_stop(self):
        """嗅探启停控制"""
        sniffer = APISniffer()
        sniffer.start_sniff()
        assert sniffer._is_sniffing is True

        sniffer.capture_request({
            "url": "https://api.m.jd.com/?functionId=test&h5st=abc",
            "method": "GET",
            "responseStatus": 200,
        })

        result = sniffer.stop_sniff()
        assert sniffer._is_sniffing is False
        assert result.total_requests == 1
        assert result.api_count >= 1

    def test_sniff_result_to_dict(self):
        """嗅探结果序列化"""
        sniffer = APISniffer()
        sniffer.start_sniff()
        sniffer.capture_request({
            "url": "https://api.m.jd.com/?functionId=test",
            "method": "GET",
        })
        result = sniffer.stop_sniff()
        d = result.to_dict()
        assert "summary" in d
        assert "apis" in d


# ========== anti_detect Sec-CH-UA 测试 ==========


class TestSecChUaConsistency:
    """Sec-CH-UA 一致性校验测试"""

    def test_chrome_version_extraction(self):
        """从 Chrome UA 提取版本"""
        ad = AntiDetect()
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        sec_ch_ua, mobile, platform = ad._build_sec_ch_ua(ua)

        assert 'v="118"' in sec_ch_ua
        assert "Chromium" in sec_ch_ua
        assert mobile == "?0"  # Desktop
        assert '"Windows"' in platform

    def test_mobile_ua_detection(self):
        """移动端 UA 检测"""
        ad = AntiDetect()
        ua = "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36"
        sec_ch_ua, mobile, platform = ad._build_sec_ch_ua(ua)

        assert mobile == "?1"
        assert '"Android"' in platform

    def test_ios_ua_detection(self):
        """iOS UA 检测"""
        ad = AntiDetect()
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        _, _, platform = ad._build_sec_ch_ua(ua)

        assert '"iOS"' in platform

    def test_consistency_validation(self):
        """一致性校验通过"""
        ad = AntiDetect()
        ua = "Mozilla/5.0 Chrome/118.0.0.0 Safari/537.36"
        sec_ch_ua = '"Chromium";v="118", "Google Chrome";v="118"'
        assert ad.validate_sec_ch_ua_consistency(ua, sec_ch_ua) is True

    def test_consistency_validation_fail(self):
        """一致性校验失败"""
        ad = AntiDetect()
        ua = "Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36"
        sec_ch_ua = '"Chromium";v="118", "Google Chrome";v="118"'
        assert ad.validate_sec_ch_ua_consistency(ua, sec_ch_ua) is False

    def test_stealth_headers_dynamic_version(self):
        """隐身请求头动态版本"""
        ad = AntiDetect()
        headers = ad.build_stealth_headers()
        ua = headers.get("User-Agent", "")

        # 提取 UA 中的 Chrome 版本
        import re
        match = re.search(r"Chrome/(\d+)", ua)
        if match:
            chrome_ver = match.group(1)
            sec_ch_ua = headers.get("Sec-Ch-Ua", "")
            assert f'v="{chrome_ver}"' in sec_ch_ua


# ========== cookie_manager 自动刷新测试 ==========


class TestCookieAutoRefresh:
    """Cookie 自动刷新机制测试"""

    def test_short_lived_cookies_defined(self):
        """短生命周期 Cookie 定义"""
        from python.cookie_manager import JD_SHORT_LIVED_COOKIES

        assert "thor" in JD_SHORT_LIVED_COOKIES
        assert "ctoken" in JD_SHORT_LIVED_COOKIES
        assert JD_SHORT_LIVED_COOKIES["thor"] == 7200

    def test_get_expiring_cookies(self, temp_dir):
        """获取即将过期的 Cookie"""
        from python.cookie_manager import CookieManager

        mgr = CookieManager(storage_dir=str(temp_dir))
        # 设置一个即将过期的 Cookie
        mgr.set_cookie("thor", "test_value", time.time() + 300)  # 5 分钟后过期

        expiring = mgr.get_expiring_cookies(threshold_seconds=600)
        thor_entries = [e for e in expiring if e["name"] == "thor"]
        assert len(thor_entries) > 0
        assert thor_entries[0]["is_expired"] is False

    def test_get_expired_cookies(self, temp_dir):
        """获取已过期的 Cookie"""
        from python.cookie_manager import CookieManager

        mgr = CookieManager(storage_dir=str(temp_dir))
        mgr.set_cookie("thor", "test_value", time.time() - 10)  # 已过期

        expiring = mgr.get_expiring_cookies(threshold_seconds=600)
        thor_entries = [e for e in expiring if e["name"] == "thor"]
        assert len(thor_entries) > 0
        assert thor_entries[0]["is_expired"] is True

    def test_refresh_callback(self, temp_dir):
        """刷新回调触发"""
        from python.cookie_manager import CookieManager

        refreshed = []

        def mock_refresh(cookie_name, account_id):
            refreshed.append(cookie_name)
            return f"new_{cookie_name}_value"

        mgr = CookieManager(
            storage_dir=str(temp_dir),
            auto_refresh=False,  # 不启动线程
            refresh_callback=mock_refresh,
        )

        # 设置即将过期的 Cookie
        mgr.set_cookie("thor", "old_value", time.time() + 100)

        # 手动触发刷新检查
        mgr._check_and_refresh_expiring_cookies()

        assert "thor" in refreshed

    def test_shutdown_stops_thread(self, temp_dir):
        """shutdown 停止刷新线程"""
        from python.cookie_manager import CookieManager

        mgr = CookieManager(
            storage_dir=str(temp_dir),
            auto_refresh=True,
            refresh_callback=lambda n, a: "value",
            refresh_check_interval=0.5,
        )

        assert mgr._refresh_thread is not None
        assert mgr._refresh_thread.is_alive()

        mgr.shutdown()
        time.sleep(1)
        assert not mgr._refresh_thread.is_alive()
