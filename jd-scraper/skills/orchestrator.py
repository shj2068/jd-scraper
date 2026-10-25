"""
AI Orchestrator - 智能编排层

协调 MCP Server 和 Skills，实现自动化逆向工程工作流
"""

import logging
import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

from skills.base_skill import BaseSkill, SkillConfig, SkillResult, SkillStatus, SkillRegistry
from skills.traffic_sniffer import TrafficSnifferSkill
from skills.crypto_analyzer import CryptoAnalyzerSkill
from skills.dynamic_verifier import DynamicVerifierSkill
from skills.jd_finance import JDFinanceSkill, create_jd_finance_skill

logger = logging.getLogger(__name__)


@dataclass
class WorkflowStep:
    """工作流步骤"""
    name: str
    skill_name: str
    input_mapping: Dict[str, str] = field(default_factory=dict)
    output_key: Optional[str] = None
    condition: Optional[str] = None
    on_failure: str = "abort"  # abort, skip, retry


@dataclass
class WorkflowResult:
    """工作流执行结果"""
    workflow_name: str
    status: str
    steps_completed: int
    total_steps: int
    step_results: Dict[str, Any] = field(default_factory=dict)
    final_output: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class AIOrchestrator:
    """
    AI 编排器
    
    职责：
    - 意图识别
    - 任务分解
    - Skill 选择与调度
    - 工作流管理
    - 结果聚合
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.registry = SkillRegistry()
        self._init_skills()
        
        # 工作流模板
        self._workflow_templates = {
            "reverse_engineering": self._create_reverse_workflow(),
            "jd_finance_collection": self._create_jd_finance_workflow(),
            "traffic_analysis": self._create_traffic_analysis_workflow(),
            "full_pipeline": self._create_full_pipeline_workflow()
        }
    
    def _init_skills(self):
        """初始化所有 Skill"""
        
        # Traffic Sniffer
        sniffer = TrafficSnifferSkill()
        self.registry.register(sniffer)
        
        # Crypto Analyzer
        analyzer = CryptoAnalyzerSkill()
        self.registry.register(analyzer)
        
        # Dynamic Verifier
        verifier = DynamicVerifierSkill()
        self.registry.register(verifier)
        
        # JD Finance
        jd_finance = create_jd_finance_skill(
            app_key=self.config.get("jd_app_key", ""),
            secret_key=self.config.get("jd_secret_key", "")
        )
        self.registry.register(jd_finance)
        
        logger.info(f"Initialized {len(self.registry.list_skills())} skills")
    
    # ----------------------------------------------------------------
    # 工作流模板
    # ----------------------------------------------------------------
    
    def _create_reverse_workflow(self) -> List[WorkflowStep]:
        """创建逆向工程工作流"""
        return [
            WorkflowStep(
                name="sniff_traffic",
                skill_name="traffic-sniffer",
                input_mapping={"requests": "input.requests"},
                output_key="sniff_result"
            ),
            WorkflowStep(
                name="analyze_crypto",
                skill_name="crypto-analyzer",
                input_mapping={
                    "suspicious_params": "sniff_result.suspicious_params",
                    "request_data": "input.requests[0]"
                },
                output_key="crypto_result"
            ),
            WorkflowStep(
                name="verify_dynamic",
                skill_name="dynamic-verifier",
                input_mapping={
                    "package_name": "input.package_name",
                    "analyses": "crypto_result.analyses"
                },
                output_key="verify_result",
                condition="input.package_name is not None"
            )
        ]
    
    def _create_jd_finance_workflow(self) -> List[WorkflowStep]:
        """创建京东金融采集工作流"""
        return [
            WorkflowStep(
                name="collect_data",
                skill_name="jd-finance",
                input_mapping={
                    "target": "input.target",
                    "cookies": "input.cookies",
                    "params": "input.params"
                },
                output_key="collection_result"
            )
        ]
    
    def _create_traffic_analysis_workflow(self) -> List[WorkflowStep]:
        """创建流量分析工作流"""
        return [
            WorkflowStep(
                name="sniff",
                skill_name="traffic-sniffer",
                input_mapping={"requests": "input.requests"},
                output_key="sniff_result"
            ),
            WorkflowStep(
                name="analyze",
                skill_name="crypto-analyzer",
                input_mapping={
                    "analysis": "sniff_result.analysis",
                    "suspicious_params": "sniff_result.suspicious_params"
                },
                output_key="analysis_result"
            )
        ]
    
    def _create_full_pipeline_workflow(self) -> List[WorkflowStep]:
        """创建完整管道工作流"""
        return (
            self._create_reverse_workflow() +
            self._create_jd_finance_workflow()
        )
    
    # ----------------------------------------------------------------
    # 工作流执行
    # ----------------------------------------------------------------
    
    def execute_workflow(
        self,
        workflow_name: str,
        input_data: Dict[str, Any]
    ) -> WorkflowResult:
        """
        执行工作流
        
        Args:
            workflow_name: 工作流名称
            input_data: 输入数据
        
        Returns:
            工作流执行结果
        """
        start_time = datetime.now()
        
        logger.info(f"Executing workflow: {workflow_name}")
        
        # 获取工作流模板
        steps = self._workflow_templates.get(workflow_name)
        
        if not steps:
            return WorkflowResult(
                workflow_name=workflow_name,
                status="error",
                steps_completed=0,
                total_steps=0,
                error=f"Unknown workflow: {workflow_name}"
            )
        
        # 执行上下文
        context = {"input": input_data}
        completed_steps = 0
        
        # 逐步执行
        for step in steps:
            logger.info(f"Executing step: {step.name} ({step.skill_name})")
            
            # 检查条件
            if step.condition and not self._evaluate_condition(step.condition, context):
                logger.info(f"Skipping step {step.name}: condition not met")
                continue
            
            # 解析输入映射
            step_input = self._resolve_input_mapping(step.input_mapping, context)
            
            # 获取 Skill
            skill = self.registry.get(step.skill_name)
            
            if not skill:
                logger.error(f"Skill not found: {step.skill_name}")
                
                if step.on_failure == "abort":
                    return WorkflowResult(
                        workflow_name=workflow_name,
                        status="failed",
                        steps_completed=completed_steps,
                        total_steps=len(steps),
                        step_results=context,
                        error=f"Skill not found: {step.skill_name}"
                    )
                continue
            
            # 执行 Skill
            result = skill.run(step_input)
            
            # 保存结果
            if step.output_key:
                context[step.output_key] = result.data if result.data else {}
            
            completed_steps += 1
            
            # 检查执行结果
            if result.status != SkillStatus.SUCCESS:
                logger.warning(f"Step {step.name} failed: {result.error}")
                
                if step.on_failure == "abort":
                    return WorkflowResult(
                        workflow_name=workflow_name,
                        status="failed",
                        steps_completed=completed_steps,
                        total_steps=len(steps),
                        step_results=context,
                        error=f"Step {step.name} failed: {result.error}"
                    )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return WorkflowResult(
            workflow_name=workflow_name,
            status="success",
            steps_completed=completed_steps,
            total_steps=len(steps),
            step_results=context,
            final_output=context,
            duration=duration
        )
    
    def _evaluate_condition(self, condition: str, context: Dict) -> bool:
        """评估条件表达式"""
        try:
            # 简单的条件评估
            if "is not None" in condition:
                var_path = condition.replace(" is not None", "").strip()
                value = self._resolve_path(var_path, context)
                return value is not None
            elif "is None" in condition:
                var_path = condition.replace(" is None", "").strip()
                value = self._resolve_path(var_path, context)
                return value is None
            return True
        except:
            return True
    
    def _resolve_input_mapping(
        self,
        mapping: Dict[str, str],
        context: Dict
    ) -> Dict[str, Any]:
        """解析输入映射"""
        resolved = {}
        
        for target_key, source_path in mapping.items():
            value = self._resolve_path(source_path, context)
            resolved[target_key] = value
        
        return resolved
    
    def _resolve_path(self, path: str, context: Dict) -> Any:
        """解析路径表达式"""
        
        parts = path.split(".")
        current = context
        
        for part in parts:
            if current is None:
                return None
            
            # 处理数组索引
            if "[" in part and "]" in part:
                key = part[:part.index("[")]
                index = int(part[part.index("[") + 1:part.index("]")])
                
                if key:
                    current = current.get(key, [])
                if isinstance(current, list) and index < len(current):
                    current = current[index]
                else:
                    return None
            else:
                current = current.get(part) if isinstance(current, dict) else None
        
        return current
    
    # ----------------------------------------------------------------
    # 便捷方法
    # ----------------------------------------------------------------
    
    def analyze_traffic(self, requests: List[Dict]) -> WorkflowResult:
        """分析网络流量"""
        return self.execute_workflow("traffic_analysis", {"requests": requests})
    
    def reverse_engineer(
        self,
        requests: List[Dict],
        package_name: Optional[str] = None
    ) -> WorkflowResult:
        """逆向工程分析"""
        return self.execute_workflow("reverse_engineering", {
            "requests": requests,
            "package_name": package_name
        })
    
    def collect_jd_finance(
        self,
        target: str = "jintiao_quota",
        cookies: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> WorkflowResult:
        """采集京东金融数据"""
        return self.execute_workflow("jd_finance_collection", {
            "target": target,
            "cookies": cookies or {},
            "params": params or {}
        })
    
    def full_pipeline(
        self,
        requests: List[Dict],
        target: str = "jintiao_quota",
        package_name: Optional[str] = None,
        cookies: Optional[Dict] = None
    ) -> WorkflowResult:
        """完整管道：逆向 + 采集"""
        return self.execute_workflow("full_pipeline", {
            "requests": requests,
            "target": target,
            "package_name": package_name,
            "cookies": cookies or {}
        })
    
    def get_stats(self) -> Dict[str, Any]:
        """获取所有 Skill 统计"""
        return self.registry.get_all_stats()
    
    def list_workflows(self) -> List[str]:
        """列出所有可用工作流"""
        return list(self._workflow_templates.keys())


# ============================================================================
# 全局编排器实例
# ============================================================================

_orchestrator: Optional[AIOrchestrator] = None


def get_orchestrator(config: Optional[Dict] = None) -> AIOrchestrator:
    """获取全局编排器实例"""
    global _orchestrator
    
    if _orchestrator is None:
        _orchestrator = AIOrchestrator(config)
    
    return _orchestrator


def reset_orchestrator():
    """重置全局编排器"""
    global _orchestrator
    _orchestrator = None
