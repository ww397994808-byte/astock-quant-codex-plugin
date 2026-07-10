from __future__ import annotations

from pathlib import Path

from services.student_backtest_plan_precheck_service import StudentBacktestPlanPrecheckService


def test_student_backtest_plan_precheck_ready_for_weekly_swing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentBacktestPlanPrecheckService().run(
        idea="中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究",
        session_id="alice",
    )

    assert result.status == "VALID"
    assert result.artifacts["status"] == "BACKTEST_PLAN_READY"
    assert result.artifacts["backtest_plan"]["strategy_pattern"] == "swing"
    assert result.artifacts["backtest_plan"]["timeframe"] == "1w"
    assert result.artifacts["backtest_plan"]["execution_model"]["fill_bar"] == "next_bar_open"
    assert result.artifacts["safe_to_copy"] is True
    assert Path(result.report_path, "STUDENT_BACKTEST_PLAN_PRECHECK.md").exists()
    assert Path(result.report_path, "backtest_plan_precheck.yaml").exists()


def test_student_backtest_plan_precheck_blocks_bad_rotation_timeframe(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentBacktestPlanPrecheckService().run(
        idea="煤炭银行电力1小时轮动，选强势行业，控制回撤",
        timeframe="1h",
    )

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BLOCKED_BACKTEST_PLAN"
    assert result.artifacts["safe_to_copy"] is False
    assert any("不支持 1h 周期" in item["message"] for item in result.artifacts["blockers"])


def test_student_backtest_plan_precheck_blocks_crypto_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentBacktestPlanPrecheckService().run(
        idea="BTC 5分钟均线突破，接交易所合约实盘",
        timeframe="5m",
    )

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "WRONG_ASSET_VERSION"
    assert any(item["id"] == "wrong_asset_version" for item in result.artifacts["blockers"])


def test_student_backtest_plan_precheck_can_force_grid_pattern(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentBacktestPlanPrecheckService().run(
        idea="红利ETF日线分层买卖，跌2%买一层，涨2%卖一层",
        strategy_pattern="grid",
    )

    assert result.status == "VALID"
    assert result.artifacts["backtest_plan"]["strategy_pattern"] == "grid"
    assert any(item["id"] == "grid_state_cash" for item in result.artifacts["assumption_checks"])


def test_student_backtest_plan_precheck_requires_idea(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentBacktestPlanPrecheckService().run()

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "MISSING_IDEA"
    assert result.artifacts["blockers"][0]["id"] == "missing_idea"
