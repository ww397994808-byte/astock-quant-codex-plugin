from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CausalityFinding:
    severity: str
    message: str
    line: int | None = None
    code: str = ""

    def to_dict(self) -> dict:
        out = {"severity": self.severity, "message": self.message}
        if self.line is not None:
            out["line"] = self.line
        if self.code:
            out["code"] = self.code
        return out


@dataclass
class CausalityReport:
    status: str
    findings: list[CausalityFinding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"status": self.status, "findings": [item.to_dict() for item in self.findings]}


class SignalCausalityChecker:
    """Static signal-causality checks for strategy source.

    This is intentionally fail-closed for obvious future-looking constructs.
    Runtime window isolation remains the stronger guarantee.
    """

    _FUTURE_NAME_RE = re.compile(
        r"(future|next_|tomorrow|未来收益|未来价格|下一根|明天|后验|label|target_return)",
        re.IGNORECASE,
    )
    _DANGEROUS_CALLS = {
        "open": "策略代码不允许直接读写外部文件。",
        "eval": "策略代码不允许 eval。",
        "exec": "策略代码不允许 exec。",
        "compile": "策略代码不允许动态编译代码。",
    }
    _DANGEROUS_IMPORT_ROOTS = {
        "os", "sys", "subprocess", "requests", "urllib", "socket", "pathlib",
        "pickle", "sqlite3", "pymysql", "psycopg2", "sqlalchemy", "xtquant",
    }
    _FULL_SAMPLE_METHODS = {"mean", "std", "min", "max", "median", "quantile", "rank", "idxmax", "idxmin"}

    def check_file(self, path: str | Path) -> dict:
        p = Path(path)
        if not p.exists():
            return {"status": "VALID", "findings": []}
        report = self.check_text(p.read_text(encoding="utf-8"))
        out = report.to_dict()
        for item in out["findings"]:
            item["path"] = str(p)
        return out

    def check_text(self, code: str) -> CausalityReport:
        findings: list[CausalityFinding] = []
        raw = code or ""
        if re.search(r"shift\s*\(\s*-\d+", raw):
            findings.append(CausalityFinding("HIGH", "检测到 shift(-n)，信号疑似读取未来 K 线。", code="SHIFT_NEGATIVE"))
        if re.search(r"\.iloc\s*\[[^\]]*\+\s*1[^\]]*\]", raw):
            findings.append(CausalityFinding("HIGH", "检测到 iloc[i+1]，信号疑似读取未来 K 线。", code="ILOC_PLUS_ONE"))
        if re.search(r"rows\s*\[[^\]]*\+\s*1[^\]]*\]", raw):
            findings.append(CausalityFinding("HIGH", "检测到 rows[index+1]，信号疑似读取未来 K 线。", code="ROWS_PLUS_ONE"))

        try:
            tree = ast.parse(raw)
        except SyntaxError as exc:
            return CausalityReport("INVALID", [CausalityFinding("HIGH", f"策略代码语法错误：{exc}", getattr(exc, "lineno", None), "SYNTAX")])

        visitor = _CausalityVisitor(self)
        visitor.visit(tree)
        findings.extend(visitor.findings)

        status = "INVALID" if any(item.severity == "HIGH" for item in findings) else "VALID"
        return CausalityReport(status, findings)

    def write_report(self, path: str | Path, report: dict) -> None:
        lines = ["# Signal Causality Report", "", f"status: {report['status']}", ""]
        if report.get("findings"):
            for item in report["findings"]:
                line = f"- [{item.get('severity')}] {item.get('message')}"
                if item.get("line"):
                    line += f" (line {item['line']})"
                lines.append(line)
        else:
            lines.append("- 未发现 HIGH 风险信号因果问题。")
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


