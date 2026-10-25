"""
Reverse Engineering MCP Server

提供标准化的逆向工程工具接口，支持：
- 网络流量捕获与分析
- 加密参数识别
- 动态 Hook 与验证
- 设备指纹生成
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict
import hashlib
import hmac
import base64
import re
from collections import Counter
import math

from mcp.server import Server
from mcp.types import Tool, TextContent, Resource, Prompt

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class CapturedRequest:
    """捕获的 HTTP 请求"""
    url: str
    method: str
    headers: Dict[str, str]
    query_params: Dict[str, str]
    body: Optional[str]
    timestamp: float
    suspicious_params: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class EncryptionAnalysis:
    """加密分析结果"""
    param_name: str
    param_value: str
    inferred_algorithm: str
    confidence: float
    characteristics: Dict[str, Any]
    possible_inputs: List[str]
    formula: Optional[str] = None


@dataclass
class HookResult:
    """Hook 结果"""
    method_name: str
    arguments: List[Dict[str, Any]]
    return_value: Any
    timestamp: float
    stack_trace: Optional[str] = None


# ============================================================================
# MCP Server 实现
# ============================================================================

app = Server("reverse-engineering-mcp")


# ----------------------------------------------------------------------------
# Tool 1: capture_traffic - 网络流量捕获
# ----------------------------------------------------------------------------

@app.tool("capture_traffic")
async def capture_traffic(
    target_url: str,
    duration: int = 30,
    filter_patterns: Optional[List[str]] = None,
    proxy_port: int = 8080
) -> Dict[str, Any]:
    """
    捕获目标 URL 的网络流量
    
    Args:
        target_url: 目标 URL 或域名
        duration: 抓包时长（秒）
        filter_patterns: URL 过滤模式列表
        proxy_port: 代理端口
    
    Returns:
        捕获的请求列表及分析结果
    """
    logger.info(f"Starting traffic capture: {target_url} for {duration}s")
    
    captured_requests = []
    
    try:
        # 使用 mitmproxy 进行流量捕获
        from mitmproxy import options, master
        from mitmproxy.addons import export
        
        # 创建自定义 addon
        class CaptureAddon:
            def __init__(self):
                self.requests = []
            
            def response(self, flow):
                # 过滤目标域名
                if target_url in flow.request.host:
                    req_data = {
                        "url": flow.request.url,
                        "method": flow.request.method,
                        "headers": dict(flow.request.headers),
                        "query_params": dict(flow.request.query),
                        "body": flow.request.get_text(),
                        "timestamp": flow.request.timestamp_start,
                        "response_status": flow.response.status_code,
                        "response_body": flow.response.get_text()[:1000]  # 限制长度
                    }
                    
                    # 识别可疑参数
                    suspicious = identify_suspicious_params(req_data)
                    req_data["suspicious_params"] = suspicious
                    
                    self.requests.append(req_data)
        
        # 配置 mitmproxy
        opts = options.Options(
            listen_host='127.0.0.1',
            listen_port=proxy_port,
            ssl_insecure=True
        )
        
        addon = CaptureAddon()
        
        # 运行抓包
        async def run_capture():
            m = master.Master(opts)
            m.addons.add(addon)
            
            # 应用过滤模式
            if filter_patterns:
                for pattern in filter_patterns:
                    logger.info(f"Filter pattern: {pattern}")
            
            await asyncio.sleep(duration)
            m.shutdown()
        
        await run_capture()
        
        captured_requests = addon.requests
        
        logger.info(f"Captured {len(captured_requests)} requests")
        
        return {
            "status": "success",
            "total_requests": len(captured_requests),
            "suspicious_requests": len([r for r in captured_requests if r.get("suspicious_params")]),
            "requests": captured_requests,
            "duration": duration,
            "target": target_url
        }
        
    except ImportError:
        logger.warning("mitmproxy not available, using mock data")
        return {
            "status": "mock",
            "message": "mitmproxy not installed, returning mock data",
            "total_requests": 0,
            "requests": []
        }
    except Exception as e:
        logger.error(f"Traffic capture failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "total_requests": 0,
            "requests": []
        }


def identify_suspicious_params(request_data: Dict) -> List[Dict[str, Any]]:
    """识别可疑的加密参数"""
    suspicious = []
    
    # 可疑参数命名模式
    suspicious_patterns = [
        r'sign[a-z_]*$',
        r'signature[a-z_]*$',
        r'token[a-z_]*$',
        r'encrypt[a-z_]*$',
        r'hash[a-z_]*$',
        r'cipher[a-z_]*$',
        r'h5st$',
        r'st$',
        r'sv$',
        r'uuid$'
    ]
    
    # 检查所有参数
    all_params = {
        **request_data.get("query_params", {}),
    }
    
    # 解析 body
    body = request_data.get("body")
    if body:
        try:
            body_json = json.loads(body)
            all_params.update(body_json)
        except:
            pass
    
    for key, value in all_params.items():
        if not value or not isinstance(value, str):
            continue
        
        # 命名模式匹配
        for pattern in suspicious_patterns:
            if re.match(pattern, key.lower()):
                suspicious.append({
                    "name": key,
                    "value": value[:100],  # 限制长度
                    "reason": "naming_pattern",
                    "pattern": pattern,
                    "characteristics": analyze_value_characteristics(value)
                })
                break
        
        # 值特征分析
        if looks_encrypted(value) and not any(s["name"] == key for s in suspicious):
            suspicious.append({
                "name": key,
                "value": value[:100],
                "reason": "encryption_pattern",
                "characteristics": analyze_value_characteristics(value)
            })
    
    return suspicious


def analyze_value_characteristics(value: str) -> Dict[str, Any]:
    """分析值的特征"""
    return {
        "length": len(value),
        "charset": detect_charset(value),
        "entropy": calculate_entropy(value),
        "is_base64": is_base64(value),
        "is_hex": all(c in '0123456789abcdefABCDEF' for c in value) if value else False,
        "timestamp_like": is_timestamp_like(value),
        "uuid_like": is_uuid_like(value)
    }


def looks_encrypted(value: str) -> bool:
    """判断值是否像加密数据"""
    if not value or len(value) < 8:
        return False
    
    # 高熵值
    entropy = calculate_entropy(value)
    if entropy > 4.0 and len(value) >= 16:
        return True
    
    # 特定长度（常见加密块大小）
    if len(value) in [16, 24, 32, 40, 48, 64]:
        if value.isalnum() or is_base64(value):
            return True
    
    return False


def calculate_entropy(s: str) -> float:
    """计算信息熵"""
    if not s:
        return 0.0
    
    counter = Counter(s)
    entropy = 0.0
    
    for count in counter.values():
        probability = count / len(s)
        if probability > 0:
            entropy -= probability * math.log2(probability)
    
    return entropy


def detect_charset(value: str) -> str:
    """检测字符集"""
    if value.isalnum() and value.islower():
        return "hex_lowercase"
    elif value.isalnum():
        return "alphanumeric"
    elif is_base64(value):
        return "base64"
    elif all(c in '0123456789abcdefABCDEF' for c in value):
        return "hex"
    else:
        return "mixed"


def is_base64(value: str) -> bool:
    """判断是否为 Base64"""
    try:
        if len(value) % 4 != 0:
            return False
        
        if not re.match(r'^[A-Za-z0-9+/]*={0,2}$', value):
            return False
        
        base64.b64decode(value, validate=True)
        return True
    except:
        return False


def is_timestamp_like(value: str) -> bool:
    """判断是否像时间戳"""
    try:
        ts = int(value)
        # 检查是否在合理范围内（2020-2030）
        return 1577836800 <= ts <= 1893456000
    except:
        return False


def is_uuid_like(value: str) -> bool:
    """判断是否像 UUID"""
    uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
    return bool(re.match(uuid_pattern, value.lower()))


# ----------------------------------------------------------------------------
# Tool 2: analyze_encryption - 加密分析
# ----------------------------------------------------------------------------

@app.tool("analyze_encryption")
async def analyze_encryption(
    request_data: Dict[str, Any],
    suspected_params: Optional[List[str]] = None,
    context_params: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    分析请求中的加密参数，推断算法
    
    Args:
        request_data: 请求数据（包含 headers, query, body）
        suspected_params: 疑似加密参数名列表
        context_params: 上下文参数（用于复现）
    
    Returns:
        加密分析结果
    """
    logger.info(f"Analyzing encryption for params: {suspected_params}")
    
    analyses = []
    
    # 提取参数
    all_params = {
        **request_data.get("query_params", {}),
        **request_data.get("headers", {})
    }
    
    body = request_data.get("body")
    if body:
        try:
            all_params.update(json.loads(body))
        except:
            pass
    
    # 分析每个可疑参数
    target_params = suspected_params or list(all_params.keys())
    
    for param_name in target_params:
        if param_name not in all_params:
            continue
        
        param_value = all_params[param_name]
        
        # 推断算法
        analysis = infer_algorithm(param_name, param_value, all_params, context_params)
        if analysis:
            analyses.append(asdict(analysis))
    
    return {
        "status": "success",
        "analyses": analyses,
        "total_analyzed": len(analyses),
        "recommendations": generate_recommendations(analyses)
    }


