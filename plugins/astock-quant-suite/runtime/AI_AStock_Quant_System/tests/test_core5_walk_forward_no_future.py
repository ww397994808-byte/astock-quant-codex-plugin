from __future__ import annotations

import csv
import json
from pathlib import Path

from research.core5_relative_strength_grid import config
from research.core5_relative_strength_grid.walk_forward import (
    run_walk_forward,
    validate_window_card,
    write_result_files,
)
from research.core5_relative_strength_grid.market import load_market


def _month_dates() -> list[str]:
    return [
        "2020-01-31",
        "2020-02-29",
        "2020-03-31",
        "2020-04-30",
        "2020-05-31",
        "2020-06-30",
        "2020-07-31",
        "2020-08-31",
        "2020-09-30",
        "2020-10-31",
        "2020-11-30",
        "2020-12-31",
        "2021-01-31",
    ]


def _param_equities() -> dict[str, list[dict[str, float]]]:
    dates = _month_dates()
    payload = {}
    for symbol_idx, symbol in enumerate(config.CORE5):
        symbol_params = []
        for param_idx in range(2):
            equity = {}
            value = 100.0 + symbol_idx * 3 + param_idx
            for step, date in enumerate(dates):
                value *= 1.0 + 0.005 * (symbol_idx + 1) + 0.001 * param_idx + step * 0.0001
                equity[date] = value
            symbol_params.append(equity)
        payload[symbol] = symbol_params
    return payload


def test_walk_forward_decisions_are_causal() -> None:
    rule = config.FixedRule(param_lookback_months=3, symbol_lookback_months=1, top_weights=(1.0,))

    result = run_walk_forward(_param_equities(), rule=rule, start_year="2020")

    assert result["walk_forward_audit"]["status"] == "VALID"
    assert result["decisions"]
    for decision in result["decisions"]:
        assert decision["causality_status"] == "PASS"
        assert decision["param_train_end_date"] == decision["rebalance_date"]
        assert decision["symbol_train_end_date"] == decision["rebalance_date"]
        assert decision["rebalance_date"] < decision["test_start_date"]
        assert decision["test_start_date"] == decision["next_date"]


def test_window_validation_rejects_future_test_overlap() -> None:
    rule = config.FixedRule(param_lookback_months=3, symbol_lookback_months=1, top_weights=(1.0,))
    bad_card = {
        "param_train_start_date": "2020-01-31",
        "param_train_end_date": "2020-04-30",
        "param_train_months": 4,
        "symbol_train_start_date": "2020-03-31",
        "symbol_train_end_date": "2020-04-30",
        "decision_made_after": "2020-04-30",
        "rebalance_date": "2020-04-30",
        "test_start_date": "2020-04-30",
        "test_end_date": "2020-04-30",
        "next_date": "2020-04-30",
        "causality_rule": "param_train_end_date <= rebalance_date < test_start_date",
    }

    findings = validate_window_card(bad_card, rule=rule)

    assert any("严格晚于调仓日" in item for item in findings)


def test_write_result_files_persists_audit_and_window_columns(tmp_path: Path) -> None:
    rule = config.FixedRule(param_lookback_months=3, symbol_lookback_months=1, top_weights=(1.0,))
    result = run_walk_forward(_param_equities(), rule=rule, start_year="2020")

    write_result_files(tmp_path, "2020", result)

    audit = json.loads((tmp_path / "start_2020_walk_forward_audit.json").read_text(encoding="utf-8"))
    assert audit["status"] == "VALID"
    with (tmp_path / "start_2020_decisions.csv").open(encoding="utf-8") as f:
        row = next(csv.DictReader(f))
    assert row["causality_status"] == "PASS"
    assert row["param_train_end_date"] == row["rebalance_date"]
    assert row["rebalance_date"] < row["test_start_date"]


def test_load_market_accepts_datetime_column(tmp_path: Path) -> None:
    path = tmp_path / "daily.csv"
    path.write_text(
        "datetime,open,high,low,close,volume\n"
        "2021-01-04,10,11,9,10.5,1000\n"
        "2021-01-05,10.5,12,10,11.5,1200\n",
        encoding="utf-8",
    )

    market = load_market("601088.SH", str(path), "2021-01-01", "2021-12-31")

    assert market.dates == ["2021-01-04", "2021-01-05"]
    assert market.rows[0]["time"].hour == 15
