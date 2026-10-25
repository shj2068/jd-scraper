"""
CryptoAnalyzer Skill - 加密算法分析

推断加密算法，生成复现代码
"""

import logging
import hashlib
import hmac
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from skills.base_skill import BaseSkill, SkillConfig, SkillResult

logger = logging.getLogger(__name__)


class CryptoAnalyzerSkill(BaseSkill):
    """
    加密算法分析 Skill
    
    功能：
    - 加密算法特征匹配
    - 签名公式推断
    - 参数组合尝试
    - 复现代码生成
    """
    
    # 已知算法特征库
    ALGORITHM_SIGNATURES = {
        "MD5": {
            "length": 32,
            "charset": "hex",
            "pattern": r'^[a-f0-9]{32}$',
            "hash_func": hashlib.md5
        },
        "SHA1": {
            "length": 40,
            "charset": "hex",
            "pattern": r'^[a-f0-9]{40}$',
            "hash_func": hashlib.sha1
        },
        "SHA256": {
            "length": 64,
            "charset": "hex",
            "pattern": r'^[a-f0-9]{64}$',
            "hash_func": hashlib.sha256
        },
        "SHA512": {
            "length": 128,
            "charset": "hex",
            "pattern": r'^[a-f0-9]{128}$',
            "hash_func": hashlib.sha512
        },
        "HMAC_MD5": {
            "length": 32,
            "charset": "hex",
            "requires_key": True,
            "hash_func": hashlib.md5
        },
        "HMAC_SHA256": {
            "length": 64,
            "charset": "hex",
            "requires_key": True,
            "hash_func": hashlib.sha256
        },
        "AES_ECB": {
            "length_multiple": 16,
            "charset": "base64_or_hex"
        },
        "AES_CBC": {
            "length_multiple": 16,
            "charset": "base64_or_hex",
            "has_iv": True
        },
        "DES": {
            "length_multiple": 8,
            "charset": "base64_or_hex"
        },
        "Base64": {
            "charset": "base64",
            "pattern": r'^[A-Za-z0-9+/]*={0,2}$'
        }
    }
    
    # 常见盐值/密钥
    COMMON_SECRETS = [
        "secret", "key", "salt", "password",
        "jd_secret", "jd_key", "app_secret",
        "api_secret", "sign_key", ""
    ]
    
    def __init__(self, config: Optional[SkillConfig] = None):
        if config is None:
            config = SkillConfig(
                name="crypto-analyzer",
                version="1.0.0",
                description="加密算法分析与复现代码生成",
                timeout=60,
                tags=["crypto", "analysis", "reverse-engineering"],
                dependencies=["traffic-sniffer"]
            )
        
        super().__init__(config)
    
    def validate_input(self, input_data: Dict) -> bool:
        """验证输入"""
        return (
            "suspicious_params" in input_data or
            "analysis" in input_data or
            "request_data" in input_data
        )
    
    def execute_impl(self, input_data: Dict) -> Dict[str, Any]:
        """执行加密分析"""
        
        # 获取可疑参数
        suspicious_params = input_data.get("suspicious_params", [])
        
        # 如果没有直接的 suspicious_params，从 analysis 中提取
        if not suspicious_params and "analysis" in input_data:
            for req_analysis in input_data["analysis"]:
                suspicious_params.extend(req_analysis.get("suspicious_params", []))
        
        if not suspicious_params:
            return {
                "status": "no_params",
                "message": "No suspicious parameters to analyze"
            }
        
        # 获取上下文参数
        context_params = input_data.get("context_params", {})
        request_data = input_data.get("request_data", {})
        
        # 分析每个可疑参数
        analyses = []
        
        for param in suspicious_params:
            analysis = self._analyze_param(param, context_params, request_data)
            if analysis:
                analyses.append(analysis)
        
        # 生成复现代码
        code_blocks = []
        for analysis in analyses:
            if analysis.get("reproduction", {}).get("success"):
                code = self._generate_code(analysis)
                code_blocks.append(code)
        
        return {
            "status": "success",
            "total_analyzed": len(analyses),
            "analyses": analyses,
            "reproduction_code": "\n\n".join(code_blocks),
            "summary": self._generate_summary(analyses)
        }
    
    def _analyze_param(
        self,
        param: Dict,
        context_params: Dict,
        request_data: Dict
    ) -> Optional[Dict[str, Any]]:
        """分析单个参数"""
        
        param_name = param.get("name", "")
        param_value = param.get("value", "")
        characteristics = param.get("characteristics", {})
        
        if not param_value:
            return None
        
        # 推断算法
        candidates = self._match_algorithm(param_value, characteristics)
        
        if not candidates:
            return {
                "param_name": param_name,
                "param_value": param_value[:100],
                "status": "unknown",
                "message": "Could not identify algorithm"
            }
        
        # 选择最佳匹配
        best_algo, confidence = candidates[0]
        
        # 尝试复现
        all_params = {**context_params}
        if request_data:
            all_params.update(request_data.get("query_params", {}))
            all_params.update(request_data.get("headers", {}))
        
        reproduction = self._attempt_reproduction(
            param_name, param_value, all_params, best_algo
        )
        
        return {
            "param_name": param_name,
            "param_value": param_value[:200],
            "inferred_algorithm": best_algo,
            "confidence": confidence,
            "candidates": [{"algorithm": a, "confidence": c} for a, c in candidates],
            "characteristics": characteristics,
            "reproduction": reproduction,
            "formula": reproduction.get("formula"),
            "code": self._generate_code_for_algorithm(best_algo, reproduction)
        }
    
    def _match_algorithm(
        self,
        value: str,
        characteristics: Dict
    ) -> List[Tuple[str, float]]:
        """匹配算法"""
        
        candidates = []
        
        for algo_name, signature in self.ALGORITHM_SIGNATURES.items():
            confidence = 0.0
            
            # 长度匹配
            if "length" in signature:
                if len(value) == signature["length"]:
                    confidence += 0.4
            
            if "length_multiple" in signature:
                if len(value) % signature["length_multiple"] == 0:
                    confidence += 0.3
            
            # 字符集匹配
            if "charset" in signature:
                charset = signature["charset"]
                
                if charset == "hex":
                    if all(c in '0123456789abcdef' for c in value.lower()):
                        confidence += 0.3
                
                elif charset == "base64":
                    if characteristics.get("is_base64"):
                        confidence += 0.4
                
                elif charset == "base64_or_hex":
                    if characteristics.get("is_base64") or characteristics.get("is_hex"):
                        confidence += 0.3
            
            # 正则匹配
            if "pattern" in signature:
                if re.match(signature["pattern"], value.lower()):
                    confidence += 0.3
            
            if confidence > 0.3:
                candidates.append((algo_name, min(confidence, 1.0)))
        
        # 按置信度排序
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return candidates
    
    def _attempt_reproduction(
        self,
        param_name: str,
        param_value: str,
        all_params: Dict[str, str],
        algorithm: str
    ) -> Dict[str, Any]:
        """尝试复现加密结果"""
        
        # 移除目标参数本身
        other_params = {k: v for k, v in all_params.items() if k != param_name}
        
        # 生成参数组合
        combinations = self._generate_combinations(other_params)
        
        # 尝试每种组合
        for combo in combinations:
            # 尝试不同的拼接方式
            for concat_method in ["sorted_join", "direct_join", "json_dump"]:
                result = self._apply_algorithm(algorithm, combo, concat_method)
                
                if result == param_value.lower():
                    return {
                        "success": True,
                        "input_params": list(combo.keys()),
                        "concat_method": concat_method,
                        "formula": self._generate_formula(algorithm, combo, concat_method),
                        "code": self._generate_code_for_algorithm(algorithm, {
                            "input_params": list(combo.keys()),
                            "concat_method": concat_method
                        })
                    }
        
        # 尝试带密钥的算法
        if algorithm.startswith("HMAC"):
            for secret in self.COMMON_SECRETS:
                for combo in combinations[:10]:  # 限制尝试次数
                    result = self._apply_hmac(algorithm, combo, secret)
                    
                    if result == param_value.lower():
                        return {
                            "success": True,
                            "input_params": list(combo.keys()),
                            "secret_key": secret,
                            "formula": f"HMAC({'+'.join(combo.keys())}, key='{secret}')",
                            "code": self._generate_hmac_code(algorithm, combo, secret)
                        }
        
        return {
            "success": False,
            "reason": "No matching combination found",
            "suggestions": [
                "Check if there are hidden parameters",
                "Verify if timestamp is involved",
                "Look for salt/secret values in code",
                "Try different parameter ordering"
            ]
        }
    
    def _generate_combinations(self, params: Dict[str, str]) -> List[Dict[str, str]]:
        """生成参数组合"""
        
        import itertools
        
        combinations = []
        keys = list(params.keys())
        
        # 单参数
        for key in keys:
            combinations.append({key: params[key]})
        
        # 双参数组合
        for pair in itertools.combinations(keys, 2):
            combinations.append({k: params[k] for k in pair})
        
        # 三参数组合（限制数量）
        if len(keys) <= 6:
            for triple in itertools.combinations(keys, 3):
                combinations.append({k: params[k] for k in triple})
        
        return combinations
    
    def _apply_algorithm(
        self,
        algorithm: str,
        params: Dict[str, str],
        concat_method: str = "sorted_join"
    ) -> str:
        """应用算法"""
        
        # 拼接参数
        if concat_method == "sorted_join":
            concat = "".join(str(v) for k, v in sorted(params.items()))
        elif concat_method == "direct_join":
            concat = "".join(str(v) for v in params.values())
        elif concat_method == "json_dump":
            concat = json.dumps(params, separators=(',', ':'), sort_keys=True)
        else:
            concat = "".join(str(v) for v in params.values())
        
        # 获取哈希函数
        sig = self.ALGORITHM_SIGNATURES.get(algorithm, {})
        hash_func = sig.get("hash_func")
        
        if hash_func:
            return hash_func(concat.encode()).hexdigest()
        
        return ""
    
    def _apply_hmac(
        self,
        algorithm: str,
        params: Dict[str, str],
        secret: str
    ) -> str:
        """应用 HMAC 算法"""
        
        concat = "".join(str(v) for v in sorted(params.items()))
        
        if "MD5" in algorithm:
            hash_func = hashlib.md5
        elif "SHA256" in algorithm:
            hash_func = hashlib.sha256
        else:
            hash_func = hashlib.md5
        
        return hmac.new(
            secret.encode(),
            concat.encode(),
            hash_func
        ).hexdigest()
    
    def _generate_formula(
        self,
        algorithm: str,
        params: Dict[str, str],
        concat_method: str
    ) -> str:
        """生成公式"""
        
        if concat_method == "sorted_join":
            param_str = " + ".join(sorted(params.keys()))
        else:
            param_str = " + ".join(params.keys())
        
        return f"{algorithm}({param_str})"
    
    def _generate_code(self, analysis: Dict) -> str:
        """生成复现代码"""
        
        algorithm = analysis.get("inferred_algorithm", "MD5")
        reproduction = analysis.get("reproduction", {})
        
        if not reproduction.get("success"):
            return f"# Could not reproduce {analysis.get('param_name')}"
        
        return self._generate_code_for_algorithm(algorithm, reproduction)
    
    def _generate_code_for_algorithm(
        self,
        algorithm: str,
        reproduction: Dict
    ) -> str:
        """为特定算法生成代码"""
        
        input_params = reproduction.get("input_params", [])
        concat_method = reproduction.get("concat_method", "sorted_join")
        
        if algorithm.startswith("HMAC"):
            secret = reproduction.get("secret_key", "secret")
            return self._generate_hmac_code(algorithm, {k: "" for k in input_params}, secret)
        
        # 生成参数列表
        param_list = ", ".join(input_params)
        
        # 生成拼接代码
        if concat_method == "sorted_join":
            concat_code = '"".join(str(v) for k, v in sorted(params.items()))'
        elif concat_method == "json_dump":
            concat_code = 'json.dumps(params, separators=(",", ":"), sort_keys=True)'
        else:
            concat_code = '"".join(str(v) for v in params.values())'
        
        # 生成哈希代码
        hash_func_map = {
            "MD5": "hashlib.md5",
            "SHA1": "hashlib.sha1",
            "SHA256": "hashlib.sha256",
            "SHA512": "hashlib.sha512"
        }
        
        hash_func = hash_func_map.get(algorithm, "hashlib.md5")
        
        code = f'''
import hashlib
import json

def generate_sign({param_list}):
    """
    Generate {algorithm} signature
    Formula: {reproduction.get('formula', 'N/A')}
    """
    params = {{{', '.join(f'"{k}": {k}' for k in input_params)}}}
    
    # Concatenate parameters
    concat = {concat_code}
    
    # Calculate hash
    return {hash_func}(concat.encode()).hexdigest()
'''
        
        return code
    
    def _generate_hmac_code(
        self,
        algorithm: str,
        params: Dict[str, str],
        secret: str
    ) -> str:
        """生成 HMAC 代码"""
        
        input_params = list(params.keys())
        param_list = ", ".join(input_params)
        
        hash_func_map = {
            "HMAC_MD5": "hashlib.md5",
            "HMAC_SHA256": "hashlib.sha256"
        }
        
        hash_func = hash_func_map.get(algorithm, "hashlib.md5")
        
        code = f'''
import hmac
import hashlib

def generate_hmac_sign({param_list}, secret="{secret}"):
    """
    Generate {algorithm} signature
    """
    params = {{{', '.join(f'"{k}": {k}' for k in input_params)}}}
    concat = "".join(str(v) for k, v in sorted(params.items()))
    
    return hmac.new(
        secret.encode(),
        concat.encode(),
        {hash_func}
    ).hexdigest()
'''
        
        return code
    
    def _generate_summary(self, analyses: List[Dict]) -> Dict[str, Any]:
        """生成分析摘要"""
        
        total = len(analyses)
        reproduced = sum(1 for a in analyses if a.get("reproduction", {}).get("success"))
        
        algorithm_counts = {}
        for a in analyses:
            algo = a.get("inferred_algorithm", "unknown")
            algorithm_counts[algo] = algorithm_counts.get(algo, 0) + 1
        
        avg_confidence = (
            sum(a.get("confidence", 0) for a in analyses) / total
            if total > 0 else 0.0
        )
        
        return {
            "total_analyzed": total,
            "successfully_reproduced": reproduced,
            "reproduction_rate": round(reproduced / max(total, 1), 2),
            "average_confidence": round(avg_confidence, 2),
            "algorithm_distribution": algorithm_counts,
            "high_confidence": [
                a["param_name"] for a in analyses
                if a.get("confidence", 0) >= 0.8
            ]
        }
