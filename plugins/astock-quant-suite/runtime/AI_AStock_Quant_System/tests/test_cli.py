import subprocess
import sys
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cli_generate_sample_data_and_backtest():
    gen = subprocess.run([sys.executable, "cli.py", "generate-sample-data"], cwd=ROOT, text=True, capture_output=True)
    assert gen.returncode == 0, gen.stderr
    bt = subprocess.run([
        sys.executable,
        "cli.py",
        "backtest",
        "--strategy",
        "boll_mean_reversion",
        "--symbol",
        "601088.SH",
        "--data",
        "data/sample/601088.csv",
    ], cwd=ROOT, text=True, capture_output=True)
    assert bt.returncode == 0, bt.stderr
    assert "status: VALID" in bt.stdout


def test_cli_backtest_accepts_strategy_params():
    bt = subprocess.run([
        sys.executable,
        "cli.py",
        "backtest",
        "--strategy",
        "boll_mean_reversion",
        "--symbol",
        "601088.SH",
        "--data",
        "data/sample/601088.csv",
        "--strategy-params",
        '{"window":15,"num_std":1.8,"stop_loss":0.08}',
    ], cwd=ROOT, text=True, capture_output=True)
    assert bt.returncode == 0, bt.stderr
    assert "status: VALID" in bt.stdout


def test_cli_grid_backtest_accepts_template_params():
    bt = subprocess.run([
        sys.executable,
        "cli.py",
        "backtest",
        "--strategy",
        "grid",
        "--symbol",
        "601088.SH",
        "--data",
        "data/sample/601088.csv",
        "--strategy-params",
        '{"grid_step":0.02,"levels":3,"layer_percent":0.1}',
    ], cwd=ROOT, text=True, capture_output=True)
    assert bt.returncode == 0, bt.stderr
    assert "status: VALID" in bt.stdout


