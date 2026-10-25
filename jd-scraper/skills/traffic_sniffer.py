"""
TrafficSniffer Skill - 流量嗅探

自动嗅探网络请求，识别可疑加密参数，生成参数分类报告
"""

import logging
import re
import math
import json
import base64
from typing import Dict, List, Any, Optional
from collections import Counter
from datetime import datetime

from skills.base_skill import BaseSkill, SkillConfig, SkillResult, SkillStatus

logger = logging.getLogger(__name__)


class TrafficSnifferSkill(BaseSkill):
    """
    流量嗅探 Skill
    
    功能：
    - 捕获和分析 HTTP 请求
    - 识别可疑加密参数
    - 参数特征分析
    - 生成嗅探报告
    """
    
    # 可疑参数命名模式
    SUSPICIOUS_PATTERNS = [
        (r'sign[a-z_]*$', 'signature_like'),
        (r'signature[a-z_]*$', 'signature_like'),
        (r'token[a-z_]*$', 'token_like'),
        (r'encrypt[a-z_]*$', 'encryption_like'),
        (r'hash[a-z_]*$', 'hash_like'),
        (r'cipher[a-z_]*$', 'cipher_like'),
        (r'h5st$', 'jd_h5st'),
        (r'\bst$', 'jd_st'),
        (r'\bsv$', 'jd_sv'),
        (r'uuid$', 'uuid_like'),
        (r'timestamp$', 'timestamp_like'),
        (r'nonce$', 'nonce_like'),
        (r'app_?key$', 'app_key'),
        (r'secret$', 'secret_like'),
        (r'pin$', 'jd_pin'),
        (r'client[a-z_]*$', 'client_like'),
    ]
    
    def __init__(self, config: Optional[SkillConfig] = None):
        if config is None:
            config = SkillConfig(
                name="traffic-sniffer",
                version="1.0.0",
                description="网络流量嗅探与可疑参数识别",
                timeout=120,
                tags=["traffic", "sniffing", "analysis"],
                dependencies=[]
            )
        
        super().__init__(config)
        
        # 嗅探状态
        self._captured_requests: List[Dict] = []
        self._analysis_cache: Dict[str, Any] = {}
    
    def validate_input(self, input_data: Dict) -> bool:
        """验证输入"""
        # 至少需要 requests 列表或单个 request
        if "requests" in input_data:
            return isinstance(input_data["requests"], list)
        elif "request" in input_data:
            return isinstance(input_data["request"], dict)
        elif "url" in input_data:
            return True
        return False
    
    def execute_impl(self, input_data: Dict) -> Dict[str, Any]:
        """执行嗅探分析"""
        
        # 获取请求数据
        requests = input_data.get("requests", [])
        if not requests and "request" in input_data:
            requests = [input_data["request"]]
        
        if not requests:
            return {
                "status": "no_data",
                "message": "No requests to analyze"
            }
        
        # 分析每个请求
        analysis_results = []
        all_suspicious_params = []
        
        for req in requests:
            result = self._analyze_request(req)
            analysis_results.append(result)
            
            if result.get("suspicious_params"):
                all_suspicious_params.extend(result["suspicious_params"])
        
        # 生成报告
        report = self._generate_report(analysis_results, all_suspicious_params)
        
        return {
            "status": "success",
            "total_requests": len(requests),
            "analyzed_requests": len(analysis_results),
            "suspicious_params_count": len(all_suspicious_params),
            "analysis": analysis_results,
            "suspicious_params": all_suspicious_params,
            "report": report
        }
    
    def _analyze_request(self, request: Dict) -> Dict[str, Any]:
        """分析单个请求"""
        
        result = {
            "url": request.get("url", ""),
            "method": request.get("method", "GET"),
            "timestamp": request.get("timestamp", datetime.now().isoformat()),
            "suspicious_params": [],
            "param_classification": {},
            "risk_score": 0.0
        }
        
        # 收集所有参数
        all_params = {}
        
        # Query 参数
        query_params = request.get("query_params", {})
        all_params.update(query_params)
        
        # Headers
        headers = request.get("headers", {})
        
        # Body 参数
        body = request.get("body")
        if body:
            try:
                if isinstance(body, str):
                    body_params = json.loads(body)
                else:
                    body_params = body
                all_params.update(body_params)
            except (json.JSONDecodeError, TypeError):
                # 尝试 form-urlencoded
                try:
                    from urllib.parse import parse_qs
                    parsed = parse_qs(body)
                    all_params.update({k: v[0] for k, v in parsed.items()})
                except:
                    pass
        
        # 分类参数
        for key, value in all_params.items():
            if not isinstance(value, str):
                continue
            
            classification = self._classify_param(key, value)
            result["param_classification"][key] = classification
            
            # 检查是否可疑
            if classification.get("suspicious", False):
                suspicious_info = {
                    "name": key,
                    "value": value[:200],
                    "reasons": classification.get("reasons", []),
                    "characteristics": self._analyze_characteristics(value),
                    "classification": classification
                }
                result["suspicious_params"].append(suspicious_info)
        
        # 计算风险分数
        result["risk_score"] = self._calculate_risk_score(result)
        
        return result
    
    def _classify_param(self, name: str, value: str) -> Dict[str, Any]:
        """分类参数"""
        
        classification = {
            "name": name,
            "type": "unknown",
            "suspicious": False,
            "reasons": [],
            "confidence": 0.0
        }
        
        # 1. 命名模式匹配
        for pattern, param_type in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, name.lower()):
                classification["type"] = param_type
                classification["suspicious"] = True
                classification["reasons"].append(f"naming_pattern:{pattern}")
                classification["confidence"] = max(classification["confidence"], 0.7)
                break
        
        # 2. 值特征分析
        value_analysis = self._analyze_value(value)
        
        if value_analysis.get("is_encrypted"):
            classification["suspicious"] = True
            classification["reasons"].append("value_encrypted_like")
            classification["confidence"] = max(classification["confidence"], 0.6)
        
        if value_analysis.get("is_hash"):
            classification["type"] = "hash"
            classification["suspicious"] = True
            classification["reasons"].append(f"value_hash:{value_analysis.get('hash_type')}")
            classification["confidence"] = max(classification["confidence"], 0.8)
        
        if value_analysis.get("is_timestamp"):
            classification["type"] = "timestamp"
            classification["reasons"].append("value_timestamp")
        
        if value_analysis.get("is_uuid"):
            classification["type"] = "uuid"
            classification["reasons"].append("value_uuid")
        
        # 3. 上下文推断
        if "sign" in name.lower() and len(value) >= 16:
            classification["type"] = "signature"
            classification["suspicious"] = True
            classification["reasons"].append("context_signature")
            classification["confidence"] = max(classification["confidence"], 0.85)
        
        return classification
    
    def _analyze_value(self, value: str) -> Dict[str, Any]:
        """分析值的特征"""
        
        analysis = {
            "length": len(value),
            "is_encrypted": False,
            "is_hash": False,
            "hash_type": None,
            "is_timestamp": False,
            "is_uuid": False,
            "is_base64": False,
            "entropy": 0.0,
            "charset": "unknown"
        }
        
        if not value:
            return analysis
        
        # 熵值分析
        analysis["entropy"] = self._calculate_entropy(value)
        
        # 字符集检测
        analysis["charset"] = self._detect_charset(value)
        
        # Hash 检测
        if re.match(r'^[a-f0-9]{32}$', value.lower()):
            analysis["is_hash"] = True
            analysis["hash_type"] = "MD5"
            analysis["is_encrypted"] = True
        elif re.match(r'^[a-f0-9]{40}$', value.lower()):
            analysis["is_hash"] = True
            analysis["hash_type"] = "SHA1"
            analysis["is_encrypted"] = True
        elif re.match(r'^[a-f0-9]{64}$', value.lower()):
            analysis["is_hash"] = True
            analysis["hash_type"] = "SHA256"
            analysis["is_encrypted"] = True
        
        # Base64 检测
        if self._is_base64(value):
            analysis["is_base64"] = True
            if len(value) % 16 == 0:
                analysis["is_encrypted"] = True
        
        # 时间戳检测
        try:
            ts = int(value)
            if 1577836800 <= ts <= 1893456000:  # 2020-2030
                analysis["is_timestamp"] = True
        except:
            pass
        
        # UUID 检测
        uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
        if re.match(uuid_pattern, value.lower()):
            analysis["is_uuid"] = True
        
        # 高熵值判断
        if analysis["entropy"] > 4.0 and len(value) >= 16:
            analysis["is_encrypted"] = True
        
        return analysis
    
    def _analyze_characteristics(self, value: str) -> Dict[str, Any]:
        """分析参数值特征"""
        
        return {
            "length": len(value),
            "charset": self._detect_charset(value),
            "entropy": round(self._calculate_entropy(value), 4),
            "is_base64": self._is_base64(value),
            "is_hex": bool(re.match(r'^[a-fA-F0-9]+$', value)) if value else False,
            "is_numeric": value.isdigit() if value else False,
            "unique_chars": len(set(value)),
            "char_distribution": dict(Counter(value).most_common(10))
        }
    
    def _calculate_entropy(self, s: str) -> float:
        """计算信息熵"""
        if not s:
            return 0.0
        
        counter = Counter(s)
        entropy = 0.0
        length = len(s)
        
        for count in counter.values():
            probability = count / length
            if probability > 0:
                entropy -= probability * math.log2(probability)
        
        return entropy
    
    def _detect_charset(self, value: str) -> str:
        """检测字符集"""
        if not value:
            return "empty"
        
        if all(c in '0123456789abcdef' for c in value.lower()):
            return "hex_lowercase"
        elif all(c in '0123456789abcdefABCDEF' for c in value):
            return "hex_mixed"
        elif self._is_base64(value):
            return "base64"
        elif value.isalnum():
            return "alphanumeric"
        elif value.isdigit():
            return "numeric"
        elif value.isalpha():
            return "alpha"
        else:
            return "mixed"
    
    def _is_base64(self, value: str) -> bool:
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
    
    def _calculate_risk_score(self, result: Dict) -> float:
        """计算风险分数"""
        
        score = 0.0
        
        # 可疑参数数量
        suspicious_count = len(result.get("suspicious_params", []))
        score += min(suspicious_count * 0.2, 0.5)
        
        # 最高置信度
        max_confidence = max(
            (p.get("classification", {}).get("confidence", 0)
             for p in result.get("suspicious_params", [])),
            default=0.0
        )
        score += max_confidence * 0.3
        
        # 参数类型多样性
        types = set(
            p.get("classification", {}).get("type", "unknown")
            for p in result.get("suspicious_params", [])
        )
        if len(types) > 2:
            score += 0.2
        
        return min(round(score, 2), 1.0)
    
    def _generate_report(
        self,
        analysis_results: List[Dict],
        suspicious_params: List[Dict]
    ) -> Dict[str, Any]:
        """生成嗅探报告"""
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_requests": len(analysis_results),
                "total_suspicious_params": len(suspicious_params),
                "avg_risk_score": round(
                    sum(r.get("risk_score", 0) for r in analysis_results) /
                    max(len(analysis_results), 1),
                    2
                )
            },
            "param_types": {},
            "high_risk_params": [],
            "recommendations": []
        }
        
        # 统计参数类型
        for param in suspicious_params:
            param_type = param.get("classification", {}).get("type", "unknown")
            if param_type not in report["param_types"]:
                report["param_types"][param_type] = 0
            report["param_types"][param_type] += 1
        
        # 高风险参数
        for param in suspicious_params:
            confidence = param.get("classification", {}).get("confidence", 0)
            if confidence >= 0.7:
                report["high_risk_params"].append({
                    "name": param["name"],
                    "type": param.get("classification", {}).get("type"),
                    "confidence": confidence,
                    "reasons": param.get("reasons", [])
                })
        
        # 生成建议
        if not suspicious_params:
            report["recommendations"].append("未发现可疑加密参数")
        else:
            report["recommendations"].append(
                f"发现 {len(suspicious_params)} 个可疑参数，建议进一步分析"
            )
            
            if report["high_risk_params"]:
                report["recommendations"].append(
                    f"其中 {len(report['high_risk_params'])} 个高置信度参数需要重点关注"
                )
            
            # 检查常见 JD 参数
            jd_params = [p for p in suspicious_params
                        if p.get("classification", {}).get("type", "").startswith("jd_")]
            if jd_params:
                report["recommendations"].append(
                    "检测到京东特有参数（h5st/st/sv），建议使用 JD 专用逆向策略"
                )
        
        return report
