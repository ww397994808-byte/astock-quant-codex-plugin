from __future__ import annotations

from core.result import TaskResult
from core.run_manager import RunManager
from qmt.readonly import QMTReadonlyChecker


class QMTCheckService:
    def run(self) -> TaskResult:
        ctx = RunManager().create_run("qmt_readonly")
        checker = QMTReadonlyChecker()
        snapshot = checker.collect()
        checker.write_report(ctx.output_dir, snapshot)
        status = "VALID" if snapshot.ok else "INVALID"
        return TaskResult(
            status=status,
            message="QMT 只读检查完成",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=status,
            warnings=snapshot.failures,
            artifacts={"qmt_readonly": snapshot.to_dict()},
        )