def test_cli_student_start_generates_start_bundle():
    run = subprocess.run([
        sys.executable,
        "cli.py",
        "student-start",
        "--no-session-index",
        "--no-preview",
    ], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert "STUDENT_START" not in run.stderr
    assert "report_path:" in run.stdout
    report_path = Path(next(line.split(": ", 1)[1] for line in run.stdout.splitlines() if line.startswith("report_path: ")))
    assert (ROOT / report_path / "STUDENT_START.md").exists()


def test_cli_student_product_audit_generates_delivery_report():
    run = subprocess.run([
        sys.executable,
        "cli.py",
        "student-product-audit",
        "--limit",
        "3",
    ], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert "学员产品化体检完成" in run.stdout
    report_path = Path(next(line.split(": ", 1)[1] for line in run.stdout.splitlines() if line.startswith("report_path: ")))
    assert (ROOT / report_path / "STUDENT_PRODUCT_AUDIT.md").exists()


def test_cli_student_idea_preflight_generates_ready_card():
    run = subprocess.run([
        sys.executable,
        "cli.py",
        "student-idea-preflight",
        "--idea",
        "中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究",
        "--session-id",
        "cli-student",
    ], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert "策略想法预检完成" in run.stdout
    report_path = Path(next(line.split(": ", 1)[1] for line in run.stdout.splitlines() if line.startswith("report_path: ")))
    assert (ROOT / report_path / "STUDENT_IDEA_PREFLIGHT.md").exists()


def test_cli_student_backtest_plan_precheck_generates_plan_card():
    run = subprocess.run([
        sys.executable,
        "cli.py",
        "student-backtest-plan-precheck",
        "--idea",
        "中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究",
        "--session-id",
        "cli-plan",
    ], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert "回测计划预检完成" in run.stdout
    assert "status: VALID" in run.stdout
    report_path = Path(next(line.split(": ", 1)[1] for line in run.stdout.splitlines() if line.startswith("report_path: ")))
    assert (ROOT / report_path / "STUDENT_BACKTEST_PLAN_PRECHECK.md").exists()
    assert (ROOT / report_path / "backtest_plan_precheck.yaml").exists()


def test_cli_student_course_path_generates_route_bundle():
    run = subprocess.run([
        sys.executable,
        "cli.py",
        "student-course-path",
        "--idea",
        "中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究",
        "--session-id",
        "cli-course",
    ], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert "学员课程路线生成完成" in run.stdout
    assert "status: VALID" in run.stdout
    report_path = Path(next(line.split(": ", 1)[1] for line in run.stdout.splitlines() if line.startswith("report_path: ")))
    assert (ROOT / report_path / "STUDENT_COURSE_PATH.md").exists()
    assert (ROOT / report_path / "student_course_path_cards.json").exists()


def test_cli_student_research_contract_generates_contract():
    run = subprocess.run([
        sys.executable,
        "cli.py",
        "student-research-contract",
        "--idea",
        "中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究",
        "--code",
        "ma20 = close.rolling(20).mean().shift(1)\nsignal = close > ma20\n",
        "--session-id",
        "cli-contract",
    ], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert "学员研究契约生成完成" in run.stdout
    assert "status: VALID" in run.stdout
    report_path = Path(next(line.split(": ", 1)[1] for line in run.stdout.splitlines() if line.startswith("report_path: ")))
    assert (ROOT / report_path / "STUDENT_RESEARCH_CONTRACT.md").exists()
    assert (ROOT / report_path / "research_contract.json").exists()


def test_cli_student_contract_check_reports_missing_evidence():
    run = subprocess.run([
        sys.executable,
        "cli.py",
        "student-contract-check",
        "--session-id",
        "missing-contract-cli",
    ], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert "学员研究契约对账完成" in run.stdout
    assert "status: INVALID" in run.stdout
    report_path = Path(next(line.split(": ", 1)[1] for line in run.stdout.splitlines() if line.startswith("report_path: ")))
    assert (ROOT / report_path / "STUDENT_CONTRACT_CHECK.md").exists()


def test_cli_student_future_leak_precheck_blocks_future_code():
    run = subprocess.run([
        sys.executable,
        "cli.py",
        "student-future-leak-precheck",
        "--code",
        "signal = close.shift(-1) > close",
        "--session-id",
        "cli-leak-check",
    ], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert "未来函数代码预检完成" in run.stdout
    assert "status: INVALID" in run.stdout
    report_path = Path(next(line.split(": ", 1)[1] for line in run.stdout.splitlines() if line.startswith("report_path: ")))
    assert (ROOT / report_path / "STUDENT_FUTURE_LEAK_PRECHECK.md").exists()


def test_cli_student_first_run_prepares_without_execution():
    run = subprocess.run([
        sys.executable,
        "cli.py",
        "student-first-run",
        "--idea",
        "中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究",
        "--session-id",
        "cli-first-run",
    ], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert "学员首跑向导完成" in run.stdout
    report_path = Path(next(line.split(": ", 1)[1] for line in run.stdout.splitlines() if line.startswith("report_path: ")))
    report = (ROOT / report_path / "STUDENT_FIRST_RUN.md").read_text(encoding="utf-8")
    assert "execute: False" in report
    assert "student-workflow" in report


def test_cli_student_handoff_pack_generates_bundle():
    run = subprocess.run([
        sys.executable,
        "cli.py",
        "student-handoff-pack",
        "--no-product-audit",
        "--no-session-report",
    ], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert "学员交付包生成完成" in run.stdout
    report_path = Path(next(line.split(": ", 1)[1] for line in run.stdout.splitlines() if line.startswith("report_path: ")))
    assert (ROOT / report_path / "STUDENT_HANDOFF_PACK.md").exists()


def test_cli_repair_dsl_backtest_generates_audit_reports(tmp_path: Path):
    dsl = tmp_path / "repair.yaml"
    dsl.write_text(
        "\n".join([
            "pattern: timing",
            "symbols:",
            "- 601088.SH",
            "entry:",
            "  type: MADeviationEntry",
            "  params:",
            "    window: 20",
            "    deviation: 0.04",
            "exit:",
            "- type: FixedTakeProfitExit",
            "  params:",
            "    take_profit: 0.08",
            "filters:",
            "- type: TrendFilter",
            "  params:",
            "    window: 20",
            "- type: CooldownFilter",
            "  params:",
            "    cooldown_bars: 3",
            "sizing:",
            "  type: FixedPercentSizing",
            "  params:",
            "    percent: 0.5",
            "timeframe: 1d",
            "adjust: point_in_time_qfq",
        ]) + "\n",
        encoding="utf-8",
    )
    bt = subprocess.run([
        sys.executable,
        "cli.py",
        "repair-dsl-backtest",
        "--dsl",
        str(dsl),
        "--symbol",
        "601088.SH",
        "--data",
        "data/sample/601088.csv",
        "--timeframe",
        "1d",
        "--adjust",
        "point_in_time_qfq",
    ], cwd=ROOT, text=True, capture_output=True)
    assert bt.returncode == 0, bt.stderr
    assert "status: VALID" in bt.stdout
    report_path = next(line.split(": ", 1)[1] for line in bt.stdout.splitlines() if line.startswith("report_path: "))
    report_dir = Path(report_path)
    assert (report_dir / "audit_report.md").exists()
    assert (report_dir / "future_leak_report.md").exists()
    assert (report_dir / "readiness_report.md").exists()
    assert (report_dir / "repair_dsl_run_report.md").exists()
    assert (report_dir / "compiled_strategy.json").exists()
    assert (report_dir / "backtest_plan.yaml").exists()
    assert (report_dir / "repair_dsl_next_actions.md").exists()


def test_cli_repair_dsl_backtest_can_run_paper_and_stage(tmp_path: Path):
    dsl = tmp_path / "repair.yaml"
    dsl.write_text(
        "\n".join([
            "pattern: timing",
            "symbols:",
            "- 601088.SH",
            "entry:",
            "  type: MADeviationEntry",
            "  params:",
            "    window: 20",
            "    deviation: 0.04",
            "exit:",
            "- type: FixedTakeProfitExit",
            "  params:",
            "    take_profit: 0.08",
            "filters:",
            "- type: TrendFilter",
            "  params:",
            "    window: 20",
            "- type: CooldownFilter",
            "  params:",
            "    cooldown_bars: 3",
            "sizing:",
            "  type: FixedPercentSizing",
            "  params:",
            "    percent: 0.5",
            "timeframe: 1d",
            "adjust: point_in_time_qfq",
        ]) + "\n",
        encoding="utf-8",
    )
    bt = subprocess.run([
        sys.executable,
        "cli.py",
        "repair-dsl-backtest",
        "--dsl",
        str(dsl),
        "--symbol",
        "601088.SH",
        "--data",
        "data/sample/601088.csv",
        "--timeframe",
        "1d",
        "--adjust",
        "point_in_time_qfq",
        "--paper-observation",
        "--stage-check",
    ], cwd=ROOT, text=True, capture_output=True)
    assert bt.returncode == 0, bt.stderr
    assert "status: INVALID" in bt.stdout
    report_path = next(line.split(": ", 1)[1] for line in bt.stdout.splitlines() if line.startswith("report_path: "))
    report_dir = Path(report_path)
    assert (report_dir / "paper_observation_report.md").exists()
    assert (report_dir / "stage_gate_report.md").exists()
    next_actions = (report_dir / "repair_dsl_next_actions.md").read_text(encoding="utf-8")
    run_report = (report_dir / "repair_dsl_run_report.md").read_text(encoding="utf-8")
    assert "先解决 0 成交" in next_actions
    assert "entry.params.deviation: 0.03" in next_actions
    assert "模拟盘观察" in run_report
    assert "阶段门" in run_report


def test_cli_repair_dsl_backtest_auto_repair_runs_candidates(tmp_path: Path):
    dsl = tmp_path / "repair.yaml"
    dsl.write_text(
        "\n".join([
            "pattern: timing",
            "symbols:",
            "- 601088.SH",
            "entry:",
            "  type: MADeviationEntry",
            "  params:",
            "    window: 20",
            "    deviation: 0.04",
            "exit:",
            "- type: FixedTakeProfitExit",
            "  params:",
            "    take_profit: 0.08",
            "filters:",
            "- type: TrendFilter",
            "  params:",
            "    window: 20",
            "- type: CooldownFilter",
            "  params:",
            "    cooldown_bars: 3",
            "sizing:",
            "  type: FixedPercentSizing",
            "  params:",
            "    percent: 0.5",
            "timeframe: 1d",
            "adjust: point_in_time_qfq",
        ]) + "\n",
        encoding="utf-8",
    )
    bt = subprocess.run([
        sys.executable,
        "cli.py",
        "repair-dsl-backtest",
        "--dsl",
        str(dsl),
        "--symbol",
        "601088.SH",
        "--data",
        "data/sample/601088.csv",
        "--timeframe",
        "1d",
        "--adjust",
        "point_in_time_qfq",
        "--paper-observation",
        "--stage-check",
        "--auto-repair",
    ], cwd=ROOT, text=True, capture_output=True)
    assert bt.returncode == 0, bt.stderr
    report_path = next(line.split(": ", 1)[1] for line in bt.stdout.splitlines() if line.startswith("report_path: "))
    report_dir = Path(report_path)
    auto_report = (report_dir / "repair_dsl_auto_repair.md").read_text(encoding="utf-8")
    assert (report_dir / "repair_dsl_auto_repair.json").exists()
    assert "relax_ma_deviation_1" in auto_report
    assert "diagnose_ma_deviation_001" in auto_report
    assert "remove_trend_filter_probe" in auto_report
    assert "next_command:" in auto_report
    assert "qmt_next_command:" in auto_report
    assert (report_dir / "auto_repair_candidates" / "relax_ma_deviation_1" / "strategy_dsl.yaml").exists()
    assert (report_dir / "auto_repair_candidates" / "relax_ma_deviation_1" / "repair_dsl_run_report.md").exists()
    ranked = json.loads((report_dir / "repair_dsl_auto_repair.json").read_text(encoding="utf-8"))
    assert ranked[0]["audit_status"] == "VALID"
    assert ranked[0]["trade_count"] >= 3
    assert ranked[0]["paper_status"] == "VALID"
    assert ranked[0]["qmt_next_command"] == "python3 cli.py qmt-check"
    assert "pretrade-package" in ranked[0]["pretrade_package_command"]
    promotion = json.loads((report_dir / "REPAIR_DSL_PROMOTION.json").read_text(encoding="utf-8"))
    assert promotion["status"] == "READY_FOR_QMT_READONLY"
    assert promotion["selected_variant_id"] == ranked[0]["variant_id"]
    assert "pretrade-package" in promotion["pretrade_package_command"]
    assert "pretrade-check" in promotion["pretrade_boundary"]
    assert (report_dir / "promotion_candidate" / "SELECTED_REPAIR_DSL.yaml").exists()
    assert (report_dir / "promotion_candidate" / "README.md").exists()
    promotion_md = (report_dir / "REPAIR_DSL_PROMOTION.md").read_text(encoding="utf-8")
    assert "QMT 只读检查" in promotion_md
    assert "不能跳过 pretrade-check" in promotion_md
