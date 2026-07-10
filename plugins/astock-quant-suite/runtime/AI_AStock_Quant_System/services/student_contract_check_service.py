from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.result import TaskResult
from core.run_manager import RunManager


class StudentContractCheckService:
    """Check whether a student workflow still matches the pre-run research contract."""

    def run(
        self,
        contract: str | None = None,
        workflow: str | None = None,
        session_id: str | None = None,
    ) -> TaskResult:
        session_id = self._clean_label(session_id)
        contract_source = self._load_contract(contract, session_id)
        workflow_source = self._load_workflow(workflow, session_id)
        payload = self._payload(contract_source, workflow_source, session_id)
        ctx = RunManager().create_run("student_contract_check")
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if payload["status"] == "CONTRACT_MATCHED" else "INVALID"
        warnings = [item["message"] for item in payload.get("blockers", []) + payload.get("warnings", [])]
        return TaskResult(
            status=result_status,
            message=f"学员研究契约对账完成：{payload['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _payload(self, contract_source: dict[str, Any], workflow_source: dict[str, Any], session_id: str) -> dict[str, Any]:
        blockers = []
        warnings = []
        checks = []
        if not contract_source["found"]:
            blockers.append(self._issue("contract_missing", "缺少研究契约", contract_source.get("error") or "未找到 research_contract.json。", "先运行 student-research-contract。"))
        if not workflow_source["found"]:
            blockers.append(self._issue("workflow_missing", "缺少学生工作流", workflow_source.get("error") or "未找到 workflow_manifest.json。", "先运行 student-workflow。"))

        contract = contract_source.get("data") or {}
        workflow = workflow_source.get("data") or {}
        assumption = workflow_source.get("assumption") or {}
        if contract and workflow:
            checks.extend(self._field_checks(contract, workflow, assumption))
            blockers.extend([
                self._issue(
                    f"contract_drift:{item['field']}",
                    "研究假设漂移",
                    f"{item['field']} 不一致：contract={item['expected'] or 'MISSING'} workflow={item['actual'] or 'MISSING'}。",
                    "重新按契约运行 student-workflow，或生成新的研究契约后作为新研究分支。",
                )
                for item in checks
                if item["status"] == "FAIL"
            ])
            if workflow.get("status") != "VALID":
                warnings.append(self._issue(
                    "workflow_not_valid",
                    "工作流尚未通过",
                    f"workflow status={workflow.get('status') or 'MISSING'}。",
                    "这不一定是契约漂移，但不能作为推进 QMT 或实盘的证据。",
                ))
        status = "CONTRACT_MATCHED" if not blockers else "CONTRACT_DRIFT" if contract and workflow else "CONTRACT_CHECK_BLOCKED"
        payload = {
            "status": status,
            "summary": self._summary(status, blockers, warnings),
            "session_id": session_id or workflow.get("session_id") or contract.get("session_id") or "",
            "contract_id": contract_source.get("contract_id") or "",
            "safe_to_copy": False,
            "next_command": self._next_command(status, contract_source, workflow_source),
            "hard_boundary": "student-contract-check 只做契约和 workflow 对账；不会回测、不会连接 QMT、不会 pretrade、不会下单。",
            "contract_source": self._source_meta(contract_source),
            "workflow_source": self._source_meta(workflow_source),
            "checks": checks,
            "blockers": self._dedupe_issues(blockers),
            "warnings": self._dedupe_issues(warnings),
            "cards": self._cards(status, checks, contract_source, workflow_source),
        }
        return payload

    def _field_checks(self, contract: dict[str, Any], workflow: dict[str, Any], assumption: dict[str, Any]) -> list[dict[str, Any]]:
        expected_pattern = contract.get("strategy_pattern") or ""
        actual_pattern = assumption.get("strategy_pattern") or self._workflow_strategy_pattern(workflow)
        expected_execution = contract.get("execution_model") or {}
        actual_execution = assumption.get("execution_model") or {}
        fields = [
            ("resolved_symbol", contract.get("resolved_symbol"), workflow.get("symbol")),
            ("asset_type", contract.get("asset_type"), workflow.get("asset_type")),
            ("timeframe", contract.get("timeframe"), workflow.get("timeframe")),
            ("adjust", contract.get("adjust"), workflow.get("adjust")),
            ("strategy_pattern", expected_pattern, actual_pattern),
            ("template_name", contract.get("template_name"), assumption.get("template_name") or self._workflow_template_name(workflow)),
        ]
        checks = [self._check(field, expected, actual) for field, expected, actual in fields if expected or actual]
        if assumption:
            checks.extend([
                self._check("assumption.timeframe", contract.get("timeframe"), assumption.get("timeframe")),
                self._check("assumption.adjust", contract.get("adjust"), assumption.get("adjust")),
                self._check("assumption.strategy_pattern", expected_pattern, assumption.get("strategy_pattern")),
                self._check("assumption.template_name", contract.get("template_name"), assumption.get("template_name")),
            ])
        for key in ["signal_bar", "fill_bar", "price_basis", "t_plus_1"]:
            checks.append(self._check(f"execution_model.{key}", expected_execution.get(key), actual_execution.get(key)))
        return checks

    def _workflow_strategy_pattern(self, workflow: dict[str, Any]) -> str:
        for step in workflow.get("steps") or []:
            if step.get("step") == "select-strategy":
                return str((step.get("artifacts") or {}).get("strategy_pattern") or "")
        return ""

    def _workflow_template_name(self, workflow: dict[str, Any]) -> str:
        strategy = str(workflow.get("strategy") or "")
        if strategy == "boll_mean_reversion":
            return "swing"
        if strategy == "ma_cross":
            return "timing"
        return strategy

    def _check(self, field: str, expected: Any, actual: Any) -> dict[str, Any]:
        expected_text = "" if expected is None else str(expected)
        actual_text = "" if actual is None else str(actual)
        return {
            "field": field,
            "expected": expected_text,
            "actual": actual_text,
            "status": "PASS" if expected_text == actual_text else "FAIL",
        }

    def _load_contract(self, explicit: str | None, session_id: str) -> dict[str, Any]:
        source = self._load_explicit_or_latest(explicit, "student_research_contract", "STUDENT_RESEARCH_CONTRACT.json", session_id)
        if not source["found"]:
            return source
        data = source.get("data") or {}
        contract = data.get("contract") or data
        return {
            **source,
            "data": contract,
            "contract_id": data.get("contract_id") or "",
            "status": data.get("status") or source.get("status", ""),
        }

    def _load_workflow(self, explicit: str | None, session_id: str) -> dict[str, Any]:
        source = self._load_explicit_or_latest(explicit, "student_workflow", "workflow_manifest.json", session_id)
        if not source["found"]:
            return source
        run_dir = Path(source.get("run_dir") or "")
        assumption_path = run_dir / "BACKTEST_ASSUMPTION_CARD.json"
        assumption = self._read_json(assumption_path).get("data") if assumption_path.exists() else {}
        return {**source, "assumption": assumption or {}}

    def _load_explicit_or_latest(self, explicit: str | None, prefix: str, filename: str, session_id: str) -> dict[str, Any]:
        if explicit:
            path = Path(explicit)
            if path.is_dir():
                path = path / filename
            return self._read_json(path)
        candidates = sorted(Path("reports").glob(f"{prefix}_*/{filename}"))
        for path in reversed(candidates):
            source = self._read_json(path)
            if not session_id or self._matches_session(source.get("data") or {}, session_id):
                return source
        return {"found": False, "path": "", "run_dir": "", "data": {}, "error": f"未找到 {filename}"}

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"found": False, "path": str(path), "run_dir": str(path.parent), "data": {}, "error": f"文件不存在：{path}"}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"found": False, "path": str(path), "run_dir": str(path.parent), "data": {}, "error": f"无法读取 JSON：{exc}"}
        return {"found": True, "path": str(path), "run_dir": str(path.parent), "data": data}

    def _matches_session(self, data: dict[str, Any], session_id: str) -> bool:
        if str(data.get("session_id") or "") == session_id:
            return True
        contract = data.get("contract") or {}
        return str(contract.get("session_id") or "") == session_id

    def _source_meta(self, source: dict[str, Any]) -> dict[str, Any]:
        return {
            "found": source.get("found", False),
            "path": source.get("path", ""),
            "run_dir": source.get("run_dir", ""),
            "status": source.get("status") or (source.get("data") or {}).get("status", ""),
            "error": source.get("error", ""),
        }

    def _cards(self, status: str, checks: list[dict[str, Any]], contract_source: dict[str, Any], workflow_source: dict[str, Any]) -> list[dict[str, Any]]:
        failed = [item for item in checks if item["status"] == "FAIL"]
        return [
            {
                "id": "contract_check",
                "title": "契约对账",
                "status": "PASS" if status == "CONTRACT_MATCHED" else "BLOCK",
                "action": "workflow 与研究契约一致。" if status == "CONTRACT_MATCHED" else "先处理契约漂移或缺失证据。",
                "why": f"failed={len(failed)}; contract={contract_source.get('path') or 'MISSING'}; workflow={workflow_source.get('path') or 'MISSING'}",
                "command": "",
                "safe_to_copy": False,
            }
        ]

    def _summary(self, status: str, blockers: list[dict[str, str]], warnings: list[dict[str, str]]) -> str:
        if status == "CONTRACT_MATCHED":
            return f"workflow 与研究契约一致；提醒项 {len(warnings)} 个。"
        if status == "CONTRACT_DRIFT":
            return f"发现 {len(blockers)} 个契约漂移，不能把该 workflow 当作本契约证据。"
        return f"契约对账缺少必要证据：{len(blockers)} 个阻断项。"

    def _next_command(self, status: str, contract_source: dict[str, Any], workflow_source: dict[str, Any]) -> str:
        if status == "CONTRACT_MATCHED":
            workflow_dir = workflow_source.get("run_dir") or "<workflow报告目录>"
            return f"python3 cli.py student-control-center --workflow {workflow_dir}"
        if not contract_source.get("found"):
            return 'python3 cli.py student-research-contract --idea "<策略想法>" --session-id <学员或案例ID>'
        if not workflow_source.get("found"):
            return 'python3 cli.py student-workflow --idea "<策略想法>" --timeframe 1d --adjust point_in_time_qfq --auto-refine'
        return "重新按研究契约运行 student-workflow，或生成新的 student-research-contract 作为新分支。"

    def _issue(self, issue_id: str, title: str, message: str, fix: str) -> dict[str, str]:
        return {"id": issue_id, "title": title, "message": message, "fix": fix}

    def _clean_label(self, value: str | None) -> str:
        text = str(value or "").strip()
        return "".join(ch for ch in text if ch.isalnum() or ch in {"-", "_", "."})[:80]

    def _dedupe_issues(self, issues: list[dict[str, str]]) -> list[dict[str, str]]:
        deduped = []
        seen = set()
        for issue in issues:
            key = (issue.get("id", ""), issue.get("message", ""))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(issue)
        return deduped

    def _write_outputs(self, output_dir: Path, payload: dict[str, Any]) -> None:
        (output_dir / "STUDENT_CONTRACT_CHECK.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "student_contract_check_cards.json").write_text(
            json.dumps(payload["cards"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# Student Contract Check",
            "",
            f"status: {payload['status']}",
            f"contract_id: {payload.get('contract_id') or 'MISSING'}",
            f"session_id: {payload.get('session_id') or 'MISSING'}",
            "",
            "## 当前结论",
            f"- {payload['summary']}",
            f"- {payload['hard_boundary']}",
            "",
            "## 下一步",
            f"- command: `{payload['next_command']}`",
            "",
            "## 对账项",
        ]
        for item in payload["checks"]:
            lines.append(f"- [{item['status']}] {item['field']}: contract={item['expected'] or 'MISSING'} workflow={item['actual'] or 'MISSING'}")
        if not payload["checks"]:
            lines.append("- NONE")
        lines.extend(["", "## 阻断项"])
        lines.extend([f"- {item['title']}: {item['message']} fix={item['fix']}" for item in payload.get("blockers") or []] or ["- NONE"])
        lines.extend(["", "## 提醒项"])
        lines.extend([f"- {item['title']}: {item['message']} fix={item['fix']}" for item in payload.get("warnings") or []] or ["- NONE"])
        lines.extend(["", "## 证据来源"])
        for label in ["contract_source", "workflow_source"]:
            source = payload[label]
            lines.extend([
                f"### {label}",
                f"- found: {source.get('found', False)}",
                f"- path: {source.get('path') or 'MISSING'}",
                f"- status: {source.get('status') or 'MISSING'}",
                f"- error: {source.get('error') or 'MISSING'}",
            ])
        (output_dir / "STUDENT_CONTRACT_CHECK.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
