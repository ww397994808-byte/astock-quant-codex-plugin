from __future__ import annotations

import json
from pathlib import Path

from services.student_contract_check_service import StudentContractCheckService


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path.parent


def _contract_payload(session_id: str = "alice", timeframe: str = "1w") -> dict:
    return {
        "status": "CONTRACT_READY",
        "contract_id": "abc123",
        "contract": {
            "idea": "中国神华周线布林",
            "session_id": session_id,
            "resolved_symbol": "601088.SH",
            "asset_type": "stock",
            "strategy_pattern": "swing",
            "template_name": "swing",
            "timeframe": timeframe,
            "adjust": "point_in_time_qfq",
            "execution_model": {
                "signal_bar": "close_confirmed",
                "fill_bar": "next_bar_open",
                "price_basis": "next_bar_open",
                "t_plus_1": True,
            },
        },
    }


def _workflow_payload(session_id: str = "alice", timeframe: str = "1w") -> dict:
    return {
        "status": "VALID",
        "session_id": session_id,
        "symbol": "601088.SH",
        "asset_type": "stock",
        "strategy": "boll_mean_reversion",
        "timeframe": timeframe,
        "adjust": "point_in_time_qfq",
        "steps": [{"step": "select-strategy", "artifacts": {"strategy_pattern": "swing"}}],
    }


def _assumption_payload(timeframe: str = "1w") -> dict:
    return {
        "status": "VALID",
        "strategy_pattern": "swing",
        "template_name": "swing",
        "timeframe": timeframe,
        "adjust": "point_in_time_qfq",
        "execution_model": {
            "signal_bar": "close_confirmed",
            "fill_bar": "next_bar_open",
            "price_basis": "next_bar_open",
            "t_plus_1": True,
        },
    }


def test_student_contract_check_matches_contract_and_workflow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    contract_dir = _write_json(tmp_path / "reports/student_research_contract_1/STUDENT_RESEARCH_CONTRACT.json", _contract_payload())
    workflow_dir = _write_json(tmp_path / "reports/student_workflow_1/workflow_manifest.json", _workflow_payload())
    _write_json(workflow_dir / "BACKTEST_ASSUMPTION_CARD.json", _assumption_payload())

    result = StudentContractCheckService().run(contract=str(contract_dir), workflow=str(workflow_dir))

    assert result.status == "VALID"
    assert result.artifacts["status"] == "CONTRACT_MATCHED"
    assert all(item["status"] == "PASS" for item in result.artifacts["checks"])
    assert Path(result.report_path, "STUDENT_CONTRACT_CHECK.md").exists()


def test_student_contract_check_blocks_timeframe_drift(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    contract_dir = _write_json(tmp_path / "reports/student_research_contract_1/STUDENT_RESEARCH_CONTRACT.json", _contract_payload(timeframe="1w"))
    workflow_dir = _write_json(tmp_path / "reports/student_workflow_1/workflow_manifest.json", _workflow_payload(timeframe="1d"))
    _write_json(workflow_dir / "BACKTEST_ASSUMPTION_CARD.json", _assumption_payload(timeframe="1d"))

    result = StudentContractCheckService().run(contract=str(contract_dir), workflow=str(workflow_dir))

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "CONTRACT_DRIFT"
    assert any(item["field"] == "timeframe" and item["status"] == "FAIL" for item in result.artifacts["checks"])
    assert any(item["id"] == "contract_drift:timeframe" for item in result.artifacts["blockers"])


def test_student_contract_check_blocks_assumption_card_drift(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    contract_dir = _write_json(tmp_path / "reports/student_research_contract_1/STUDENT_RESEARCH_CONTRACT.json", _contract_payload(timeframe="1w"))
    workflow_dir = _write_json(tmp_path / "reports/student_workflow_1/workflow_manifest.json", _workflow_payload(timeframe="1w"))
    _write_json(workflow_dir / "BACKTEST_ASSUMPTION_CARD.json", _assumption_payload(timeframe="1d"))

    result = StudentContractCheckService().run(contract=str(contract_dir), workflow=str(workflow_dir))

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "CONTRACT_DRIFT"
    assert any(item["field"] == "assumption.timeframe" and item["status"] == "FAIL" for item in result.artifacts["checks"])


def test_student_contract_check_finds_latest_by_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_json(tmp_path / "reports/student_research_contract_1/STUDENT_RESEARCH_CONTRACT.json", _contract_payload(session_id="alice"))
    workflow_dir = _write_json(tmp_path / "reports/student_workflow_1/workflow_manifest.json", _workflow_payload(session_id="alice"))
    _write_json(workflow_dir / "BACKTEST_ASSUMPTION_CARD.json", _assumption_payload())

    result = StudentContractCheckService().run(session_id="alice")

    assert result.status == "VALID"
    assert result.artifacts["contract_source"]["found"] is True
    assert result.artifacts["workflow_source"]["found"] is True


def test_student_contract_check_blocks_missing_evidence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentContractCheckService().run(session_id="missing")

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "CONTRACT_CHECK_BLOCKED"
    assert any(item["id"] == "contract_missing" for item in result.artifacts["blockers"])
    assert any(item["id"] == "workflow_missing" for item in result.artifacts["blockers"])
