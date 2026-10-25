"""
DynamicVerifier Skill - 动态验证

使用 Frida 动态验证加密算法
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

from skills.base_skill import BaseSkill, SkillConfig

logger = logging.getLogger(__name__)


class DynamicVerifierSkill(BaseSkill):
    """
    动态验证 Skill
    
    功能：
    - Frida 动态 Hook
    - 参数组合验证
    - 算法正确性确认
    - 运行时行为分析
    """
    
    def __init__(self, config: Optional[SkillConfig] = None):
        if config is None:
            config = SkillConfig(
                name="dynamic-verifier",
                version="1.0.0",
                description="Frida 动态验证加密算法",
                timeout=60,
                tags=["frida", "dynamic", "verification"],
                dependencies=["crypto-analyzer"]
            )
        
        super().__init__(config)
    
    def validate_input(self, input_data: Dict) -> bool:
        """验证输入"""
        return (
            "package_name" in input_data and
            "analyses" in input_data
        )
    
    def execute_impl(self, input_data: Dict) -> Dict[str, Any]:
        """执行动态验证"""
        
        package_name = input_data["package_name"]
        analyses = input_data.get("analyses", [])
        duration = input_data.get("duration", 10)
        
        if not analyses:
            return {
                "status": "no_analyses",
                "message": "No algorithm analyses to verify"
            }
        
        # 对每个分析结果进行动态验证
        verifications = []
        
        for analysis in analyses:
            if analysis.get("confidence", 0) < 0.5:
                continue
            
            verification = self._verify_single(
                package_name, analysis, duration
            )
            verifications.append(verification)
        
        return {
            "status": "success",
            "total_verified": len(verifications),
            "verifications": verifications,
            "summary": self._generate_summary(verifications)
        }
    
    def _verify_single(
        self,
        package_name: str,
        analysis: Dict,
        duration: int
    ) -> Dict[str, Any]:
        """验证单个算法"""
        
        param_name = analysis.get("param_name", "")
        algorithm = analysis.get("inferred_algorithm", "")
        param_value = analysis.get("param_value", "")
        
        logger.info(f"Verifying {param_name} with {algorithm}")
        
        try:
            import frida
            
            # 生成验证脚本
            script_source = self._generate_verification_script(
                analysis, param_value
            )
            
            # 连接设备
            device = frida.get_usb_device()
            
            # 附加到进程
            try:
                pid = device.spawn([package_name])
                session = device.attach(pid)
                device.resume(pid)
            except:
                session = device.attach(package_name)
            
            # 创建脚本
            script = session.create_script(script_source)
            
            # 收集结果
            results = []
            
            def on_message(message, data):
                if message['type'] == 'send':
                    results.append(message['payload'])
                elif message['type'] == 'error':
                    logger.error(f"Script error: {message['stack']}")
            
            script.on('message', on_message)
            script.load()
            
            # 等待结果
            import time
            time.sleep(duration)
            
            # 分析结果
            return self._analyze_verification_results(
                results, analysis, param_value
            )
            
        except ImportError:
            logger.warning("Frida not available, using mock verification")
            return {
                "param_name": param_name,
                "algorithm": algorithm,
                "status": "mock",
                "message": "Frida not installed, mock verification only",
                "verified": False
            }
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return {
                "param_name": param_name,
                "algorithm": algorithm,
                "status": "error",
                "error": str(e),
                "verified": False
            }
    
    def _generate_verification_script(
        self,
        analysis: Dict,
        expected_output: str
    ) -> str:
        """生成验证脚本"""
        
        # 尝试推断目标类和方法
        class_name = self._infer_target_class(analysis)
        method_name = self._infer_target_method(analysis)
        
        return f'''
Java.perform(function() {{
    console.log("[*] Starting verification for {analysis.get('param_name')}");
    
    try {{
        var TargetClass = Java.use("{class_name}");
        
        TargetClass.{method_name}.implementation = function() {{
            console.log("[*] {{method_name}} called");
            
            // 收集参数
            var args = [];
            for (var i = 0; i < arguments.length; i++) {{
                var argStr = arguments[i] ? arguments[i].toString() : "null";
                args.push({{
                    index: i,
                    value: argStr.substring(0, 500),
                    type: typeof arguments[i]
                }});
            }}
            
            // 调用原方法
            var result = this.{method_name}.apply(this, arguments);
            var resultStr = result ? result.toString() : "null";
            
            console.log("[*] Result: " + resultStr);
            
            // 检查是否匹配
            var match = (resultStr === "{expected_output}");
            
            // 发送结果
            send({{
                param_name: "{analysis.get('param_name')}",
                algorithm: "{analysis.get('inferred_algorithm')}",
                arguments: args,
                return_value: resultStr.substring(0, 500),
                expected: "{expected_output}",
                match: match,
                timestamp: Date.now()
            }});
            
            return result;
        }};
        
        console.log("[*] Hook installed: {class_name}.{method_name}");
    }} catch (e) {{
        console.log("[!] Hook failed: " + e);
        send({{error: e.toString()}});
    }}
}});
'''
    
    def _infer_target_class(self, analysis: Dict) -> str:
        """推断目标类名"""
        
        # 从分析结果中推断
        param_name = analysis.get("param_name", "").lower()
        
        # 常见模式
        if "sign" in param_name or "h5st" in param_name:
            return "com.jd.framework.sign.SignUtils"
        elif "encrypt" in param_name:
            return "com.jd.framework.crypto.CryptoUtils"
        elif "token" in param_name:
            return "com.jd.framework.auth.TokenManager"
        else:
            return "com.jd.framework.utils.Utils"
    
    def _infer_target_method(self, analysis: Dict) -> str:
        """推断目标方法名"""
        
        param_name = analysis.get("param_name", "").lower()
        
        if "sign" in param_name or "h5st" in param_name:
            return "generateSign"
        elif "encrypt" in param_name:
            return "encrypt"
        elif "hash" in param_name:
            return "hash"
        else:
            return "generate"
    
    def _analyze_verification_results(
        self,
        results: List[Dict],
        analysis: Dict,
        expected_output: str
    ) -> Dict[str, Any]:
        """分析验证结果"""
        
        param_name = analysis.get("param_name", "")
        algorithm = analysis.get("inferred_algorithm", "")
        
        if not results:
            return {
                "param_name": param_name,
                "algorithm": algorithm,
                "status": "no_results",
                "verified": False,
                "message": "No verification results captured"
            }
        
        # 检查匹配
        matches = [r for r in results if r.get("match")]
        
        if matches:
            return {
                "param_name": param_name,
                "algorithm": algorithm,
                "status": "success",
                "verified": True,
                "matches": len(matches),
                "total_calls": len(results),
                "confidence": 1.0,
                "captured_args": matches[0].get("arguments", []),
                "return_value": matches[0].get("return_value", ""),
                "message": f"Algorithm verified: {algorithm}"
            }
        
        # 未匹配但有结果
        return {
            "param_name": param_name,
            "algorithm": algorithm,
            "status": "partial",
            "verified": False,
            "total_calls": len(results),
            "captured_results": results[:5],
            "message": "Captured calls but no exact match. Review manually.",
            "suggestions": [
                "Check if parameters are in correct order",
                "Verify if there are additional hidden inputs",
                "Confirm the expected output value"
            ]
        }
    
    def _generate_summary(self, verifications: List[Dict]) -> Dict[str, Any]:
        """生成验证摘要"""
        
        total = len(verifications)
        verified = sum(1 for v in verifications if v.get("verified"))
        
        return {
            "total_verified": total,
            "successfully_verified": verified,
            "verification_rate": round(verified / max(total, 1), 2),
            "verified_params": [
                v["param_name"] for v in verifications if v.get("verified")
            ],
            "failed_params": [
                v["param_name"] for v in verifications if not v.get("verified")
            ]
        }
