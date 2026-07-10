from __future__ import annotations

from pathlib import Path

from services.student_future_leak_precheck_service import StudentFutureLeakPrecheckService


def test_student_future_leak_precheck_blocks_negative_shift(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentFutureLeakPrecheckService().run(code="df['signal'] = close.shift(-1) > close", session_id="alice")

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "LEAK_RISK_FOUND"
    assert result.artifacts["checker_report"]["high_count"] >= 1
    assert result.artifacts["safe_to_copy"] is False
    assert Path(result.report_path, "STUDENT_FUTURE_LEAK_PRECHECK.md").exists()
    assert Path(result.report_path, "submitted_strategy.py").exists()


def test_student_future_leak_precheck_blocks_centered_rolling(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentFutureLeakPrecheckService().run(code="signal = close.rolling(20, center=True).mean()")

    assert result.status == "INVALID"
    assert any("center" in item["message"] or "居中" in item["message"] for item in result.artifacts["checker_report"]["findings"])


def test_student_future_leak_precheck_allows_causal_history_window(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = "ma20 = close.rolling(20).mean().shift(1)\nsignal = close > ma20\n"

    result = StudentFutureLeakPrecheckService().run(code=code, strategy_name="ma_break")

    assert result.status == "VALID"
    assert result.artifacts["status"] == "LEAK_CHECK_VALID"
    assert result.artifacts["safe_to_copy"] is True
    assert result.artifacts["checker_report"]["high_count"] == 0


def test_student_future_leak_precheck_reads_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    strategy = tmp_path / "strategy.py"
    strategy.write_text("signal = df['close'].rolling(20).mean()\n", encoding="utf-8")

    result = StudentFutureLeakPrecheckService().run(file=str(strategy))

    assert result.status == "VALID"
    assert result.artifacts["source_type"] == "file"
    assert result.artifacts["source_path"] == str(strategy)


def test_student_future_leak_precheck_requires_code(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentFutureLeakPrecheckService().run()

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "MISSING_CODE"
    assert result.artifacts["blockers"][0]["id"] == "missing_code"
