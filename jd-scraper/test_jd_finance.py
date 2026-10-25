#!/usr/bin/env python3
"""
京东金融 APP 金条数据采集测试

测试逆向工程 AI 工具系统的完整工作流：
1. 流量嗅探 (TrafficSniffer)
2. 加密分析 (CryptoAnalyzer)
3. 京东金融数据采集 (JDFinance)
4. 完整管道测试 (Full Pipeline)
"""

import sys
import os
import json
import logging
import time
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from skills.orchestrator import AIOrchestrator, get_orchestrator
from skills.traffic_sniffer import TrafficSnifferSkill
from skills.crypto_analyzer import CryptoAnalyzerSkill
from skills.jd_finance import JDFinanceSkill, create_jd_finance_skill
from skills.base_skill import SkillConfig

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("test_jd_finance")


# ============================================================================
# 测试数据
# ============================================================================

# 模拟的京东金融 APP 请求数据（基于实际抓包分析）
MOCK_JD_FINANCE_REQUESTS = [
    {
        "url": "https://ms.jr.jd.com/gw/generic/zj/h5/m/latest/creditLimit",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.210 Mobile Safari/537.36 jdapp;android;10.5.0",
            "Referer": "https://m.jd.com/",
            "Origin": "https://m.jd.com"
        },
        "query_params": {},
        "body": json.dumps({
            "appKey": "jd_finance_app",
            "clientVersion": "10.5.0",
            "client": "android",
            "ts": str(int(time.time() * 1000)),
            "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "sign": "e10adc3949ba59abbe56e057f20f883e",
            "pin": "test_user_pin",
            "body": json.dumps({"scene": "jintiao"})
        }),
        "timestamp": time.time()
    },
    {
        "url": "https://ms.jr.jd.com/gw/generic/zj/h5/m/latest/interestRate",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36"
        },
        "query_params": {},
        "body": json.dumps({
            "appKey": "jd_finance_app",
            "clientVersion": "10.5.0",
            "client": "android",
            "ts": str(int(time.time() * 1000)),
            "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "sign": "098f6bcd4621d373cade4e832627b4f6",
            "pin": "test_user_pin",
            "body": json.dumps({"loanType": "jintiao"})
        }),
        "timestamp": time.time()
    }
]

# 模拟的响应数据
MOCK_JD_FINANCE_RESPONSES = {
    "jintiao_quota": {
        "resultCode": "0000",
        "resultMsg": "success",
        "resultData": {
            "creditLimit": 50000,
            "availableLimit": 35000,
            "usedLimit": 15000,
            "currency": "CNY",
            "status": "ACTIVE",
            "updateTime": "2026-10-25 10:00:00"
        }
    },
    "jintiao_rate": {
        "resultCode": "0000",
        "resultMsg": "success",
        "resultData": {
            "dailyRate": 0.0002,
            "annualRate": 0.072,
            "minRate": 0.0001,
            "maxRate": 0.0005,
            "discountRate": 0.8
        }
    },
    "credit_score": {
        "resultCode": "0000",
        "resultMsg": "success",
        "resultData": {
            "creditScore": 720,
            "scoreLevel": "A",
            "scoreTrend": "up",
            "updateTime": "2026-10-25 10:00:00"
        }
    }
}


# ============================================================================
# 测试用例
# ============================================================================

def test_traffic_sniffer():
    """测试 1: 流量嗅探 Skill"""
    
    print("\n" + "=" * 60)
    print("TEST 1: TrafficSniffer Skill - 流量嗅探")
    print("=" * 60)
    
    sniffer = TrafficSnifferSkill()
    
    result = sniffer.run({
        "requests": MOCK_JD_FINANCE_REQUESTS
    })
    
    print(f"\nStatus: {result.status.value}")
    print(f"Duration: {result.duration:.2f}s")
    
    if result.data:
        data = result.data
        print(f"Total Requests: {data.get('total_requests', 0)}")
        print(f"Suspicious Params: {data.get('suspicious_params_count', 0)}")
        
        # 打印可疑参数
        for param in data.get("suspicious_params", []):
            print(f"  - {param['name']}: {param.get('reasons', [])}")
        
        # 打印报告
        report = data.get("report", {})
        print(f"\nReport Summary:")
        print(f"  Avg Risk Score: {report.get('summary', {}).get('avg_risk_score', 0)}")
        print(f"  Param Types: {report.get('param_types', {})}")
    
    return result