def infer_algorithm(
    param_name: str,
    param_value: str,
    all_params: Dict[str, str],
    context_params: Optional[Dict[str, str]]
) -> Optional[EncryptionAnalysis]:
    """推断加密算法"""
    
    # 基于特征匹配
    candidates = []
    
    # MD5 特征
    if len(param_value) == 32 and all(c in '0123456789abcdef' for c in param_value.lower()):
        candidates.append(("MD5", 0.8))
    
    # SHA1 特征
    elif len(param_value) == 40 and all(c in '0123456789abcdef' for c in param_value.lower()):
        candidates.append(("SHA1", 0.8))
    
    # SHA256 特征
    elif len(param_value) == 64 and all(c in '0123456789abcdef' for c in param_value.lower()):
        candidates.append(("SHA256", 0.8))
    
    # Base64 编码（可能是 AES/DES）
    elif is_base64(param_value) and len(param_value) % 16 == 0:
        candidates.append(("AES/DES_Base64", 0.6))
    
    # HMAC 特征（需要密钥）
    elif len(param_value) == 32 and "sign" in param_name.lower():
        candidates.append(("HMAC_MD5", 0.7))
    
    if not candidates:
        return None
    
    # 选择最佳匹配
    best_algo, confidence = max(candidates, key=lambda x: x[1])
    
    # 尝试复现
    possible_inputs, formula = attempt_reproduction(
        param_name, param_value, all_params, best_algo, context_params
    )
    
    return EncryptionAnalysis(
        param_name=param_name,
        param_value=param_value,
        inferred_algorithm=best_algo,
        confidence=confidence,
        characteristics=analyze_value_characteristics(param_value),
        possible_inputs=possible_inputs,
        formula=formula
    )