class _CausalityVisitor(ast.NodeVisitor):
    def __init__(self, checker: SignalCausalityChecker) -> None:
        self.checker = checker
        self.findings: list[CausalityFinding] = []
        self._loop_vars: set[str] = set()

    def visit_Import(self, node: ast.Import) -> Any:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root in self.checker._DANGEROUS_IMPORT_ROOTS:
                self._high(node, f"策略代码不允许 import {root}，避免绕过系统数据窗口。", "DANGEROUS_IMPORT")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        root = (node.module or "").split(".")[0]
        if root in self.checker._DANGEROUS_IMPORT_ROOTS:
            self._high(node, f"策略代码不允许 from {root} import ...，避免绕过系统数据窗口。", "DANGEROUS_IMPORT")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> Any:
        if self.checker._FUTURE_NAME_RE.search(node.id):
            self._high(node, f"变量名 {node.id} 疑似未来标签或未来收益。", "FUTURE_VARIABLE")
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> Any:
        added = []
        if isinstance(node.target, ast.Name):
            added.append(node.target.id)
            self._loop_vars.add(node.target.id)
        self.generic_visit(node)
        for item in added:
            self._loop_vars.discard(item)

    def visit_Call(self, node: ast.Call) -> Any:
        name = self._call_name(node.func)
        if name in self.checker._DANGEROUS_CALLS:
            self._high(node, self.checker._DANGEROUS_CALLS[name], "DANGEROUS_CALL")
        if name == "getattr":
            self._high(node, "策略代码不允许 getattr，避免动态访问未来数据或逃逸沙箱。", "DANGEROUS_CALL")

        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr == "shift" and self._has_negative_period(node):
                self._high(node, "检测到 shift(-n)，信号疑似读取未来 K 线。", "SHIFT_NEGATIVE")
            if attr in {"pct_change", "diff"} and self._has_negative_period(node):
                self._high(node, f"检测到 {attr}(-n)，信号疑似读取未来 K 线。", "NEGATIVE_PERIOD_CHANGE")
            if attr == "rolling" and self._keyword_bool(node, "center", True):
                self._high(node, "检测到 rolling(..., center=True)，居中窗口会读取未来 K 线。", "CENTERED_ROLLING")
            if attr == "merge_asof" and self._keyword_str(node, "direction") == "forward":
                self._high(node, "检测到 merge_asof(direction='forward')，会把未来记录并入当前信号。", "FORWARD_ASOF")
            if attr in self.checker._FULL_SAMPLE_METHODS and self._looks_like_full_series(node.func.value):
                self._medium(node, f"检测到可能使用全样本 {attr} 生成信号；请改为 rolling/expanding 并只使用历史窗口。", "FULL_SAMPLE_STAT")
            if attr.startswith("read_") or attr.startswith("to_"):
                self._high(node, f"策略代码不允许 pandas/numpy IO 方法 {attr}。", "PANDAS_IO")
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        if self._subscript_plus_one(node):
            self._high(node, "检测到 index+1 访问，信号疑似读取未来 K 线。", "INDEX_PLUS_ONE")
        self.generic_visit(node)

    def _subscript_plus_one(self, node: ast.Subscript) -> bool:
        return self._contains_loop_plus(node.slice)

    def _contains_loop_plus(self, node: ast.AST) -> bool:
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left_loop = isinstance(node.left, ast.Name) and node.left.id in self._loop_vars
            right_one = isinstance(node.right, ast.Constant) and node.right.value == 1
            if left_loop and right_one:
                return True
        return any(self._contains_loop_plus(child) for child in ast.iter_child_nodes(node))

    def _negative_int(self, node: ast.AST) -> bool:
        return (
            isinstance(node, ast.UnaryOp)
            and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, int)
            and node.operand.value > 0
        )

    def _has_negative_period(self, node: ast.Call) -> bool:
        if node.args and self._negative_int(node.args[0]):
            return True
        for keyword in node.keywords:
            if keyword.arg in {"periods", "period", "n"} and self._negative_int(keyword.value):
                return True
        return False

    def _keyword_bool(self, node: ast.Call, name: str, expected: bool) -> bool:
        for keyword in node.keywords:
            if keyword.arg == name and isinstance(keyword.value, ast.Constant):
                return keyword.value.value is expected
        return False

    def _keyword_str(self, node: ast.Call, name: str) -> str:
        for keyword in node.keywords:
            if keyword.arg == name and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                return keyword.value.value.lower()
        return ""

    def _looks_like_full_series(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id in {"close", "open", "high", "low", "volume", "df", "rows", "data"}
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            return node.value.id in {"df", "data"}
        return False

    def _call_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""

    def _high(self, node: ast.AST, message: str, code: str) -> None:
        self.findings.append(CausalityFinding("HIGH", message, getattr(node, "lineno", None), code))

    def _medium(self, node: ast.AST, message: str, code: str) -> None:
        self.findings.append(CausalityFinding("MEDIUM", message, getattr(node, "lineno", None), code))