def test_crypto_analyzer(suspicious_params):
    """测试 2: 加密分析 Skill"""
    
    print("\n" + "=" * 60)
    print("TEST 2: CryptoAnalyzer Skill - 加密算法分析")
    print("=" * 60)
    
    analyzer = CryptoAnalyzerSkill()
    
    result = analyzer.run({
        "suspicious_params": suspicious_params,
        "request_data": MOCK_JD_FINANCE_REQUESTS[0] if MOCK_JD_FINANCE_REQUESTS else {},
        "context_params": {
            "appKey": "jd_finance_app",
            "clientVersion": "10.5.0",
            "client": "android"
        }
    })
    
    print(f"\nStatus: {result.status.value}")
    print(f"Duration: {result.duration:.2f}s")
    
    if result.data:
        data = result.data
        print(f"Total Analyzed: {data.get('total_analyzed', 0)}")
        
        for analysis in data.get("analyses", []):
            print(f"\n  Param: {analysis.get('param_name')}")
            print(f"  Algorithm: {analysis.get('inferred_algorithm')}")
            print(f"  Confidence: {analysis.get('confidence', 0):.2f}")
            print(f"  Reproduction: {'Success' if analysis.get('reproduction', {}).get('success') else 'Failed'}")
            if analysis.get("formula"):
                print(f"  Formula: {analysis.get('formula')}")
        
        # 打印复现代码
        code = data.get("reproduction_code", "")
        if code:
            print(f"\n  Generated Code:")
            print("  " + "-" * 40)
            for line in code.split("\n")[:20]:
                print(f"  {line}")
            if code.count("\n") > 20:
                print("  ... (truncated)")
    
    return result


def test_jd_finance_collection():
    """测试 3: 京东金融数据采集"""
    
    print("\n" + "=" * 60)
    print("TEST 3: JDFinance Skill - 京东金融数据采集")
    print("=" * 60)
    
    # 创建 Skill（无真实凭证，测试模式）
    skill = create_jd_finance_skill(
        app_key="test_app_key",
        secret_key="test_secret_key"
    )
    
    # 测试各个端点
    targets = ["jintiao_quota", "jintiao_rate", "credit_score"]
    
    for target in targets:
        print(f"\n--- Target: {target} ---")
        
        result = skill.run({
            "target": target,
            "cookies": {
                "pin": "test_pin",
                "wskey": "test_wskey"
            }
        })
        
        print(f"Status: {result.status.value}")
        
        if result.data:
            data = result.data
            response = data.get("response", {})
            
            if response.get("success"):
                print(f"Data: {json.dumps(response.get('data', {}), indent=2, ensure_ascii=False)}")
            else:
                print(f"Error: {response.get('error', 'Unknown error')}")
                print(f"Note: This is expected without valid credentials")
    
    return result


def test_full_pipeline():
    """测试 4: 完整管道测试"""
    
    print("\n" + "=" * 60)
    print("TEST 4: Full Pipeline - 完整管道测试")
    print("=" * 60)
    
    orchestrator = get_orchestrator({
        "jd_app_key": "test_app_key",
        "jd_secret_key": "test_secret_key"
    })
    
    # 测试流量分析工作流
    print("\n--- Workflow: traffic_analysis ---")
    
    result = orchestrator.analyze_traffic(MOCK_JD_FINANCE_REQUESTS)
    
    print(f"Status: {result.status}")
    print(f"Steps: {result.steps_completed}/{result.total_steps}")
    print(f"Duration: {result.duration:.2f}s")
    
    if result.step_results:
        sniff_result = result.step_results.get("sniff_result", {})
        analysis_result = result.step_results.get("analysis_result", {})
        
        print(f"\nSniff Results:")
        print(f"  Suspicious Params: {sniff_result.get('suspicious_params_count', 0)}")
        
        print(f"\nAnalysis Results:")
        print(f"  Total Analyzed: {analysis_result.get('total_analyzed', 0)}")
    
    # 测试京东金融采集工作流
    print("\n--- Workflow: jd_finance_collection ---")
    
    result2 = orchestrator.collect_jd_finance(
        target="jintiao_quota",
        cookies={"pin": "test_pin"}
    )
    
    print(f"Status: {result2.status}")
    print(f"Steps: {result2.steps_completed}/{result2.total_steps}")
    
    # 打印 Skill 统计
    print("\n--- Skill Statistics ---")
    stats = orchestrator.get_stats()
    
    for skill_name, skill_stats in stats.items():
        print(f"\n  {skill_name}:")
        print(f"    Executions: {skill_stats.get('execution_count', 0)}")
        print(f"    Success Rate: {skill_stats.get('success_rate', 0):.2%}")
    
    return result


