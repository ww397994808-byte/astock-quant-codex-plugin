from __future__ import annotations

import json
from pathlib import Path

from services.pretrade_package_service import PretradePackageService
from services.pretrade_runbook_refresh_service import PretradeRunbookRefreshService


def _write_candidate(reports: Path) -> Path:
    run_dir = reports / "repair_candidate_1"
    run_dir.mkdir(parents=True)
    (run_dir / "backtest_plan.yaml").write_text(
        "status: VALID\nblockers: []\npromotion_policy:\n  qmt_allowed: true\n",
        encoding="utf-8",
    )
    (run_dir / "audit_report.md").write_text("# Audit Report\n\n状态：VALID\n", encoding="utf-8")
    (run_dir / "readiness_report.md").write_text("readiness: PAPER_READY\n", encoding="utf-8")
    (run_dir / "paper_observation.json").write_text(json.dumps({"status": "VALID"}), encoding="utf-8")
    (run_dir / "paper_observation_report.md").write_text("status: VALID\n", encoding="utf-8")
    (run_dir / "performance.json").write_text(json.dumps({"trade_count": 10}), encoding="utf-8")
    (run_dir / "trades.csv").write_text("symbol,action\n601088.SH,BUY\n", encoding="utf-8")
    dsl = reports / "SELECTED_REPAIR_DSL.yaml"
    dsl.write_text("symbols:\n- 601088.SH\n", encoding="utf-8")
    promotion = reports / "REPAIR_DSL_PROMOTION.json"
    promotion.write_text(
        json.dumps({
            "selected_variant_id": "expand_dev_0001_hold_10",
            "selected_dsl_path": str(dsl),
            "source_report_path": str(run_dir),
            "candidate": {"report_path": str(run_dir)},
        }),
        encoding="utf-8",
    )
    return promotion


def test_pretrade_package_blocks_before_qmt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reports = tmp_path / "reports"
    reports.mkdir()
    promotion = _write_candidate(reports)

    result = PretradePackageService().run(str(promotion))

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BLOCKED_BEFORE_PRETRADE"
    assert any(item["category"] == "QMT 只读" for item in result.artifacts["fix_plan"])
    assert any(item["runbook_type"] == "stop_trading" for item in result.artifacts["fix_plan"])
    assert result.artifacts["runbook_summary"]["blocked"] >= 1
    assert result.artifacts["runbook_summary"]["pending"] >= 1
    assert "python3 cli.py qmt-check" in result.artifacts["required_next_commands"][0]
    report = Path(result.report_path) / "PRETRADE_READINESS_PACKAGE.md"
    assert report.exists()
    text = report.read_text(encoding="utf-8")
    assert "不允许跳过 pretrade-check" in text
    assert "## 修复清单" in text
    assert "dry_run" in text
    runbook = Path(result.report_path) / "PRETRADE_RUNBOOK.md"
    assert runbook.exists()
    runbook_text = runbook.read_text(encoding="utf-8")
    assert "## 停止推进事项" in runbook_text
    assert "stop_trading: True" in runbook_text
    assert "blocked:" in runbook_text
    assert "status: blocked" in runbook_text


def test_pretrade_package_ready_after_qmt_but_pretrade_still_blocks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reports = tmp_path / "reports"
    reports.mkdir()
    promotion = _write_candidate(reports)
    qmt_dir = reports / "qmt_readonly_1"
    qmt_dir.mkdir()
    (qmt_dir / "qmt_account_snapshot.json").write_text(
        json.dumps({"ok": True, "connected": True, "checks": {"qmt_connected": True, "account_available": True}}),
        encoding="utf-8",
    )
    (qmt_dir / "qmt_readonly_report.md").write_text("status: VALID\n", encoding="utf-8")

    result = PretradePackageService().run(str(promotion), qmt_run_id="qmt_readonly_1")

    assert result.status == "VALID"
    assert result.artifacts["status"] == "READY_FOR_PRETRADE_CHECK"
    assert result.artifacts["pretrade_status"] == "INVALID"
    assert "enable_real_trade 未开启" in result.artifacts["pretrade_failures"]
    fix_by_title = {item["title"]: item for item in result.artifacts["fix_plan"]}
    assert fix_by_title["enable_real_trade 未开启"]["category"] == "人工安全开关"
    assert fix_by_title["enable_real_trade 未开启"]["can_auto_fix"] is False
    assert fix_by_title["enable_real_trade 未开启"]["runbook_type"] == "manual_confirmation"
    assert fix_by_title["enable_real_trade 未开启"]["status"] == "pending"
    assert fix_by_title["未输入 CONFIRM_REAL_TRADE"]["category"] == "人工确认"
    assert (Path(result.report_path) / "PRETRADE_RUNBOOK.json").exists()
    evidence = Path(result.report_path) / "evidence"
    assert (evidence / "qmt_account_snapshot.json").exists()
    assert (evidence / "pretrade_report.md").exists()


def test_pretrade_runbook_refresh_marks_resolved_items(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reports = tmp_path / "reports"
    reports.mkdir()
    promotion = _write_candidate(reports)
    initial = PretradePackageService().run(str(promotion))

    qmt_dir = reports / "qmt_readonly_1"
    qmt_dir.mkdir()
    (qmt_dir / "qmt_account_snapshot.json").write_text(
        json.dumps({"ok": True, "connected": True, "checks": {"qmt_connected": True, "account_available": True}}),
        encoding="utf-8",
    )
    (qmt_dir / "qmt_readonly_report.md").write_text("status: VALID\n", encoding="utf-8")

    result = PretradeRunbookRefreshService().run(initial.report_path, qmt_run_id="qmt_readonly_1")

    assert result.status == "VALID"
    assert result.artifacts["status"] == "READY_FOR_PRETRADE_CHECK"
    assert result.artifacts["summary"]["verified"] >= 1
    assert result.artifacts["summary"]["pending"] >= 1
    titles_by_status = {}
    for item in result.artifacts["runbook_items"]:
        titles_by_status.setdefault(item["status"], set()).add(item["title"])
    assert "QMT 只读检查未通过" in titles_by_status["verified"]
    assert "enable_real_trade 未开启" in titles_by_status["pending"]
    report = Path(result.report_path) / "PRETRADE_RUNBOOK_REFRESH.md"
    assert report.exists()
    text = report.read_text(encoding="utf-8")
    assert "## 本次已解除" in text
    assert "QMT 只读检查未通过" in text


def test_pretrade_runbook_refresh_keeps_stop_trading_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reports = tmp_path / "reports"
    reports.mkdir()
    promotion = _write_candidate(reports)
    initial = PretradePackageService().run(str(promotion))

    result = PretradeRunbookRefreshService().run(
        str(Path(initial.report_path) / "PRETRADE_READINESS_PACKAGE.json")
    )

    assert result.status == "INVALID"
    blocked = [item for item in result.artifacts["runbook_items"] if item["status"] == "blocked"]
    assert any(item["title"] == "标的不可交易或停牌" for item in blocked)
    assert result.artifacts["summary"]["blocked"] >= 1
