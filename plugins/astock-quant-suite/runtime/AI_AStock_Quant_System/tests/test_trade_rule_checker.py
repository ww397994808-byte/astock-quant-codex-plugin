import csv
from pathlib import Path

from audit.trade_rule_checker import TradeRuleChecker


def test_trade_rule_checker_detects_t_plus_1_violation(tmp_path: Path):
    trades = tmp_path / "trades.csv"
    with trades.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "action", "quantity", "price", "amount", "signal_time", "execute_time", "commission", "stamp_tax", "transfer_fee", "total_fee", "reason"])
        writer.writeheader()
        writer.writerow({"symbol": "601088.SH", "action": "BUY", "quantity": 100, "price": 10, "amount": 1000, "signal_time": "2024-01-01", "execute_time": "2024-01-02", "commission": 5, "stamp_tax": 0, "transfer_fee": 0.01, "total_fee": 5.01, "reason": ""})
        writer.writerow({"symbol": "601088.SH", "action": "SELL", "quantity": 100, "price": 10, "amount": 1000, "signal_time": "2024-01-01", "execute_time": "2024-01-02", "commission": 5, "stamp_tax": 0.5, "transfer_fee": 0.01, "total_fee": 5.51, "reason": ""})
    for name in ["orders.csv", "positions.csv"]:
        (tmp_path / name).write_text("\n", encoding="utf-8")
    report = TradeRuleChecker().check(tmp_path)
    assert report["status"] == "INVALID"


def _write_orders(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        fields = ["symbol", "action", "quantity", "signal_time", "execute_time", "signal_datetime", "execute_datetime", "timeframe", "price", "status", "reason"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _empty_trade_files(tmp_path: Path) -> None:
    (tmp_path / "trades.csv").write_text("symbol,action,quantity,price,amount,signal_time,execute_time,commission,stamp_tax,transfer_fee,total_fee,reason\n", encoding="utf-8")
    (tmp_path / "positions.csv").write_text("cash,total_position,available_position\n100000,0,0\n", encoding="utf-8")


def test_trade_rule_checker_blocks_same_daily_bar_execution(tmp_path: Path):
    _empty_trade_files(tmp_path)
    _write_orders(tmp_path / "orders.csv", [{
        "symbol": "601088.SH",
        "action": "BUY",
        "quantity": 100,
        "signal_time": "2024-01-02",
        "execute_time": "2024-01-02",
        "signal_datetime": "2024-01-02 14:59:00",
        "execute_datetime": "2024-01-02 15:00:00",
        "timeframe": "1d",
        "price": 10,
        "status": "FILLED",
        "reason": "",
    }])

    report = TradeRuleChecker().check(tmp_path)

    assert report["status"] == "INVALID"
    assert any("同一根 1d K 线" in item["message"] for item in report["findings"])


def test_trade_rule_checker_blocks_same_week_execution(tmp_path: Path):
    _empty_trade_files(tmp_path)
    _write_orders(tmp_path / "orders.csv", [{
        "symbol": "601088.SH",
        "action": "BUY",
        "quantity": 100,
        "signal_time": "2024-01-02",
        "execute_time": "2024-01-05",
        "signal_datetime": "2024-01-02 15:00:00",
        "execute_datetime": "2024-01-05 09:30:00",
        "timeframe": "1w",
        "price": 10,
        "status": "FILLED",
        "reason": "",
    }])

    report = TradeRuleChecker().check(tmp_path)

    assert report["status"] == "INVALID"
    assert any("同一根 1w K 线" in item["message"] for item in report["findings"])


def test_trade_rule_checker_blocks_same_intraday_bucket(tmp_path: Path):
    _empty_trade_files(tmp_path)
    _write_orders(tmp_path / "orders.csv", [{
        "symbol": "601088.SH",
        "action": "BUY",
        "quantity": 100,
        "signal_time": "2024-01-02",
        "execute_time": "2024-01-02",
        "signal_datetime": "2024-01-02 09:31:00",
        "execute_datetime": "2024-01-02 09:39:00",
        "timeframe": "10m",
        "price": 10,
        "status": "FILLED",
        "reason": "",
    }])

    report = TradeRuleChecker().check(tmp_path)

    assert report["status"] == "INVALID"
    assert any("同一根 10m K 线" in item["message"] for item in report["findings"])


def test_trade_rule_checker_allows_next_bar_execution(tmp_path: Path):
    _empty_trade_files(tmp_path)
    _write_orders(tmp_path / "orders.csv", [{
        "symbol": "601088.SH",
        "action": "BUY",
        "quantity": 100,
        "signal_time": "2024-01-02",
        "execute_time": "2024-01-03",
        "signal_datetime": "2024-01-02 15:00:00",
        "execute_datetime": "2024-01-03 09:30:00",
        "timeframe": "1d",
        "price": 10,
        "status": "FILLED",
        "reason": "",
    }])

    report = TradeRuleChecker().check(tmp_path)

    assert report["status"] == "VALID"
