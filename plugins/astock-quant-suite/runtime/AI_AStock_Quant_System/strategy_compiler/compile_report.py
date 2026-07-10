from __future__ import annotations

import json
from pathlib import Path


class CompileReportWriter:
    def write(self, output_dir: str | Path, compiled: dict | None = None, errors: list[str] | None = None, action_reports: list[dict] | None = None) -> None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        errors = errors or []
        action_reports = action_reports or []
        status = "INVALID" if errors else "VALID"
        lines = ["# Strategy Compile Report", "", f"status: {status}", ""]
        if action_reports:
            lines.append("## Action Reports")
            for item in action_reports:
                lines.append(f"- {item.get('action')}: {item.get('status')} {item.get('error', '')}")
            lines.append("")
        if compiled:
            lines += [
                "## Compiled Strategy",
                f"- template: {compiled.get('template_name')}",
                f"- entry_rules: {', '.join(compiled.get('entry_rules', []))}",
                f"- exit_rules: {', '.join(compiled.get('exit_rules', []))}",
                f"- filters: {', '.join(compiled.get('filters', [])) or 'none'}",
                f"- sizing_rules: {', '.join(compiled.get('sizing_rules', []))}",
            ]
        if errors:
            lines.append("## Compile Errors")
            lines.extend(f"- {error}" for error in errors)
        (output_dir / "compile_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (output_dir / "compiled_strategy.json").write_text(json.dumps(compiled or {"status": "INVALID", "errors": errors}, ensure_ascii=False, indent=2), encoding="utf-8")