def attempt_reproduction(
    param_name: str,
    param_value: str,
    all_params: Dict[str, str],
    algorithm: str,
    context_params: Optional[Dict[str, str]]
) -> tuple[List[str], Optional[str]]:
    """尝试复现加密结果"""
    
    # 收集可能的输入参数
    other_params = {k: v for k, v in all_params.items() if k != param_name}
    
    if context_params:
        other_params.update(context_params)
    
    # 尝试常见组合
    import itertools
    
    combinations_tried = []
    
    # 单参数
    for key, value in other_params.items():
        result = apply_algorithm(algorithm, {key: value})
        if result == param_value:
            return [key], f"{algorithm}({key})"
        combinations_tried.append(f"{algorithm}({key})")
    
    # 双参数组合
    keys = list(other_params.keys())
    for pair in itertools.combinations(keys, 2):
        combo = {k: other_params[k] for k in pair}
        result = apply_algorithm(algorithm, combo)
        if result == param_value:
            return list(pair), f"{algorithm}({' + '.join(pair)})"
    
    # 三参数组合（限制数量）
    if len(keys) <= 5:
        for triple in itertools.combinations(keys, 3):
            combo = {k: other_params[k] for k in triple}
            result = apply_algorithm(algorithm, combo)
            if result == param_value:
                return list(triple), f"{algorithm}({' + '.join(triple)})"
    
    # 未找到匹配
    return [], None


def apply_algorithm(algorithm: str, params: Dict[str, str]) -> str:
    """应用算法"""
    
    # 拼接参数
    concat = "".join(str(v) for v in sorted(params.items()))
    
    if algorithm == "MD5":
        return hashlib.md5(concat.encode()).hexdigest()
    
    elif algorithm == "SHA1":
        return hashlib.sha1(concat.encode()).hexdigest()
    
    elif algorithm == "SHA256":
        return hashlib.sha256(concat.encode()).hexdigest()
    
    elif algorithm.startswith("HMAC"):
        # 尝试常见密钥
        for key in ["secret", "key", "salt", ""]:
            result = hmac.new(
                key.encode(),
                concat.encode(),
                hashlib.md5
            ).hexdigest()
            # 简化处理
            return result
    
    return ""


def generate_recommendations(analyses: List[Dict]) -> List[str]:
    """生成建议"""
    recommendations = []
    
    if not analyses:
        return ["未发现明显的加密参数"]
    
    for analysis in analyses:
        confidence = analysis.get("confidence", 0)
        
        if confidence < 0.7:
            recommendations.append(
                f"参数 {analysis['param_name']} 的推断置信度较低 ({confidence:.2f})，建议人工验证"
            )
        
        if not analysis.get("formula"):
            recommendations.append(
                f"参数 {analysis['param_name']} 无法自动复现，可能存在隐藏参数或盐值"
            )
        else:
            recommendations.append(
                f"参数 {analysis['param_name']} 疑似使用 {analysis['formula']}"
            )
    
    return recommendations


