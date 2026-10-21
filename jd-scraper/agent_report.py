#!/usr/bin/env python3
"""
智能体报告生成模块

生成采集报告、嗅探报告、监控报告等多种格式的文档。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from python.utils import setup_logger

logger = setup_logger("agent_report")


class AgentReportGenerator:
    """智能体报告生成器"""

    def __init__(self, output_dir: str = "./data/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_full_report(self, pipeline_result: Dict) -> str:
        """
        生成完整流水线报告（Markdown 格式）

        Args:
            pipeline_result: run_full_pipeline() 的返回值

        Returns:
            Markdown 格式报告
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        summary = pipeline_result.get("summary", {})

        lines = [
            "# AI+JS逆向京东工业网数据采集智能体 — 运行报告",
            "",
            f"**生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**智能体版本**: 2.0.0",
            f"**运行耗时**: {summary.get('elapsed_seconds', 0):.1f} 秒",
            "",
            "---",
            "",
            "## 执行摘要",
            "",
            f"| 指标 | 值 |",
            f"|------|-----|",
            f"| 当前阶段 | {summary.get('phase', 'unknown')} |",
            f"| JSRPC 状态 | {'正常' if summary.get('jsrpc_healthy') else '不可用'} |",
            f"| h5st 版本 | {summary.get('h5st_version', '未检测')} |",
            f"| 签名策略 | {summary.get('sign_strategy', '未选择')} |",
            f"| 总请求数 | {summary.get('total_requests', 0)} |",
            f"| 成功率 | {summary.get('success_rate', '0.0%')} |",
            f"| 发现 API 数 | {summary.get('discovered_apis', 0)} |",
            f"| 告警数 | {summary.get('alerts', 0)} |",
            "",
        ]

        # 各阶段详情
        for stage in pipeline_result.get("pipeline", []):
            phase_num = stage.get("phase", "?")
            result = stage.get("result", {})
            phase_name = result.get("phase", "unknown")

            lines.extend([
                "---",
                "",
                f"## Phase {phase_num}: {self._phase_title(phase_name)}",
                "",
            ])

            if phase_name == "environment_diagnosis":
                lines.extend(self._format_diagnosis(result))
            elif phase_name == "service_startup":
                lines.extend(self._format_startup(result))
            elif phase_name == "api_sniffing":
                lines.extend(self._format_sniffing(result))
            elif phase_name == "strategy_selection":
                lines.extend(self._format_strategy(result))
            elif phase_name == "collection":
                lines.extend(self._format_collection(result))
            elif phase_name == "monitoring":
                lines.extend(self._format_monitoring(result))

        # 错误日志
        errors = summary.get("errors", [])
        if errors:
            lines.extend([
                "---",
                "",
                "## 错误日志",
                "",
            ])
            for err in errors:
                lines.append(f"- ⚠️ {err}")

        lines.extend([
            "",
            "---",
            "",
            "*本报告由 AI+JS逆向京东工业网数据采集智能体 v2.0 自动生成*",
        ])

        report_text = "\n".join(lines)

        # 保存报告
        report_path = self.output_dir / f"agent_report_{timestamp}.md"
        report_path.write_text(report_text, encoding="utf-8")
        logger.info(f"报告已保存: {report_path}")

        return report_text

    def generate_sniff_report(self, sniff_result: Dict) -> str:
        """生成 API 嗅探报告"""
        summary = sniff_result.get("summary", {})

        lines = [
            "# API 嗅探报告",
            "",
            f"**时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**耗时**: {summary.get('sniff_duration', 'N/A')}",
            f"**总请求数**: {summary.get('total_requests', 0)}",
            f"**去重 API 数**: {summary.get('api_count', 0)}",
            "",
            "## 签名参数",
            "",
        ]

        sig_params = summary.get("signature_params", [])
        if sig_params:
            for p in sig_params:
                lines.append(f"- `{p}` — 需要逆向")
        else:
            lines.append("无签名参数")

        lines.extend(["", "## 逆向目标", ""])
        targets = summary.get("reverse_targets", [])
        if targets:
            for t in targets:
                lines.append(f"- `{t}`")
        else:
            lines.append("无需逆向的接口")

        lines.extend(["", "## API 列表", ""])
        apis = sniff_result.get("apis", [])
        if apis:
            lines.append("| # | Host | Path | 参数数 | 需逆向 | 标签 |")
            lines.append("|---|------|------|--------|--------|------|")
            for i, api in enumerate(apis, 1):
                reverse = "是" if api.get("needs_reverse") else "否"
                tags = ", ".join(api.get("tags", [])[:3])
                lines.append(
                    f"| {i} | {api.get('host', '')} | "
                    f"{api.get('path', '')[:40]} | "
                    f"{len(api.get('params', {}))} | {reverse} | {tags} |"
                )

        return "\n".join(lines)

    def generate_monitoring_snapshot(self, dashboard: Dict) -> str:
        """生成监控快照报告"""
        agent_info = dashboard.get("agent", {})
        monitor_info = dashboard.get("monitor", {})

        lines = [
            "# 监控快照",
            "",
            f"**时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 智能体状态",
            "",
            f"- 阶段: {agent_info.get('phase', 'unknown')}",
            f"- JSRPC: {'正常' if agent_info.get('jsrpc_healthy') else '不可用'}",
            f"- 总请求: {agent_info.get('total_requests', 0)}",
            f"- 成功率: {agent_info.get('success_rate', '0.0%')}",
            "",
        ]

        if monitor_info:
            sign_info = monitor_info.get("sign", {})
            ip_info = monitor_info.get("ip", {})

            lines.extend([
                "## 签名监控",
                "",
                f"- 失败率: {sign_info.get('failure_rate', 0):.2%}",
                f"- 总请求: {sign_info.get('total_requests', 0)}",
                f"- 健康: {'✓' if sign_info.get('is_healthy') else '✗'}",
                "",
                "## IP 监控",
                "",
                f"- 封禁率: {ip_info.get('ban_rate', 0):.2%}",
                f"- 健康: {'✓' if ip_info.get('is_healthy') else '✗'}",
            ])

        return "\n".join(lines)

    # ============================================================
    # 内部格式化方法
    # ============================================================

    def _phase_title(self, phase_name: str) -> str:
        titles = {
            "environment_diagnosis": "环境诊断",
            "service_startup": "服务启动",
            "api_sniffing": "API 嗅探",
            "strategy_selection": "签名策略选型",
            "collection": "数据采集",
            "monitoring": "监控仪表盘",
        }
        return titles.get(phase_name, phase_name)

    def _format_diagnosis(self, result: Dict) -> List[str]:
        lines = [
            f"**环境就绪**: {'✓ 是' if result.get('ready') else '✗ 否'}",
            "",
            "| 检查项 | 状态 | 详情 |",
            "|--------|------|------|",
        ]
        for check in result.get("checks", []):
            status = "✓" if check.get("status") == "ok" else "✗"
            detail = check.get("value", check.get("status", ""))
            lines.append(f"| {check['name']} | {status} | {detail} |")
        lines.append("")
        return lines

    def _format_startup(self, result: Dict) -> List[str]:
        lines = [
            "| 服务 | 状态 | 备注 |",
            "|------|------|------|",
        ]
        for svc in result.get("services", []):
            status = "✓" if svc.get("status") == "ok" else "✗"
            hint = svc.get("hint", "")
            lines.append(f"| {svc['name']} | {status} | {hint} |")
        lines.append("")
        return lines

    def _format_sniffing(self, result: Dict) -> List[str]:
        summary = result.get("summary", {})
        lines = [
            f"- 总请求数: {summary.get('total_requests', 0)}",
            f"- API 数量: {summary.get('api_count', 0)}",
            f"- 签名参数: {', '.join(summary.get('signature_params', [])) or '无'}",
            f"- 逆向目标: {', '.join(summary.get('reverse_targets', [])) or '无'}",
            "",
        ]
        return lines

    def _format_strategy(self, result: Dict) -> List[str]:
        lines = [
            f"- 检测版本: `{result.get('detected_version', 'unknown')}`",
            f"- 推荐策略: `{result.get('recommended_strategy', 'unknown')}`",
            f"- 可靠性: {result.get('reliability', 'N/A')}",
            f"- 维护成本: {result.get('maintenance_cost', 'N/A')}",
            f"- 说明: {result.get('description', '')}",
            "",
        ]
        return lines

    def _format_collection(self, result: Dict) -> List[str]:
        lines = [
            f"- 状态: {'✓ 成功' if result.get('status') == 'success' else '✗ 失败'}",
            f"- functionId: `{result.get('function_id', '')}`",
            f"- 策略: {result.get('strategy', 'N/A')}",
        ]
        if result.get("error"):
            lines.append(f"- 错误: {result['error']}")
        lines.append("")
        return lines

    def _format_monitoring(self, result: Dict) -> List[str]:
        agent = result.get("agent", {})
        lines = [
            f"- 阶段: {agent.get('phase', 'unknown')}",
            f"- 成功率: {agent.get('success_rate', '0.0%')}",
            f"- 总请求: {agent.get('total_requests', 0)}",
            "",
        ]
        return lines
