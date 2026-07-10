from __future__ import annotations

from tasks.audit_task import AuditTask
from tasks.adaptive_intake_task import AdaptiveIntakeTask
from tasks.backtest_task import BacktestTask
from tasks.build_adjustment_factors_task import BuildAdjustmentFactorsTask
from tasks.course_demo_task import CourseDemoTask
from tasks.core5_walk_forward_task import Core5WalkForwardTask
from tasks.core5_live_signal_task import Core5LiveSignalTask
from tasks.core5_signal_sandbox_task import Core5SignalSandboxTask
from tasks.generate_sample_data_task import GenerateSampleDataTask
from tasks.doctor_task import DoctorTask
from tasks.explain_report_task import ExplainReportTask
from tasks.optimize_task import OptimizeTask
from tasks.optimize_loop_task import OptimizeLoopTask
from tasks.paper_task import PaperTask
from tasks.pretrade_task import PretradeTask
from tasks.pretrade_package_task import PretradePackageTask
from tasks.pretrade_runbook_refresh_task import PretradeRunbookRefreshTask
from tasks.qmt_batch_daily_review_task import QMTBatchDailyReviewTask
from tasks.qmt_batch_handoff_task import QMTBatchHandoffTask
from tasks.qmt_batch_handoff_wizard_task import QMTBatchHandoffWizardTask
from tasks.qmt_batch_lifecycle_task import QMTBatchLifecycleTask
from tasks.qmt_batch_sandbox_task import QMTBatchSandboxTask
from tasks.qmt_check_task import QMTCheckTask
from tasks.qmt_config_init_task import QMTConfigInitTask
from tasks.qmt_config_status_task import QMTConfigStatusTask
from tasks.qmt_daily_review_task import QMTDailyReviewTask
from tasks.qmt_handoff_task import QMTHandoffTask
from tasks.qmt_handoff_wizard_task import QMTHandoffWizardTask
from tasks.qmt_order_lifecycle_task import QMTOrderLifecycleTask
from tasks.qmt_order_sandbox_task import QMTOrderSandboxTask
from tasks.qmt_readiness_dashboard_task import QMTReadinessDashboardTask
from tasks.repair_dsl_task import RepairDSLTask
from tasks.research_task import ResearchTask
from tasks.intake_task import IntakeTask
from tasks.data_tasks import DataStatusTask, FetchDataTask, UpdateDataTask
from tasks.stage_check_task import StageCheckTask
from tasks.student_backtest_plan_precheck_task import StudentBacktestPlanPrecheckTask
from tasks.student_contract_check_task import StudentContractCheckTask
from tasks.student_control_center_task import StudentControlCenterTask
from tasks.student_course_path_task import StudentCoursePathTask
from tasks.student_doctor_task import StudentDoctorTask
from tasks.student_first_run_task import StudentFirstRunTask
from tasks.student_future_leak_precheck_task import StudentFutureLeakPrecheckTask
from tasks.student_handoff_pack_task import StudentHandoffPackTask
from tasks.student_idea_preflight_task import StudentIdeaPreflightTask
from tasks.student_next_step_runner_task import StudentNextStepRunnerTask
from tasks.student_product_audit_task import StudentProductAuditTask
from tasks.student_research_contract_task import StudentResearchContractTask
from tasks.student_safe_loop_task import StudentSafeLoopTask
from tasks.student_session_index_task import StudentSessionIndexTask
from tasks.student_session_report_task import StudentSessionReportTask
from tasks.student_start_task import StudentStartTask
from tasks.student_workflow_task import StudentWorkflowTask


TASKS = {
    "generate-sample-data": GenerateSampleDataTask,
    "course-demo": CourseDemoTask,
    "core5-walk-forward": Core5WalkForwardTask,
    "core5-live-signal": Core5LiveSignalTask,
    "core5-signal-sandbox": Core5SignalSandboxTask,
    "backtest": BacktestTask,
    "optimize": OptimizeTask,
    "optimize-loop": OptimizeLoopTask,
    "audit": AuditTask,
    "paper": PaperTask,
    "qmt-config-init": QMTConfigInitTask,
    "qmt-config-status": QMTConfigStatusTask,
    "qmt-check": QMTCheckTask,
    "pretrade-check": PretradeTask,
    "pretrade-package": PretradePackageTask,
    "pretrade-runbook-refresh": PretradeRunbookRefreshTask,
    "qmt-handoff": QMTHandoffTask,
    "qmt-handoff-wizard": QMTHandoffWizardTask,
    "qmt-batch-handoff": QMTBatchHandoffTask,
    "qmt-batch-handoff-wizard": QMTBatchHandoffWizardTask,
    "qmt-batch-sandbox": QMTBatchSandboxTask,
    "qmt-batch-lifecycle": QMTBatchLifecycleTask,
    "qmt-batch-daily-review": QMTBatchDailyReviewTask,
    "qmt-order-sandbox": QMTOrderSandboxTask,
    "qmt-order-lifecycle": QMTOrderLifecycleTask,
    "qmt-daily-review": QMTDailyReviewTask,
    "qmt-readiness-dashboard": QMTReadinessDashboardTask,
    "research": ResearchTask,
    "doctor": DoctorTask,
    "explain-report": ExplainReportTask,
    "build-adjustment-factors": BuildAdjustmentFactorsTask,
    "intake": IntakeTask,
    "intake-chat": AdaptiveIntakeTask,
    "fetch-data": FetchDataTask,
    "update-data": UpdateDataTask,
    "data-status": DataStatusTask,
    "stage-check": StageCheckTask,
    "student-backtest-plan-precheck": StudentBacktestPlanPrecheckTask,
    "student-contract-check": StudentContractCheckTask,
    "student-course-path": StudentCoursePathTask,
    "student-doctor": StudentDoctorTask,
    "student-first-run": StudentFirstRunTask,
    "student-future-leak-precheck": StudentFutureLeakPrecheckTask,
    "student-handoff-pack": StudentHandoffPackTask,
    "student-idea-preflight": StudentIdeaPreflightTask,
    "student-control-center": StudentControlCenterTask,
    "student-run-next": StudentNextStepRunnerTask,
    "student-product-audit": StudentProductAuditTask,
    "student-research-contract": StudentResearchContractTask,
    "student-safe-loop": StudentSafeLoopTask,
    "student-session-index": StudentSessionIndexTask,
    "student-session-report": StudentSessionReportTask,
    "student-start": StudentStartTask,
    "student-workflow": StudentWorkflowTask,
    "repair-dsl-backtest": RepairDSLTask,
}


def create_task(name: str):
    if name not in TASKS:
        raise ValueError(f"未知任务：{name}")
    return TASKS[name]()
