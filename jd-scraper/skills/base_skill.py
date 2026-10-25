"""
Skills Framework - Base Skill & Skill Registry

提供可复用的 Skill 基类和注册机制
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json
import time
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# Skill 配置与元数据
# ============================================================================

class SkillStatus(Enum):
    """Skill 状态"""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class SkillConfig:
    """Skill 配置"""
    name: str
    version: str = "1.0.0"
    description: str = ""
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    log_level: str = "INFO"
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class SkillResult:
    """Skill 执行结果"""
    status: SkillStatus
    data: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "duration": self.duration,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }


# ============================================================================
# Base Skill 抽象基类
# ============================================================================

class BaseSkill(ABC):
    """
    Skill 基类
    
    提供：
    - 生命周期管理（init, execute, cleanup）
    - 钩子机制（before/after/on_error）
    - 重试与容错
    - 状态追踪
    - 日志记录
    """
    
    def __init__(self, config: SkillConfig):
        self.config = config
        self.logger = logging.getLogger(f"skill.{config.name}")
        self.logger.setLevel(getattr(logging, config.log_level))
        
        # 状态管理
        self._status = SkillStatus.IDLE
        self._execution_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._last_result: Optional[SkillResult] = None
        
        # 钩子注册
        self._hooks: Dict[str, List[Callable]] = {
            "before_execute": [],
            "after_execute": [],
            "on_error": [],
            "on_retry": []
        }
        
        # 扩展点
        self._extensions: Dict[str, Any] = {}
    
    # ----------------------------------------------------------------
    # 抽象方法（子类必须实现）
    # ----------------------------------------------------------------
    
    @abstractmethod
    def validate_input(self, input_data: Dict) -> bool:
        """验证输入参数"""
        pass
    
    @abstractmethod
    def execute_impl(self, input_data: Dict) -> Any:
        """核心执行逻辑（子类实现）"""
        pass
    
    # ----------------------------------------------------------------
    # 生命周期方法
    # ----------------------------------------------------------------
    
    def on_init(self):
        """初始化钩子（可选覆盖）"""
        pass
    
    def on_cleanup(self):
        """清理钩子（可选覆盖）"""
        pass
    
    # ----------------------------------------------------------------
    # 钩子注册
    # ----------------------------------------------------------------
    
    def register_hook(self, event: str, callback: Callable):
        """注册钩子函数"""
        if event in self._hooks:
            self._hooks[event].append(callback)
            self.logger.debug(f"Registered hook: {event}")
        else:
            self.logger.warning(f"Unknown hook event: {event}")
    
    def unregister_hook(self, event: str, callback: Callable):
        """取消注册钩子"""
        if event in self._hooks and callback in self._hooks[event]:
            self._hooks[event].remove(callback)
    
    def _trigger_hook(self, event: str, **kwargs):
        """触发钩子"""
        for callback in self._hooks.get(event, []):
            try:
                callback(**kwargs)
            except Exception as e:
                self.logger.error(f"Hook {event} failed: {e}")
    
    # ----------------------------------------------------------------
    # 核心运行逻辑
    # ----------------------------------------------------------------
    
    def run(self, input_data: Dict) -> SkillResult:
        """
        运行 Skill（完整生命周期）
        
        流程：
        1. 验证输入
        2. 触发 before_execute 钩子
        3. 执行核心逻辑（带重试）
        4. 触发 after_execute 钩子
        5. 返回结果
        """
        start_time = time.time()
        self._status = SkillStatus.RUNNING
        self._execution_count += 1
        
        self.logger.info(f"[{self.config.name}] Execution #{self._execution_count} started")
        
        # Step 1: 验证输入
        if not self.validate_input(input_data):
            return self._make_result(
                SkillStatus.FAILED,
                error="Input validation failed",
                duration=time.time() - start_time
            )
        
        # Step 2: 触发前置钩子
        self._trigger_hook("before_execute", input=input_data, skill=self)
        
        # Step 3: 执行（带重试）
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                result_data = self.execute_impl(input_data)
                
                duration = time.time() - start_time
                self._status = SkillStatus.SUCCESS
                self._success_count += 1
                
                result = SkillResult(
                    status=SkillStatus.SUCCESS,
                    data=result_data,
                    duration=duration,
                    metadata={
                        "attempt": attempt + 1,
                        "execution_count": self._execution_count
                    }
                )
                
                self._last_result = result
                
                # 触发后置钩子
                self._trigger_hook("after_execute", result=result, skill=self)
                
                self.logger.info(
                    f"[{self.config.name}] Completed in {duration:.2f}s "
                    f"(attempt {attempt + 1})"
                )
                
                return result
                
            except Exception as e:
                last_error = str(e)
                self.logger.warning(
                    f"[{self.config.name}] Attempt {attempt + 1} failed: {e}"
                )
                
                # 触发错误钩子
                self._trigger_hook(
                    "on_error",
                    error=e,
                    attempt=attempt,
                    skill=self
                )
                
                if attempt < self.config.max_retries - 1:
                    # 触发重试钩子
                    self._trigger_hook(
                        "on_retry",
                        attempt=attempt + 1,
                        max_retries=self.config.max_retries,
                        skill=self
                    )
                    time.sleep(self.config.retry_delay)
        
        # 所有重试都失败
        duration = time.time() - start_time
        self._status = SkillStatus.FAILED
        self._failure_count += 1
        
        result = self._make_result(
            SkillStatus.FAILED,
            error=last_error,
            duration=duration
        )
        self._last_result = result
        
        return result
    
    def _make_result(
        self,
        status: SkillStatus,
        data: Any = None,
        error: Optional[str] = None,
        duration: float = 0.0
    ) -> SkillResult:
        """创建结果对象"""
        return SkillResult(
            status=status,
            data=data,
            error=error,
            duration=duration
        )
    
    # ----------------------------------------------------------------
    # 状态与统计
    # ----------------------------------------------------------------
    
    @property
    def status(self) -> SkillStatus:
        return self._status
    
    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "name": self.config.name,
            "version": self.config.version,
            "execution_count": self._execution_count,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "success_rate": (
                self._success_count / self._execution_count
                if self._execution_count > 0 else 0.0
            ),
            "last_result": self._last_result.to_dict() if self._last_result else None
        }
    
    def reset_stats(self):
        """重置统计"""
        self._execution_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._last_result = None


# ============================================================================
# Skill Registry - 注册中心
# ============================================================================

class SkillRegistry:
    """
    Skill 注册中心
    
    管理所有已注册的 Skill，提供：
    - 注册/注销
    - 查找/发现
    - 依赖检查
    - 批量执行
    """
    
    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
        self._skill_classes: Dict[str, type] = {}
        self.logger = logging.getLogger("skill_registry")
    
    def register(self, skill: BaseSkill) -> bool:
        """注册 Skill 实例"""
        name = skill.config.name
        
        if name in self._skills:
            self.logger.warning(f"Skill '{name}' already registered, overwriting")
        
        self._skills[name] = skill
        self.logger.info(f"Registered skill: {name} v{skill.config.version}")
        
        return True
    
    def register_class(self, name: str, skill_class: type) -> bool:
        """注册 Skill 类（延迟实例化）"""
        self._skill_classes[name] = skill_class
        self.logger.info(f"Registered skill class: {name}")
        return True
    
    def unregister(self, name: str) -> bool:
        """注销 Skill"""
        if name in self._skills:
            del self._skills[name]
            self.logger.info(f"Unregistered skill: {name}")
            return True
        return False
    
    def get(self, name: str) -> Optional[BaseSkill]:
        """获取 Skill 实例"""
        return self._skills.get(name)
    
    def create(self, name: str, config: Optional[SkillConfig] = None) -> Optional[BaseSkill]:
        """创建 Skill 实例"""
        if name not in self._skill_classes:
            self.logger.error(f"Skill class '{name}' not found")
            return None
        
        skill_class = self._skill_classes[name]
        
        if config is None:
            config = SkillConfig(name=name)
        
        skill = skill_class(config)
        self.register(skill)
        
        return skill
    
    def list_skills(self) -> List[Dict[str, Any]]:
        """列出所有已注册的 Skill"""
        skills = []
        
        for name, skill in self._skills.items():
            skills.append({
                "name": name,
                "version": skill.config.version,
                "description": skill.config.description,
                "tags": skill.config.tags,
                "status": skill.status.value,
                "stats": skill.stats
            })
        
        return skills
    
    def find_by_tag(self, tag: str) -> List[BaseSkill]:
        """按标签查找 Skill"""
        return [
            skill for skill in self._skills.values()
            if tag in skill.config.tags
        ]
    
    def find_by_dependency(self, dependency: str) -> List[BaseSkill]:
        """查找依赖指定 Skill 的 Skill"""
        return [
            skill for skill in self._skills.values()
            if dependency in skill.config.dependencies
        ]
    
    def check_dependencies(self, name: str) -> bool:
        """检查 Skill 的依赖是否满足"""
        skill = self._skills.get(name)
        if not skill:
            return False
        
        for dep in skill.config.dependencies:
            if dep not in self._skills:
                self.logger.error(
                    f"Skill '{name}' depends on '{dep}' which is not registered"
                )
                return False
        
        return True
    
    def execute_pipeline(
        self,
        skill_names: List[str],
        input_data: Dict,
        pass_results: bool = True
    ) -> List[SkillResult]:
        """
        按顺序执行 Skill 管道
        
        Args:
            skill_names: Skill 名称列表（按执行顺序）
            input_data: 初始输入数据
            pass_results: 是否将前一个结果传递给下一个
        
        Returns:
            所有 Skill 的执行结果
        """
        results = []
        current_input = input_data.copy()
        
        for name in skill_names:
            skill = self._skills.get(name)
            
            if not skill:
                self.logger.error(f"Skill '{name}' not found, skipping")
                results.append(SkillResult(
                    status=SkillStatus.FAILED,
                    error=f"Skill '{name}' not found"
                ))
                continue
            
            # 检查依赖
            if not self.check_dependencies(name):
                results.append(SkillResult(
                    status=SkillStatus.FAILED,
                    error=f"Dependencies not satisfied for '{name}'"
                ))
                continue
            
            # 执行
            result = skill.run(current_input)
            results.append(result)
            
            # 如果失败，停止管道
            if result.status != SkillStatus.SUCCESS:
                self.logger.error(
                    f"Pipeline stopped at '{name}': {result.error}"
                )
                break
            
            # 传递结果
            if pass_results and result.data:
                if isinstance(result.data, dict):
                    current_input.update(result.data)
                else:
                    current_input["previous_result"] = result.data
        
        return results
    
    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有 Skill 的统计"""
        return {
            name: skill.stats
            for name, skill in self._skills.items()
        }


# 全局注册中心实例
global_registry = SkillRegistry()