def test_orchestrator_info():
    """测试 5: 编排器信息"""
    
    print("\n" + "=" * 60)
    print("TEST 5: Orchestrator Info - 编排器信息")
    print("=" * 60)
    
    orchestrator = get_orchestrator()
    
    # 列出可用工作流
    workflows = orchestrator.list_workflows()
    print(f"\nAvailable Workflows: {workflows}")
    
    # 列出已注册 Skill
    skills = orchestrator.registry.list_skills()
    print(f"\nRegistered Skills ({len(skills)}):")
    
    for skill in skills:
        print(f"  - {skill['name']} v{skill['version']}")
        print(f"    Status: {skill['status']}")
        print(f"    Tags: {', '.join(skill.get('tags', []))}")
    
    return {"workflows": workflows, "skills": skills}


# ============================================================================
# 集成测试
# ============================================================================

def test_integration():
    """集成测试：模拟真实场景"""
    
    print("\n" + "=" * 60)
    print("INTEGRATION TEST: 模拟真实京东金融数据采集场景")
    print("=" * 60)
    
    orchestrator = get_orchestrator({
        "jd_app_key": "test_app_key",
        "jd_secret_key": "test_secret_key"
    })
    
    # Step 1: 流量嗅探
    print("\n[Step 1] Sniffing traffic...")
    
    sniffer = TrafficSnifferSkill()
    sniff_result = sniffer.run({"requests": MOCK_JD_FINANCE_REQUESTS})
    
    if sniff_result.status.value != "success":
        print(f"  FAILED: {sniff_result.error}")
        return
    
    suspicious_params = sniff_result.data.get("suspicious_params", [])
    print(f"  Found {len(suspicious_params)} suspicious params")
    
    # Step 2: 加密分析
    print("\n[Step 2] Analyzing encryption...")
    
    analyzer = CryptoAnalyzerSkill()
    analysis_result = analyzer.run({
        "suspicious_params": suspicious_params,
        "request_data": MOCK_JD_FINANCE_REQUESTS[0]
    })
    
    if analysis_result.status.value != "success":
        print(f"  FAILED: {analysis_result.error}")
        return
    
    analyses = analysis_result.data.get("analyses", [])
    print(f"  Analyzed {len(analyses)} params")
    
    # Step 3: 数据采集
    print("\n[Step 3] Collecting JD Finance data...")
    
    collection_result = orchestrator.collect_jd_finance(
        target="jintiao_quota",
        cookies={"pin": "test_pin"}
    )
    
    print(f"  Collection status: {collection_result.status}")
    
    # 生成最终报告
    print("\n" + "-" * 60)
    print("FINAL REPORT")
    print("-" * 60)
    
    report = {
        "test_time": datetime.now().isoformat(),
        "traffic_analysis": {
            "total_requests": sniff_result.data.get("total_requests", 0),
            "suspicious_params": len(suspicious_params),
            "risk_score": sniff_result.data.get("report", {}).get("summary", {}).get("avg_risk_score", 0)
        },
        "crypto_analysis": {
            "total_analyzed": analysis_result.data.get("total_analyzed", 0),
            "reproduced": analysis_result.data.get("summary", {}).get("successfully_reproduced", 0),
            "algorithms": analysis_result.data.get("summary", {}).get("algorithm_distribution", {})
        },
        "data_collection": {
            "status": collection_result.status,
            "steps": f"{collection_result.steps_completed}/{collection_result.total_steps}"
        },
        "skill_stats": orchestrator.get_stats()
    }
    
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    
    # 保存报告
    report_path = Path("data/reports/jd_finance_test_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\nReport saved to: {report_path}")
    
    return report


# ============================================================================
# 主入口
# ============================================================================

def main():
    """主测试入口"""
    
    print("=" * 60)
    print("京东金融 APP 金条数据采集 - 逆向工程 AI 工具系统测试")
    print("=" * 60)
    print(f"Time: {datetime.now().isoformat()}")
    
    # 运行所有测试
    tests = [
        ("Traffic Sniffer", test_traffic_sniffer),
        ("Crypto Analyzer", lambda: test_crypto_analyzer(
            test_traffic_sniffer().data.get("suspicious_params", []) if test_traffic_sniffer().data else []
        )),
        ("JD Finance Collection", test_jd_finance_collection),
        ("Full Pipeline", test_full_pipeline),
        ("Orchestrator Info", test_orchestrator_info),
        ("Integration Test", test_integration),
    ]
    
    results = {}
    
    for name, test_func in tests:
        try:
            print(f"\n{'#' * 60}")
            print(f"# Running: {name}")
            print(f"{'#' * 60}")
            
            result = test_func()
            results[name] = "PASS" if result else "FAIL"
            
        except Exception as e:
            logger.error(f"Test {name} failed: {e}", exc_info=True)
            results[name] = f"ERROR: {e}"
    
    # 打印总结
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for name, status in results.items():
        icon = "[OK]" if status == "PASS" else "[FAIL]"
        print(f"  {icon} {name}: {status}")
    
    passed = sum(1 for s in results.values() if s == "PASS")
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} passed")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