# ----------------------------------------------------------------------------
# Tool 3: hook_function - 动态 Hook
# ----------------------------------------------------------------------------

@app.tool("hook_function")
async def hook_function(
    package_name: str,
    class_name: str,
    method_name: str,
    target_output: Optional[str] = None,
    duration: int = 10
) -> Dict[str, Any]:
    """
    使用 Frida Hook 目标函数
    
    Args:
        package_name: Android 包名
        class_name: 类名（完整路径）
        method_name: 方法名
        target_output: 期望的输出值（用于验证）
        duration: Hook 持续时间（秒）
    
    Returns:
        Hook 结果
    """
    logger.info(f"Hooking {package_name}.{class_name}.{method_name}")
    
    try:
        import frida
        
        # 生成 Frida 脚本
        script_source = generate_hook_script(class_name, method_name, target_output)
        
        # 连接设备
        device = frida.get_usb_device()
        
        # 启动或附加到进程
        try:
            pid = device.spawn([package_name])
            session = device.attach(pid)
            device.resume(pid)
        except:
            # 进程已运行
            session = device.attach(package_name)
        
        # 创建脚本
        script = session.create_script(script_source)
        
        # 收集结果
        results = []
        
        def on_message(message, data):
            if message['type'] == 'send':
                results.append(message['payload'])
                logger.info(f"Hook result: {message['payload']}")
            elif message['type'] == 'error':
                logger.error(f"Hook error: {message['stack']}")
        
        script.on('message', on_message)
        script.load()
        
        # 等待结果
        await asyncio.sleep(duration)
        
        # 分析结果
        return analyze_hook_results(results, target_output)
        
    except ImportError:
        logger.warning("Frida not available")
        return {
            "status": "mock",
            "message": "Frida not installed",
            "results": []
        }
    except Exception as e:
        logger.error(f"Hook failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "results": []
        }


def generate_hook_script(
    class_name: str,
    method_name: str,
    target_output: Optional[str]
) -> str:
    """生成 Frida Hook 脚本"""
    
    target_check = ""
    if target_output:
        target_check = f"""
        if (result && result.toString() === "{target_output}") {{
            console.log("[*] TARGET MATCH!");
            send({{match: true, result: result.toString()}});
        }}
        """
    
    return f"""
Java.perform(function() {{
    console.log("[*] Loading target class: {class_name}");
    
    try {{
        var TargetClass = Java.use("{class_name}");
        
        console.log("[*] Hooking method: {method_name}");
        
        TargetClass.{method_name}.implementation = function() {{
            console.log("[*] {method_name} called");
            
            // 收集参数
            var args = [];
            for (var i = 0; i < arguments.length; i++) {{
                var argValue = arguments[i] ? arguments[i].toString() : "null";
                args.push({{
                    index: i,
                    value: argValue.substring(0, 200),
                    type: typeof arguments[i]
                }});
                console.log("  Arg " + i + ": " + argValue);
            }}
            
            // 调用原方法
            var result = this.{method_name}.apply(this, arguments);
            
            console.log("  Return: " + (result ? result.toString() : "null"));
            
            // 发送结果
            send({{
                method: "{method_name}",
                arguments: args,
                return_value: result ? result.toString().substring(0, 500) : "null",
                timestamp: Date.now()
            }});
            
            {target_check}
            
            return result;
        }};
        
        console.log("[*] Hook installed successfully");
    }} catch (e) {{
        console.log("[!] Hook failed: " + e);
        send({{error: e.toString()}});
    }}
}});
"""


def analyze_hook_results(results: List[Dict], target_output: Optional[str]) -> Dict[str, Any]:
    """分析 Hook 结果"""
    
    if not results:
        return {
            "status": "no_results",
            "message": "No hook results captured",
            "results": []
        }
    
    # 检查是否有匹配
    matches = [r for r in results if r.get("match")]
    
    if matches and target_output:
        return {
            "status": "success",
            "verified": True,
            "matches": len(matches),
            "total_calls": len(results),
            "results": results,
            "confidence": 1.0
        }
    
    # 分析所有调用
    return {
        "status": "success",
        "verified": False,
        "total_calls": len(results),
        "results": results,
        "recommendation": "Review captured calls to identify pattern"
    }


# ----------------------------------------------------------------------------
# Tool 4: generate_fingerprint - 设备指纹生成
# ----------------------------------------------------------------------------

