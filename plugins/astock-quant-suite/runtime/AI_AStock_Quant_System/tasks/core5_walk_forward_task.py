from __future__ import annotations

from pathlib import Path

from core.result import TaskResult
from research.core5_relative_strength_grid.config import default_rule
from research.core5_relative_strength_grid.walk_forward import run_fixed_rule_start_check
from tasks.base_task import BaseTask


class Core5WalkForwardTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        out_dir = Path(kwargs.get("out") or "reports/core5_relative_strength_grid_package")
        starts = tuple(
            item.strip()
            for item in str(kwargs.get("starts") or "2018,2019,2020,2021").split(",")
            if item.strip()
        )
        n_random = int(kwargs.get("n_random") or 297)
        try:
            results = run_fixed_rule_start_check(
                out_dir=out_dir,
                rule=default_rule(),
                start_years=starts,
                n_random=n_random,
            )
        except Exception as exc:
            return TaskResult(
                status="INVALID",
                message=f"Core5 严格 walk-forward 回测未通过：{exc}",
                audit_status="WALK_FORWARD_INVALID",
                warnings=[str(exc)],
                artifacts={"out_dir": str(out_dir), "starts": starts, "n_random": n_random},
            )
        invalid = [
            year
            for year, result in results.items()
            if result.get("walk_forward_audit", {}).get("status") != "VALID"
        ]
        if invalid:
            return TaskResult(
                status="INVALID",
                message=f"Core5 严格 walk-forward 审计失败：{', '.join(invalid)}",
                report_path=str(out_dir),
                audit_status="WALK_FORWARD_INVALID",
                warnings=[f"start {year} 审计失败" for year in invalid],
                artifacts={"out_dir": str(out_dir), "starts": starts, "n_random": n_random},
            )
        return TaskResult(
            status="VALID",
            message="Core5 严格 walk-forward 回测完成：参数选择和品种排序均限制在调仓日及以前，报告已写入输出目录。",
            report_path=str(out_dir),
            audit_status="WALK_FORWARD_VALID",
            artifacts={
                "out_dir": str(out_dir),
                "starts": starts,
                "n_random": n_random,
                "audit_status": "VALID",
                "report": str(out_dir / "report.md"),
            },
        )
