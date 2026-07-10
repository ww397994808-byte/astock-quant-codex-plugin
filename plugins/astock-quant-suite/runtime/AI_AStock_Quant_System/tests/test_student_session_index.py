from __future__ import annotations

import json
from pathlib import Path

from services.student_session_index_service import StudentSessionIndexService


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path.parent


def test_student_session_index_blocks_without_sessions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentSessionIndexService().run()

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "NO_SESSIONS"
    assert Path(result.report_path, "STUDENT_SESSION_INDEX.md").exists()


def test_student_session_index_summarizes_sessions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    alice_paper = _write_json(
        tmp_path / "reports" / "paper_20260629_1" / "paper_observation_policy_card.json",
        {
            "status": "INVALID",
            "requirements": [
                {"metric": "observed_days", "actual": 100, "required": 20, "status": "PASS"},
                {"metric": "trade_count", "actual": 2, "required": 3, "status": "FAIL"},
            ],
            "can_continue_qmt_readonly": False,
        },
    )
    alice_dir = _write_json(
        tmp_path / "reports" / "student_workflow_20260629_1" / "workflow_manifest.json",
        {
            "status": "INVALID",
            "session_id": "alice",
            "case_id": "shenhua-boll",
            "symbol": "601088.SH",
            "strategy": "boll_mean_reversion",
            "timeframe": "1d",
            "adjust": "point_in_time_qfq",
            "steps": [
                {"step": "paper", "status": "INVALID", "report_path": str(alice_paper)},
            ],
        },
    )
    (alice_dir / "STUDENT_REPAIR_DSL.yaml").write_text("pattern: timing\n", encoding="utf-8")
    _write_json(
        alice_dir / "BACKTEST_ASSUMPTION_CARD.json",
        {
            "status": "BLOCKED",
            "strategy_pattern": "grid",
            "timeframe": "30m",
            "template_name": "grid_strategy",
            "execution_model": {"signal_timing": "bar_close", "fill_timing": "next_bar_open"},
            "learner_checks": [
                {"id": "grid_state", "title": "网格状态", "status": "REQUIRED"},
                {"id": "intraday_data", "title": "分钟数据完整性", "status": "BLOCKED"},
            ],
        },
    )
    _write_json(
        tmp_path / "reports" / "student_workflow_20260630_1" / "workflow_manifest.json",
        {
            "status": "VALID",
            "session_id": "bob",
            "case_id": "ma-cross",
            "symbol": "600000.SH",
            "strategy": "ma_cross",
            "timeframe": "1d",
            "adjust": "point_in_time_qfq",
        },
    )
    _write_json(
        tmp_path / "reports" / "student_workflow_20260701_1" / "workflow_manifest.json",
        {
            "status": "VALID",
            "symbol": "000001.SH",
        },
    )
    ledger = tmp_path / "reports" / "student_session_ledger.jsonl"
    entries = [
        {"timestamp": "2026-06-29T10:00:00", "session_id": "alice", "allowed": True, "dry_run": True, "status": "DRY_RUN_READY"},
        {"timestamp": "2026-06-29T10:01:00", "session_id": "alice", "allowed": False, "dry_run": False, "status": "BLOCKED"},
    ]
    ledger.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in entries) + "\n", encoding="utf-8")

    result = StudentSessionIndexService().run(limit=10)

    assert result.status == "VALID"
    assert result.artifacts["status"] == "SESSION_INDEX_READY"
    sessions = {item["session_id"]: item for item in result.artifacts["sessions"]}
    assert set(sessions) == {"alice", "bob"}
    assert sessions["alice"]["latest_workflow"]["current_stage"] == "REPAIR_DSL_READY"
    assert sessions["alice"]["latest_workflow"]["backtest_assumption"]["status"] == "BLOCKED"
    assert sessions["alice"]["latest_workflow"]["backtest_assumption"]["strategy_pattern"] == "grid"
    assert sessions["alice"]["latest_workflow"]["backtest_assumption"]["learner_checks"][0]["id"] == "grid_state"
    assert sessions["alice"]["latest_workflow"]["paper_policy"]["status"] == "INVALID"
    assert sessions["alice"]["latest_workflow"]["paper_policy"]["failed_metrics"] == ["trade_count"]
    assert sessions["alice"]["latest_workflow"]["paper_policy"]["repair_hints"][0]["metric"] == "trade_count"
    assert sessions["alice"]["ledger_summary"]["blocked"] == 1
    assert "student-control-center --session-id alice" in sessions["alice"]["next_command"]
    assert any("拒绝" in note for note in sessions["alice"]["risk_notes"])
    assert any("回测假设卡" in note for note in sessions["alice"]["risk_notes"])
    assert any("trade_count" in note for note in sessions["alice"]["risk_notes"])
    assert Path(result.report_path, "student_session_cards.json").exists()
    report = Path(result.report_path, "STUDENT_SESSION_INDEX.md").read_text(encoding="utf-8")
    assert "paper_policy_failed_metrics: trade_count" in report
    assert "backtest_assumption_pattern: grid" in report
    assert "grid_state: REQUIRED" in report
    assert "paper_policy_repair_hints" in report
    assert "触发条件" in report
