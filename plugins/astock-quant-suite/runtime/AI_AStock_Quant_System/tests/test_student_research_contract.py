from __future__ import annotations

from pathlib import Path

from services.student_research_contract_service import StudentResearchContractService


def _minimal_project(root: Path) -> None:
    for dirname in [
        "config",
        "data/sample",
        "reports",
        "codex_skills/astock-quant-research/scripts",
        "tasks",
    ]:
        (root / dirname).mkdir(parents=True, exist_ok=True)
    (root / "cli.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "QUICK_START_FOR_STUDENTS.md").write_text("# quick\n", encoding="utf-8")
    (root / "codex_skills/astock-quant-research/SKILL.md").write_text("---\nname: astock\n---\n", encoding="utf-8")
    (root / "codex_skills/astock-quant-research/scripts/run_astock_workflow.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "data/sample/601088.csv").write_text("date,open,high,low,close,volume\n", encoding="utf-8")
    from services.student_doctor_service import StudentDoctorService

    (root / "tasks/task_registry.py").write_text(
        "\n".join(f'"{name}": object,' for name in StudentDoctorService.REQUIRED_COMMANDS),
        encoding="utf-8",
    )
    safe_qmt = """
dry_run: true
enable_real_trade: false
account_id: "demo"
mini_qmt_path: "/tmp/mini_qmt"
"""
    (root / "config/qmt_config.example.yaml").write_text(safe_qmt, encoding="utf-8")
    (root / "config/qmt_config.yaml").write_text(safe_qmt, encoding="utf-8")


def test_student_research_contract_ready_with_causal_code(tmp_path, monkeypatch):
    _minimal_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    code = "ma20 = close.rolling(20).mean().shift(1)\nsignal = close > ma20\n"

    result = StudentResearchContractService().run(
        idea="中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究",
        code=code,
        session_id="alice",
    )

    assert result.status == "VALID"
    assert result.artifacts["status"] == "CONTRACT_READY"
    assert result.artifacts["contract_id"]
    assert result.artifacts["contract"]["strategy_pattern"] == "swing"
    assert result.artifacts["contract"]["timeframe"] == "1w"
    assert result.artifacts["safe_to_copy"] is True
    assert Path(result.report_path, "STUDENT_RESEARCH_CONTRACT.md").exists()
    assert Path(result.report_path, "research_contract.json").exists()


def test_student_research_contract_warns_when_code_not_bound(tmp_path, monkeypatch):
    _minimal_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = StudentResearchContractService().run(
        idea="中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究",
        session_id="alice",
    )

    assert result.status == "VALID"
    assert result.artifacts["status"] == "CONTRACT_READY"
    assert any(item["id"] == "future_leak_not_attached" for item in result.artifacts["warnings"])


def test_student_research_contract_blocks_future_leak_code(tmp_path, monkeypatch):
    _minimal_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = StudentResearchContractService().run(
        idea="中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究",
        code="signal = close.shift(-1) > close",
        session_id="alice",
    )

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "CONTRACT_BLOCKED"
    assert any(item["id"] in {"future_leak_blocked", "future_leak_contract_blocker"} for item in result.artifacts["blockers"])


def test_student_research_contract_blocks_bad_backtest_plan(tmp_path, monkeypatch):
    _minimal_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = StudentResearchContractService().run(
        idea="煤炭银行电力1小时轮动，选强势行业，控制回撤",
        timeframe="1h",
    )

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "CONTRACT_BLOCKED"
    assert any(item["id"] == "plan_blocked" for item in result.artifacts["blockers"])
