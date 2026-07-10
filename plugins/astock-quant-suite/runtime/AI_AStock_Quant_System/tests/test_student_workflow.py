from __future__ import annotations

import json
from pathlib import Path

from services.student_workflow_service import StudentWorkflowService


def test_student_workflow_creates_manifest_and_summary(tmp_path: Path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    result = StudentWorkflowService().run(
        idea="中国神华日线布林低吸波段，控制回撤，不要太频繁交易",
        symbol="601088.SH",
        strategy="boll_mean_reversion",
        data="data/sample/601088.csv",
        timeframe="1d",
        adjust="point_in_time_qfq",
        session_id="alice",
        case_id="shenhua-boll",
    )

    assert result.report_path
    workflow_dir = Path(result.report_path)
    manifest_path = workflow_dir / "workflow_manifest.json"
    assert manifest_path.exists()
    assert (workflow_dir / "STUDENT_WORKFLOW_SUMMARY.md").exists()
    assert (workflow_dir / "NEXT_ACTIONS.md").exists()
    assert (workflow_dir / "STUDENT_ACCEPTANCE_CHECKLIST.md").exists()
    assert (workflow_dir / "STUDENT_DIAGNOSTICS.md").exists()
    assert (workflow_dir / "STUDENT_POLICY_ACTION_PLAN.md").exists()
    assert (workflow_dir / "BACKTEST_ASSUMPTION_CARD.md").exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary = (workflow_dir / "STUDENT_WORKFLOW_SUMMARY.md").read_text(encoding="utf-8")
    next_actions = (workflow_dir / "NEXT_ACTIONS.md").read_text(encoding="utf-8")
    checklist = (workflow_dir / "STUDENT_ACCEPTANCE_CHECKLIST.md").read_text(encoding="utf-8")
    diagnostics = (workflow_dir / "STUDENT_DIAGNOSTICS.md").read_text(encoding="utf-8")
    assert [step["step"] for step in manifest["steps"]] == ["resolve-symbol", "intake", "select-strategy", "fetch-data", "backtest", "audit", "paper", "stage-check"]
    assert manifest["session_id"] == "alice"
    assert manifest["case_id"] == "shenhua-boll"
    assert "session_id: alice" in summary
    assert "--session-id alice --case-id shenhua-boll" in next_actions
    assert manifest["steps"][0]["artifacts"]["symbol"] == "601088.SH"
    assert manifest["steps"][1]["run_id"].startswith("intake_")
    assert manifest["steps"][6]["run_id"].startswith("paper_")
    assert "report:" in summary
    assert "NEXT_ACTIONS.md" in summary
    assert "BACKTEST_ASSUMPTION_CARD.md" in summary
    assert "下一版想法示例" in next_actions
    assert "STUDENT_POLICY_ACTION_PLAN.md" in next_actions
    assert "回测假设卡" in next_actions
    assert "未来函数和交易规则审计已通过" in checklist
    assert "阶段门报告已生成" in checklist
    assert "模拟盘通过只代表可以做 QMT 只读检查" in checklist
    assert "问题分流" in diagnostics
    assert "观察期已经够，主要问题是信号太少" in diagnostics
    assert any(item["type"] == "increase_signal_frequency" for item in manifest["diagnostics"])
    assert manifest["paper_policy_action_plan"]["status"] == "NEEDS_RESEARCH_REPAIR"
    assert "trade_count" in manifest["paper_policy_action_plan"]["failed_metrics"]
    assert any("student-workflow" in command for command in manifest["paper_policy_action_plan"]["next_commands"])
    assumption = manifest["backtest_assumption_card"]
    assert assumption["strategy_pattern"] == "swing"
    assert assumption["execution_model"]["fill_bar"] == "next_bar_open"
    assert any(item["id"] == "astock_rules" for item in assumption["learner_checks"])
    assert manifest["next_actions"]


def test_student_workflow_auto_selects_strategy(tmp_path: Path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    result = StudentWorkflowService().run(
        idea="中国神华日线布林低吸波段，控制回撤，不要太频繁交易",
        symbol="601088.SH",
        data="data/sample/601088.csv",
        timeframe="1d",
        adjust="point_in_time_qfq",
    )

    assert result.report_path
    manifest = json.loads((Path(result.report_path) / "workflow_manifest.json").read_text(encoding="utf-8"))
    assert manifest["strategy"] == "boll_mean_reversion"
    assert manifest["steps"][2]["step"] == "select-strategy"
    assert manifest["steps"][2]["artifacts"]["selection_mode"] == "auto"


def test_student_workflow_resolves_symbol_from_idea(tmp_path: Path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    result = StudentWorkflowService().run(
        idea="中国神华日线布林低吸波段，控制回撤，不要太频繁交易",
        data="data/sample/601088.csv",
        timeframe="1d",
        adjust="point_in_time_qfq",
    )

    assert result.report_path
    manifest = json.loads((Path(result.report_path) / "workflow_manifest.json").read_text(encoding="utf-8"))
    assert manifest["symbol"] == "601088.SH"
    assert manifest["asset_type"] == "stock"
    assert manifest["steps"][0]["step"] == "resolve-symbol"


def test_student_workflow_runs_without_data_path(tmp_path: Path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    result = StudentWorkflowService().run(
        idea="中国神华日线布林低吸波段，控制回撤，不要太频繁交易",
        timeframe="1d",
        adjust="point_in_time_qfq",
    )

    assert result.report_path
    manifest = json.loads((Path(result.report_path) / "workflow_manifest.json").read_text(encoding="utf-8"))
    assert manifest["symbol"] == "601088.SH"
    assert manifest["steps"][3]["step"] == "fetch-data"
    assert manifest["steps"][3]["report_path"].endswith("601088.SH.parquet")
    assert manifest["steps"][4]["step"] == "backtest"
    assert manifest["steps"][4]["run_id"].startswith("backtest_")


def test_student_workflow_auto_selects_grid_strategy(tmp_path: Path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    result = StudentWorkflowService().run(
        idea="中国神华日线网格，跌3%买入加仓，涨3%卖出减仓，最大回撤10%，最大仓位80%",
        symbol="601088.SH",
        data="data/sample/601088.csv",
        timeframe="1d",
        adjust="point_in_time_qfq",
    )

    assert result.report_path
    manifest = json.loads((Path(result.report_path) / "workflow_manifest.json").read_text(encoding="utf-8"))
    assert manifest["strategy"] == "grid"
    assert manifest["steps"][2]["artifacts"]["strategy_pattern"] == "grid"
    assert any(item["id"] == "grid_state" for item in manifest["backtest_assumption_card"]["learner_checks"])


def test_student_workflow_assumption_card_flags_intraday_rules(tmp_path: Path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    result = StudentWorkflowService().run(
        idea="中国神华1小时布林低吸波段，控制回撤，不要太频繁交易",
        symbol="601088.SH",
        strategy="boll_mean_reversion",
        timeframe="1h",
        adjust="point_in_time_qfq",
    )

    assert result.report_path
    workflow_dir = Path(result.report_path)
    manifest = json.loads((workflow_dir / "workflow_manifest.json").read_text(encoding="utf-8"))
    card = json.loads((workflow_dir / "BACKTEST_ASSUMPTION_CARD.json").read_text(encoding="utf-8"))
    report = (workflow_dir / "BACKTEST_ASSUMPTION_CARD.md").read_text(encoding="utf-8")

    assert manifest["backtest_assumption_card"]["timeframe"] == "1h"
    assert any(item["id"] == "intraday_data" for item in card["learner_checks"])
    assert "日内数据完整性" in report


def test_student_workflow_auto_refine_runs_second_attempt(tmp_path: Path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    result = StudentWorkflowService().run(
        idea="中国神华日线布林低吸波段，控制回撤，不要太频繁交易",
        symbol="601088.SH",
        strategy="boll_mean_reversion",
        data="data/sample/601088.csv",
        timeframe="1d",
        adjust="point_in_time_qfq",
        auto_refine=True,
        session_id="repair-session",
    )

    assert result.report_path
    workflow_dir = Path(result.report_path)
    manifest = json.loads((workflow_dir / "workflow_manifest.json").read_text(encoding="utf-8"))
    summary = (workflow_dir / "STUDENT_WORKFLOW_SUMMARY.md").read_text(encoding="utf-8")
    next_actions = (workflow_dir / "NEXT_ACTIONS.md").read_text(encoding="utf-8")
    experiments = (workflow_dir / "STUDENT_EXPERIMENTS.md").read_text(encoding="utf-8")
    repair_dsl = (workflow_dir / "STUDENT_REPAIR_DSL.md").read_text(encoding="utf-8")

    assert manifest["auto_refine"]["enabled"] is True
    assert manifest["session_id"] == "repair-session"
    assert manifest["auto_refine"]["attempt_count"] == 2
    assert manifest["attempt"] == 2
    assert len(manifest["attempts"]) == 2
    assert len(manifest["candidate_experiments"]) == 5
    assert any(item["candidate_type"] == "strategy_switch" for item in manifest["candidate_experiments"])
    assert any(item["strategy"] == "ma_cross" for item in manifest["candidate_experiments"])
    assert any(item["strategy"] == "grid" for item in manifest["candidate_experiments"])
    assert manifest["candidate_experiments"][0]["rank"] == 1
    assert "score" in manifest["candidate_experiments"][0]
    assert manifest["candidate_experiments"][0]["is_recommended"] is True
    assert "--strategy-params" in manifest["candidate_experiments"][0]["next_command"]
    assert manifest["candidate_experiments"][0]["loss_analysis"]["completed_rounds"] >= 1
    assert "所有已完成买卖回合均亏损" in manifest["candidate_experiments"][0]["loss_analysis"]["primary_causes"]
    assert manifest["candidate_experiments"][0]["repair_actions"]
    assert manifest["repair_dsl_branch"]["status"] == "VALID"
    assert "add_trend_filter" in manifest["repair_dsl_branch"]["compiler_actions"]
    assert "add_cooldown" in manifest["repair_dsl_branch"]["compiler_actions"]
    assert any(item["type"] == "TrendFilter" for item in manifest["repair_dsl_branch"]["compiled_dsl"]["filters"])
    assert any(item["type"] == "CooldownFilter" for item in manifest["repair_dsl_branch"]["compiled_dsl"]["filters"])
    assert manifest["repair_dsl_branch"]["compiled_dsl"]["session_id"] == "repair-session"
    assert "session_id: repair-session" in repair_dsl
    assert (workflow_dir / "STUDENT_REPAIR_DSL.yaml").exists()
    assert (workflow_dir / "STUDENT_REPAIR_DSL.json").exists()
    assert "更高周期趋势向上" in manifest["candidate_experiments"][0]["next_research_idea"]
    assert "等待3根K线" in manifest["candidate_experiments"][0]["next_command"]
    repair_actions = manifest["candidate_experiments"][0]["repair_actions"]
    support_by_action = {item["action"]: item for item in repair_actions}
    assert support_by_action["add_trend_filter"]["implementation_status"] == "component_available_requires_compiled_strategy"
    assert support_by_action["add_trend_filter"]["component_available"] is True
    assert support_by_action["add_confirmation"]["implementation_status"] == "research_note_only"
    assert support_by_action["add_confirmation"]["implemented_in_current_run"] is False
    assert "涨回布林中轨或20日均线时卖出" in manifest["idea"]
    assert "每次买入30%" in manifest["idea"]
    assert "Auto Refine" in summary
    assert "自动补全记录" in next_actions
    assert "STUDENT_ACCEPTANCE_CHECKLIST.md" in summary
    assert "STUDENT_DIAGNOSTICS.md" in summary
    assert "STUDENT_EXPERIMENTS.md" in summary
    assert "候选实验" in experiments
    assert "推荐结论" in experiments
    assert "下一轮命令" in experiments
    assert "strategy_switch" in experiments
    assert "switch_ma_cross" in experiments
    assert "仅推荐作为研究分支" in experiments
    assert "loss_analysis" in experiments
    assert "完整买卖回合全部亏损" in experiments
    assert "repair_actions" in experiments
    assert "加入更高周期趋势过滤" in experiments
    assert "component_available_requires_compiled_strategy" in experiments
    assert "research_note_only" in experiments
    assert "next_research_idea" in experiments
    assert "Student Repair DSL Branch" in repair_dsl
    assert "结构化研究分支" in repair_dsl
    assert "repair-dsl-backtest" in repair_dsl
    assert "audit_report.md" in repair_dsl
    assert "--paper-observation --stage-check" in repair_dsl
    assert "--auto-repair" in repair_dsl
    assert "repair_dsl_next_actions.md" in repair_dsl
    assert "repair_dsl_auto_repair.md" in repair_dsl
    assert "候选实验只解决研究方向" in experiments
    assert "## Steps\n\n## Auto Refine" not in summary
    assert next_actions.count("使用更长历史数据观察至少达到模拟盘最低成交次数") <= 3


def test_student_workflow_paper_diagnostics_distinguish_short_window():
    service = StudentWorkflowService()
    diagnostics = service._paper_diagnostics({
        "status": "INVALID",
        "observed_days": 5,
        "trade_count": 0,
        "rejected_orders": 0,
        "max_drawdown": 0.0,
        "policy": {"min_observed_days": 20, "min_trades": 3, "max_drawdown_limit": 0.3},
    })

    types = {item["type"] for item in diagnostics}
    assert "extend_observation_window" in types
    assert "increase_signal_frequency" in types
    assert any("先延长数据" in item["recommendation"] for item in diagnostics)


def test_student_workflow_paper_diagnostics_explain_rounds_and_rejections():
    diagnostics = StudentWorkflowService()._paper_diagnostics({
        "status": "INVALID",
        "observed_days": 30,
        "trade_count": 6,
        "completed_rounds": 0,
        "rejected_orders": 2,
        "rejected_order_rate": 0.5,
        "max_drawdown": -0.01,
        "policy": {
            "min_observed_days": 20,
            "min_trades": 3,
            "min_completed_rounds": 1,
            "max_drawdown_limit": 0.3,
            "max_rejected_order_rate": 0.1,
        },
    })

    types = {item["type"] for item in diagnostics}
    assert "complete_trade_rounds" in types
    assert "reduce_rejected_order_rate" in types
    assert any("不要只看单边买入" in item["recommendation"] for item in diagnostics)


def test_student_workflow_loss_analysis_detects_all_losing_rounds(tmp_path: Path):
    run_dir = tmp_path / "candidate"
    run_dir.mkdir()
    (run_dir / "trades.csv").write_text(
        "symbol,action,quantity,price,amount,execute_time,total_fee\n"
        "601088.SH,BUY,100,10,1000,2024-01-02,5\n"
        "601088.SH,SELL,100,9,900,2024-01-03,5\n"
        "601088.SH,BUY,100,10,1000,2024-01-04,5\n"
        "601088.SH,SELL,100,8,800,2024-01-05,5\n",
        encoding="utf-8",
    )
    analysis = StudentWorkflowService()._candidate_loss_analysis(run_dir, {
        "total_return": -0.1,
        "initial_cash": 10000,
        "final_equity": 9700,
        "max_drawdown": -0.03,
        "total_fee": 20,
    })

    assert analysis["completed_rounds"] == 2
    assert analysis["losing_rounds"] == 2
    assert "所有已完成买卖回合均亏损" in analysis["primary_causes"]
    assert "完整买卖回合全部亏损" in analysis["summary"]


def test_student_workflow_repair_actions_for_losing_ma_candidate():
    actions = StudentWorkflowService()._repair_actions_for_candidate(
        "ma_cross",
        {"primary_causes": ["所有已完成买卖回合均亏损"]},
        {"max_drawdown": -0.06},
    )

    action_names = {item["action"] for item in actions}
    assert {"add_trend_filter", "add_confirmation", "add_cooldown", "tighten_risk"}.issubset(action_names)
    assert any("更高周期趋势向上" in item["idea_addition"] for item in actions)


def test_student_workflow_repair_action_support_marks_compiler_boundary():
    service = StudentWorkflowService()
    trend = service._repair_action_support("add_trend_filter", "ma_cross")
    confirmation = service._repair_action_support("add_confirmation", "ma_cross")
    risk = service._repair_action_support("tighten_risk", "boll_mean_reversion")

    assert trend["component_available"] is True
    assert trend["requires_strategy_compiler"] is True
    assert trend["implemented_in_current_run"] is False
    assert confirmation["implementation_status"] == "research_note_only"
    assert risk["implemented_in_current_run"] is True


def test_student_workflow_builds_repair_dsl_branch():
    service = StudentWorkflowService()
    branch = service._build_repair_dsl_branch(
        {"symbol": "601088.SH", "timeframe": "1d", "adjust": "point_in_time_qfq"},
        [{
            "variant_id": "switch_ma_cross",
            "strategy": "ma_cross",
            "is_recommended": True,
            "repair_actions": [
                {"action": "add_trend_filter", "requires_strategy_compiler": True, "compiler_action": "add_trend_filter"},
                {"action": "add_cooldown", "requires_strategy_compiler": True, "compiler_action": "add_cooldown"},
                {"action": "add_confirmation", "requires_strategy_compiler": False, "compiler_action": ""},
            ],
        }],
    )

    assert branch["status"] == "VALID"
    assert branch["compiler_actions"] == ["add_trend_filter", "add_cooldown"]
    assert any(item["type"] == "TrendFilter" for item in branch["compiled_dsl"]["filters"])