@app.tool("generate_fingerprint")
async def generate_fingerprint(
    platform: str = "android",
    randomize: bool = True,
    consistency_check: bool = True
) -> Dict[str, Any]:
    """
    生成设备指纹
    
    Args:
        platform: 平台类型 (android/ios/web)
        randomize: 是否随机化
        consistency_check: 是否进行一致性检查
    
    Returns:
        设备指纹数据
    """
    logger.info(f"Generating fingerprint for platform: {platform}")
    
    import uuid
    import random
    
    fingerprint = {
        "platform": platform,
        "timestamp": datetime.now().isoformat(),
        "device_id": str(uuid.uuid4()) if randomize else "fixed-device-id",
        "user_agent": generate_user_agent(platform),
        "screen_resolution": generate_screen_resolution(),
        "timezone": generate_timezone(),
        "language": generate_language(),
        "canvas_hash": generate_canvas_hash() if randomize else "fixed-canvas-hash",
        "webgl_hash": generate_webgl_hash() if randomize else "fixed-webgl-hash",
        "audio_hash": generate_audio_hash() if randomize else "fixed-audio-hash"
    }
    
    # 一致性检查
    if consistency_check:
        consistency = check_fingerprint_consistency(fingerprint)
        fingerprint["consistency"] = consistency
    
    return {
        "status": "success",
        "fingerprint": fingerprint
    }


def generate_user_agent(platform: str) -> str:
    """生成 User-Agent"""
    
    if platform == "android":
        android_versions = ["10", "11", "12", "13", "14"]
        chrome_versions = ["116.0.5845.114", "118.0.5993.70", "120.0.6099.210", "123.0.6312.99"]
        
        android_ver = random.choice(android_versions)
        chrome_ver = random.choice(chrome_versions)
        
        return f"Mozilla/5.0 (Linux; Android {android_ver}; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_ver} Mobile Safari/537.36"
    
    elif platform == "ios":
        ios_versions = ["15.0", "16.0", "17.0"]
        safari_versions = ["604.1", "605.1.15"]
        
        ios_ver = random.choice(ios_versions)
        safari_ver = random.choice(safari_versions)
        
        return f"Mozilla/5.0 (iPhone; CPU iPhone OS {ios_ver} like Mac OS X) AppleWebKit/{safari_ver} (KHTML, like Gecko) Version/{ios_ver} Mobile/15E148 Safari/{safari_ver}"
    
    else:  # web
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def generate_screen_resolution() -> str:
    """生成屏幕分辨率"""
    resolutions = ["1920x1080", "2560x1440", "1366x768", "1440x900", "3840x2160"]
    return random.choice(resolutions)


def generate_timezone() -> str:
    """生成时区"""
    timezones = ["Asia/Shanghai", "Asia/Tokyo", "America/New_York", "Europe/London"]
    return random.choice(timezones)


def generate_language() -> str:
    """生成语言"""
    languages = ["zh-CN", "en-US", "ja-JP", "ko-KR"]
    return random.choice(languages)


def generate_canvas_hash() -> str:
    """生成 Canvas 指纹哈希"""
    return hashlib.md5(str(random.random()).encode()).hexdigest()


def generate_webgl_hash() -> str:
    """生成 WebGL 指纹哈希"""
    return hashlib.sha1(str(random.random()).encode()).hexdigest()


def generate_audio_hash() -> str:
    """生成 Audio 指纹哈希"""
    return hashlib.sha256(str(random.random()).encode()).hexdigest()


def check_fingerprint_consistency(fingerprint: Dict) -> Dict[str, Any]:
    """检查指纹一致性"""
    
    issues = []
    
    # 检查 UA 与平台一致性
    ua = fingerprint.get("user_agent", "")
    platform = fingerprint.get("platform", "")
    
    if platform == "android" and "Android" not in ua:
        issues.append("User-Agent does not match Android platform")
    
    if platform == "ios" and "iPhone" not in ua and "iPad" not in ua:
        issues.append("User-Agent does not match iOS platform")
    
    # 检查时间戳合理性
    timestamp = fingerprint.get("timestamp", "")
    try:
        dt = datetime.fromisoformat(timestamp)
        if (datetime.now() - dt).total_seconds() > 3600:
            issues.append("Timestamp is too old")
    except:
        issues.append("Invalid timestamp format")
    
    return {
        "consistent": len(issues) == 0,
        "issues": issues,
        "score": 1.0 - (len(issues) * 0.2)
    }


# ============================================================================
# 启动服务器
# ============================================================================

if __name__ == "__main__":
    logger.info("Starting Reverse Engineering MCP Server...")
    app.run()
