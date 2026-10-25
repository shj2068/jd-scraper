"""
JD Finance Skill - 京东金融专用逆向 Skill

专注于京东金融 APP 金条产品的数据采集
"""

import logging
import json
import hashlib
import hmac
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

from skills.base_skill import BaseSkill, SkillConfig

logger = logging.getLogger(__name__)


class JDFinanceSkill(BaseSkill):
    """
    京东金融逆向 Skill
    
    功能：
    - 金条接口分析
    - 签名算法实现
    - 请求构造
    - 数据采集
    """
    
    # 京东金融已知 API 端点
    JD_FINANCE_ENDPOINTS = {
        "jintiao_quota": {
            "url": "https://ms.jr.jd.com/gw/generic/zj/h5/m/latest/creditLimit",
            "method": "POST",
            "description": "金条额度查询"
        },
        "jintiao_rate": {
            "url": "https://ms.jr.jd.com/gw/generic/zj/h5/m/latest/interestRate",
            "method": "POST",
            "description": "金条利率查询"
        },
        "jintiao_apply": {
            "url": "https://ms.jr.jd.com/gw/generic/zj/h5/m/latest/applyInfo",
            "method": "POST",
            "description": "金条申请信息"
        },
        "user_info": {
            "url": "https://ms.jr.jd.com/gw/generic/zj/h5/m/latest/userInfo",
            "method": "POST",
            "description": "用户信息"
        },
        "credit_score": {
            "url": "https://ms.jr.jd.com/gw/generic/zj/h5/m/latest/creditScore",
            "method": "POST",
            "description": "信用评分"
        }
    }
    
    # 京东金融签名参数
    SIGN_PARAMS = [
        "appKey",
        "clientVersion",
        "client",
        "ts",  # timestamp
        "uuid",
        "sign"
    ]
    
    def __init__(self, config: Optional[SkillConfig] = None):
        if config is None:
            config = SkillConfig(
                name="jd-finance",
                version="1.0.0",
                description="京东金融 APP 金条数据采集",
                timeout=30,
                tags=["jd-finance", "jintiao", "data-collection"],
                dependencies=["traffic-sniffer", "crypto-analyzer"]
            )
        
        super().__init__(config)
        
        # 配置
        self._app_key = ""
        self._secret_key = ""
        self._client_version = ""
    
    def configure(self, app_key: str, secret_key: str, client_version: str = "10.5.0"):
        """配置京东金融参数"""
        self._app_key = app_key
        self._secret_key = secret_key
        self._client_version = client_version
    
    def validate_input(self, input_data: Dict) -> bool:
        """验证输入"""
        return "endpoint" in input_data or "target" in input_data
    
    def execute_impl(self, input_data: Dict) -> Dict[str, Any]:
        """执行京东金融数据采集"""
        
        endpoint = input_data.get("endpoint", "")
        target = input_data.get("target", "jintiao_quota")
        
        # 获取端点信息
        endpoint_info = self.JD_FINANCE_ENDPOINTS.get(target)
        
        if not endpoint_info and endpoint:
            endpoint_info = {
                "url": endpoint,
                "method": "POST",
                "description": "Custom endpoint"
            }
        
        if not endpoint_info:
            return {
                "status": "error",
                "message": f"Unknown target: {target}"
            }
        
        # 构造请求
        request = self._build_request(endpoint_info, input_data)
        
        # 发送请求
        response = self._send_request(request)
        
        # 解析响应
        result = self._parse_response(response, target)
        
        return {
            "status": "success",
            "target": target,
            "endpoint": endpoint_info["url"],
            "request": request,
            "response": result,
            "timestamp": datetime.now().isoformat()
        }
    
    def _build_request(self, endpoint_info: Dict, input_data: Dict) -> Dict[str, Any]:
        """构造请求"""
        
        url = endpoint_info["url"]
        method = endpoint_info.get("method", "POST")
        
        # 生成时间戳
        ts = str(int(time.time() * 1000))
        
        # 生成 UUID
        import uuid
        device_uuid = str(uuid.uuid4())
        
        # 构造基础参数
        params = {
            "appKey": self._app_key or "jd_finance_app",
            "clientVersion": self._client_version or "10.5.0",
            "client": "android",
            "ts": ts,
            "uuid": device_uuid
        }
        
        # 添加业务参数
        biz_params = input_data.get("params", {})
        params.update(biz_params)
        
        # 生成签名
        sign = self._generate_sign(params)
        params["sign"] = sign
        
        # 构造请求头
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": self._generate_user_agent(),
            "Referer": "https://m.jd.com/",
            "Origin": "https://m.jd.com"
        }
        
        # 添加 Cookie
        cookies = input_data.get("cookies", {})
        if cookies:
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
            headers["Cookie"] = cookie_str
        
        # 构造请求体
        body = "&".join(f"{k}={v}" for k, v in params.items())
        
        return {
            "url": url,
            "method": method,
            "headers": headers,
            "body": body,
            "params": params
        }
    
    def _generate_sign(self, params: Dict[str, str]) -> str:
        """生成签名"""
        
        # 按 key 排序
        sorted_params = sorted(params.items())
        
        # 拼接参数
        param_str = "&".join(f"{k}={v}" for k, v in sorted_params)
        
        # 添加密钥
        sign_str = param_str + self._secret_key
        
        # MD5 签名
        sign = hashlib.md5(sign_str.encode()).hexdigest()
        
        return sign
    
    def _generate_user_agent(self) -> str:
        """生成 User-Agent"""
        
        return (
            "Mozilla/5.0 (Linux; Android 13; SM-G998B) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.6099.210 Mobile Safari/537.36 "
            "jdapp;android;10.5.0;;;appBuild=96358;"
        )
    
    def _send_request(self, request: Dict) -> Dict[str, Any]:
        """发送请求"""
        
        try:
            import httpx
            
            with httpx.Client(timeout=30) as client:
                if request["method"] == "POST":
                    response = client.post(
                        request["url"],
                        headers=request["headers"],
                        content=request["body"]
                    )
                else:
                    response = client.get(
                        request["url"],
                        headers=request["headers"]
                    )
            
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text,
                "json": self._safe_json(response.text)
            }
            
        except ImportError:
            logger.warning("httpx not available, trying requests")
            
            try:
                import requests
                
                if request["method"] == "POST":
                    response = requests.post(
                        request["url"],
                        headers=request["headers"],
                        data=request["body"]
                    )
                else:
                    response = requests.get(
                        request["url"],
                        headers=request["headers"]
                    )
                
                return {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.text,
                    "json": self._safe_json(response.text)
                }
                
            except Exception as e:
                return {
                    "status_code": 0,
                    "error": str(e)
                }
        
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return {
                "status_code": 0,
                "error": str(e)
            }
    
    def _safe_json(self, text: str) -> Optional[Dict]:
        """安全解析 JSON"""
        try:
            return json.loads(text)
        except:
            return None
    
    def _parse_response(self, response: Dict, target: str) -> Dict[str, Any]:
        """解析响应"""
        
        if response.get("status_code") != 200:
            return {
                "success": False,
                "error": f"HTTP {response.get('status_code')}",
                "message": response.get("error", "Request failed")
            }
        
        json_data = response.get("json")
        
        if not json_data:
            return {
                "success": False,
                "error": "Invalid JSON response"
            }
        
        # 根据目标解析数据
        if target == "jintiao_quota":
            return self._parse_jintiao_quota(json_data)
        elif target == "jintiao_rate":
            return self._parse_jintiao_rate(json_data)
        elif target == "user_info":
            return self._parse_user_info(json_data)
        elif target == "credit_score":
            return self._parse_credit_score(json_data)
        else:
            return {
                "success": True,
                "raw_data": json_data
            }
    
    def _parse_jintiao_quota(self, data: Dict) -> Dict[str, Any]:
        """解析金条额度"""
        
        result = {
            "success": data.get("resultCode") == "0000",
            "message": data.get("resultMsg", ""),
            "data": {}
        }
        
        if result["success"]:
            result_data = data.get("resultData", {})
            result["data"] = {
                "credit_limit": result_data.get("creditLimit", 0),
                "available_limit": result_data.get("availableLimit", 0),
                "used_limit": result_data.get("usedLimit", 0),
                "currency": result_data.get("currency", "CNY"),
                "status": result_data.get("status", ""),
                "update_time": result_data.get("updateTime", "")
            }
        
        return result
    
    def _parse_jintiao_rate(self, data: Dict) -> Dict[str, Any]:
        """解析金条利率"""
        
        result = {
            "success": data.get("resultCode") == "0000",
            "message": data.get("resultMsg", ""),
            "data": {}
        }
        
        if result["success"]:
            result_data = data.get("resultData", {})
            result["data"] = {
                "daily_rate": result_data.get("dailyRate", 0),
                "annual_rate": result_data.get("annualRate", 0),
                "min_rate": result_data.get("minRate", 0),
                "max_rate": result_data.get("maxRate", 0),
                "discount_rate": result_data.get("discountRate", 0)
            }
        
        return result
    
    def _parse_user_info(self, data: Dict) -> Dict[str, Any]:
        """解析用户信息"""
        
        result = {
            "success": data.get("resultCode") == "0000",
            "message": data.get("resultMsg", ""),
            "data": {}
        }
        
        if result["success"]:
            result_data = data.get("resultData", {})
            result["data"] = {
                "user_id": result_data.get("userId", ""),
                "user_name": result_data.get("userName", ""),
                "phone": result_data.get("phone", ""),
                "real_name": result_data.get("realName", ""),
                "id_card": result_data.get("idCard", ""),
                "register_time": result_data.get("registerTime", "")
            }
        
        return result
    
    def _parse_credit_score(self, data: Dict) -> Dict[str, Any]:
        """解析信用评分"""
        
        result = {
            "success": data.get("resultCode") == "0000",
            "message": data.get("resultMsg", ""),
            "data": {}
        }
        
        if result["success"]:
            result_data = data.get("resultData", {})
            result["data"] = {
                "credit_score": result_data.get("creditScore", 0),
                "score_level": result_data.get("scoreLevel", ""),
                "score_trend": result_data.get("scoreTrend", ""),
                "update_time": result_data.get("updateTime", "")
            }
        
        return result


# ============================================================================
# 便捷函数
# ============================================================================

def create_jd_finance_skill(
    app_key: str = "",
    secret_key: str = "",
    client_version: str = "10.5.0"
) -> JDFinanceSkill:
    """创建京东金融 Skill 实例"""
    
    skill = JDFinanceSkill()
    skill.configure(app_key, secret_key, client_version)
    
    return skill


def collect_jintiao_data(
    target: str = "jintiao_quota",
    cookies: Optional[Dict] = None,
    app_key: str = "",
    secret_key: str = ""
) -> Dict[str, Any]:
    """
    便捷函数：采集金条数据
    
    Args:
        target: 采集目标 (jintiao_quota/jintiao_rate/user_info/credit_score)
        cookies: 用户 Cookie
        app_key: 应用 Key
        secret_key: 密钥
    
    Returns:
        采集结果
    """
    
    skill = create_jd_finance_skill(app_key, secret_key)
    
    input_data = {
        "target": target,
        "cookies": cookies or {}
    }
    
    result = skill.run(input_data)
    
    return result.to_dict()
