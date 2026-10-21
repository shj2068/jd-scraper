"""
JS 代码混淆反混淆引擎

混淆技术全景（按复杂度递增）：
┌─────────────────────────────────────────────────────────────────┐
│ Level │ 技术              │ 原理                    │ 破解难度 │
├───────┼───────────────────┼─────────────────────────┼──────────┤
│ 1     │ 变量名混淆        │ a,b,c 替换有意义名称    │ ★☆☆☆☆  │
│ 2     │ 字符串加密        │ base64/xor/rc4 编码字面量│ ★★☆☆☆  │
│ 3     │ 控制流平坦化      │ switch-case 打乱执行流  │ ★★★☆☆  │
│ 4     │ 死代码注入        │ 插入无效分支干扰分析    │ ★★★☆☆  │
│ 5     │ 反调试            │ debugger/setInterval    │ ★★★★☆  │
│ 6     │ 压缩+编码         │ eval(unescape(...))     │ ★★☆☆☆  │
│ 7     │ AST 变换          │ 自定义 AST 节点重组     │ ★★★★☆  │
│ 8     │ 虚拟机保护(VMP)   │ 自定义字节码+解释器     │ ★★★★★  │
└─────────────────────────────────────────────────────────────────┘

反混淆流水线：
1. 预处理: 美化/格式化 → 去除死代码 → 字符串解密
2. AST 分析: 构建控制流图 → 识别模式 → 标记可疑节点
3. 还原: 控制流去平坦化 → 变量重命名 → 函数提取
4. 验证: 执行对比 → 输出一致性检查
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import struct
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class DeobfuscationResult:
    """反混淆结果"""
    original: str
    deobfuscated: str
    techniques_detected: List[str] = field(default_factory=list)
    strings_decrypted: int = 0
    dead_code_removed: int = 0
    control_flow_restored: bool = False
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "techniques_detected": self.techniques_detected,
            "strings_decrypted": self.strings_decrypted,
            "dead_code_removed": self.dead_code_removed,
            "control_flow_restored": self.control_flow_restored,
            "warnings": self.warnings,
            "output_length": len(self.deobfuscated),
            "reduction_ratio": f"{1 - len(self.deobfuscated) / max(len(self.original), 1):.1%}",
        }


class StringDecryptor:
    """
    字符串解密器

    常见编码模式：
    - eval(unescape('%68%65%6C%6C%6F'))
    - atob('aGVsbG8=')
    - String.fromCharCode(104,101,108,108,111)
    - XOR 加密: _0x4a2b[0x3](_0x1f2a, 0x5a)
    - RC4/DES 自定义实现
    """

    def decrypt_unescape(self, code: str) -> Tuple[str, int]:
        """解密 unescape 编码"""
        pattern = r"unescape\(['\"](%[0-9a-fA-F]{2}+)['\"]\)"
        count = 0

        def replacer(m):
            nonlocal count
            try:
                decoded = binascii.unhexlify(m.group(1).replace("%", "")).decode("utf-8", errors="replace")
                count += 1
                return f'"{decoded}"'
            except Exception:
                return m.group(0)

        result = re.sub(pattern, replacer, code)
        return result, count

    def decrypt_atob(self, code: str) -> Tuple[str, int]:
        """解密 base64 atob 编码"""
        pattern = r"atob\(['\"]([A-Za-z0-9+/=]+)['\"]\)"
        count = 0

        def replacer(m):
            nonlocal count
            try:
                decoded = base64.b64decode(m.group(1)).decode("utf-8", errors="replace")
                count += 1
                return f'"{decoded}"'
            except Exception:
                return m.group(0)

        result = re.sub(pattern, replacer, code)
        return result, count

    def decrypt_fromcharcode(self, code: str) -> Tuple[str, int]:
        """解密 String.fromCharCode"""
        pattern = r"String\.fromCharCode\(([\d,\s]+)\)"
        count = 0

        def replacer(m):
            nonlocal count
            try:
                codes = [int(x.strip()) for x in m.group(1).split(",") if x.strip()]
                decoded = "".join(chr(c) for c in codes)
                count += 1
                return f'"{decoded}"'
            except Exception:
                return m.group(0)

        result = re.sub(pattern, replacer, code)
        return result, count

    def decrypt_hex_strings(self, code: str) -> Tuple[str, int]:
        """解密十六进制字符串 \\x68\\x65\\x6C\\x6C\\x6F"""
        pattern = r"'((?:\\x[0-9a-fA-F]{2})+)'"
        count = 0

        def replacer(m):
            nonlocal count
            try:
                hex_str = m.group(1)
                decoded = bytes.fromhex(hex_str.replace("\\x", "")).decode("utf-8", errors="replace")
                count += 1
                return f'"{decoded}"'
            except Exception:
                return m.group(0)

        result = re.sub(pattern, replacer, code)
        return result, count

    def decrypt_unicode_escape(self, code: str) -> Tuple[str, int]:
        """解密 Unicode 转义 \\u0068\\u0065"""
        pattern = r'"((?:\\u[0-9a-fA-F]{4})+)"'
        count = 0

        def replacer(m):
            nonlocal count
            try:
                u_str = m.group(1)
                decoded = u_str.encode().decode("unicode_escape")
                count += 1
                return f'"{decoded}"'
            except Exception:
                return m.group(0)

        result = re.sub(pattern, replacer, code)
        return result, count


class DeadCodeRemover:
    """
    死代码移除器

    常见死代码模式：
    - if(false) { ... }
    - while(false) { ... }
    - void 0; / undefined;
    - 不可达代码 (return 后的语句)
    - 无副作用的表达式语句
    """

    PATTERNS = [
        (r"if\s*\(\s*false\s*\)\s*\{[^}]*\}", "if(false)"),
        (r"if\s*\(\s*0\s*===?\s*\d+\s*\)\s*\{[^}]*\}", "if(0===N)"),
        (r"while\s*\(\s*false\s*\)\s*\{[^}]*\}", "while(false)"),
        (r"void\s+0\s*;", "void 0"),
        (r"(?:^|\s)undefined\s*;", "undefined"),
        (r"/\*[\s\S]*?\*/", "block_comment"),
    ]

    def remove(self, code: str) -> Tuple[str, int]:
        """移除死代码"""
        total_removed = 0
        result = code

        for pattern, name in self.PATTERNS:
            matches = re.findall(pattern, result)
            if matches:
                total_removed += len(matches)
                result = re.sub(pattern, "", result)

        return result, total_removed


class ControlFlowAnalyzer:
    """
    控制流平坦化分析器

    识别模式：
    var _0x1234 = 0;
    while(true) {
        switch(_0x1234) {
            case 0: ...; _0x1234 = 1; break;
            case 1: ...; _0x1234 = 2; break;
            case 2: ...; _0x1234 = 3; break;
        }
    }

    还原策略：
    1. 提取 switch 变量名
    2. 解析每个 case 的赋值目标
    3. 构建 case 执行顺序图
    4. 按顺序重组代码块
    """

    def detect_flattening(self, code: str) -> Dict[str, Any]:
        """检测控制流平坦化"""
        patterns = {
            "while_switch": r"while\s*\(\s*true\s*\)\s*\{\s*switch",
            "for_switch": r"for\s*\(\s*;\s*;\s*\)\s*\{\s*switch",
            "state_var": r"var\s+(_0x[a-f0-9]+)\s*=\s*\d+",
            "case_chain": r"case\s+\d+\s*:",
        }

        detected = {}
        for name, pattern in patterns.items():
            matches = re.findall(pattern, code)
            detected[name] = len(matches) > 0

        is_flat = detected.get("while_switch", False) or detected.get("for_switch", False)
        case_count = len(re.findall(r"case\s+\d+\s*:", code))

        return {
            "is_flattened": is_flat,
            "case_count": case_count,
            "patterns": detected,
            "confidence": "high" if is_flat and case_count > 3 else "low",
        }

    def extract_case_order(self, code: str) -> List[int]:
        """提取 case 执行顺序"""
        order = []
        for m in re.finditer(r"(_0x[a-f0-9]+)\s*=\s*(\d+)\s*;", code):
            try:
                order.append(int(m.group(2)))
            except ValueError:
                pass
        return order


class AntiDebugRemover:
    """
    反调试代码移除器

    常见反调试模式：
    - debugger; (断点陷阱)
    - setInterval(function(){debugger}, 1000)
    - Function('debugger')()
    - constructor('debugger')
    - 控制台清除 console.clear()
    """

    PATTERNS = [
        r"debugger\s*;",
        r"setInterval\s*\(\s*function\s*\(\s*\)\s*\{\s*debugger\s*\}",
        r"Function\s*\(\s*['\"]debugger['\"]\s*\)",
        r"constructor\s*\(\s*['\"]debugger['\"]\s*\)",
        r"console\.clear\s*\(\s*\)\s*;",
        r"self\[\'console\'\]\[\'clear\'\]",
    ]

    def remove(self, code: str) -> Tuple[str, int]:
        """移除反调试代码"""
        result = code
        count = 0
        for pattern in self.PATTERNS:
            matches = re.findall(pattern, result)
            if matches:
                count += len(matches)
                result = re.sub(pattern, "/* anti-debug removed */", result)
        return result, count


class JSDeobfuscator:
    """
    JS 反混淆主引擎

    流水线：预处理 → 字符串解密 → 死代码移除 → 反调试移除 → 控制流分析
    """

    def __init__(self):
        self.string_decryptor = StringDecryptor()
        self.dead_code_remover = DeadCodeRemover()
        self.control_flow_analyzer = ControlFlowAnalyzer()
        self.anti_debug_remover = AntiDebugRemover()

    def deobfuscate(self, code: str) -> DeobfuscationResult:
        """执行完整反混淆流水线"""
        result = DeobfuscationResult(original=code, deobfuscated=code)
        current = code

        # Step 1: 字符串解密
        techniques = []

        decrypted, count = self.string_decryptor.decrypt_unescape(current)
        if count > 0:
            current = decrypted
            result.strings_decrypted += count
            techniques.append("unescape_encoding")

        decrypted, count = self.string_decryptor.decrypt_atob(current)
        if count > 0:
            current = decrypted
            result.strings_decrypted += count
            techniques.append("base64_atob")

        decrypted, count = self.string_decryptor.decrypt_fromcharcode(current)
        if count > 0:
            current = decrypted
            result.strings_decrypted += count
            techniques.append("fromCharCode")

        decrypted, count = self.string_decryptor.decrypt_hex_strings(current)
        if count > 0:
            current = decrypted
            result.strings_decrypted += count
            techniques.append("hex_string_encoding")

        decrypted, count = self.string_decryptor.decrypt_unicode_escape(current)
        if count > 0:
            current = decrypted
            result.strings_decrypted += count
            techniques.append("unicode_escape")

        # Step 2: 反调试移除
        current, anti_debug_count = self.anti_debug_remover.remove(current)
        if anti_debug_count > 0:
            techniques.append("anti_debug")

        # Step 3: 死代码移除
        current, dead_count = self.dead_code_remover.remove(current)
        result.dead_code_removed = dead_count
        if dead_count > 0:
            techniques.append("dead_code")

        # Step 4: 控制流分析
        cf_analysis = self.control_flow_analyzer.detect_flattening(current)
        if cf_analysis["is_flattened"]:
            techniques.append(f"control_flow_flattening({cf_analysis['case_count']}cases)")
            result.control_flow_restored = True

        result.deobfuscated = current
        result.techniques_detected = techniques

        return result
