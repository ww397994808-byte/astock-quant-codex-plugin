import csv
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from core.readiness import StrategyReadiness, classify_readiness
from data_quality.data_quality_checker import DataQualityChecker
from examples.sample_data_generator import generate_intraday_sample_data
from market_data.adjustment import AdjustmentEngine
from market_data.corporate_actions import CorporateAction
from market_data.parquet_store import ParquetStore


ROOT = Path(__file__).resolve().parents[1]


def pit_rows():
    return [
        {"datetime": datetime(2024, 1, 2, 9, 30), "date": datetime(2024, 1, 2, 9, 30), "timeframe": "1h", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 100, "amount": 10000, "symbol": "601088.SH", "name": "x", "is_st": False, "board": "main", "paused": False},
        {"datetime": datetime(2024, 1, 10, 9, 30), "date": datetime(2024, 1, 10, 9, 30), "timeframe": "1h", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 100, "amount": 10000, "symbol": "601088.SH", "name": "x", "is_st": False, "board": "main", "paused": False},
    ]


def test_point_in_time_qfq_before_known_date_does_not_affect_price():
    action = CorporateAction("601088.SH", datetime(2024, 1, 2), datetime(2024, 1, 5), "cash", cash_dividend=10)
    adjusted = AdjustmentEngine().adjust(pit_rows(), [action], "point_in_time_qfq")
    assert adjusted[0]["close"] == 100
    assert adjusted[0]["adjust_factor"] == 1.0


def test_point_in_time_qfq_after_known_date_affects_price():
    action = CorporateAction("601088.SH", datetime(2024, 1, 2), datetime(2024, 1, 5), "cash", cash_dividend=10)
    adjusted = AdjustmentEngine().adjust(pit_rows(), [action], "point_in_time_qfq")
    assert adjusted[1]["close"] < 100
    assert adjusted[1]["adjust_factor"] < 1.0


def test_strategy_history_does_not_contain_future_adjusted_price():
    future_action = CorporateAction("601088.SH", datetime(2024, 1, 2), datetime(2024, 12, 1), "cash", cash_dividend=10)
    adjusted = AdjustmentEngine().adjust(pit_rows(), [future_action], "point_in_time_qfq")
    history_at_jan10 = adjusted[:2]
    assert all(row["adjust_factor"] == 1.0 for row in history_at_jan10)


def test_qfq_readiness_highest_research_only():
    assert classify_readiness("VALID", trade_count=20, backtest_days=800, multi_period_verified=True, multi_symbol_verified=True, risk_ok=True, adjust_type="qfq") == StrategyReadiness.RESEARCH_ONLY


def test_point_in_time_qfq_can_be_paper_ready():
    assert classify_readiness("VALID", trade_count=5, backtest_days=100, adjust_type="point_in_time_qfq") == StrategyReadiness.PAPER_READY


def test_1h_signal_execute_datetime_correct():
    subprocess.run([sys.executable, "cli.py", "generate-sample-data", "--timeframe", "1h", "--symbol", "601088.SH"], cwd=ROOT, check=True, capture_output=True, text=True)
    subprocess.run([sys.executable, "cli.py", "backtest", "--strategy", "boll_mean_reversion", "--symbol", "601088.SH", "--timeframe", "1h", "--data", "data/parquet/1h/601088.SH.parquet"], cwd=ROOT, check=True, capture_output=True, text=True)
    latest = (ROOT / "reports/latest.txt").read_text(encoding="utf-8").strip()
    with (ROOT / "reports" / latest / "orders.csv").open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            assert row["timeframe"] == "1h"
            assert row["execute_datetime"] > row["signal_datetime"]


def test_10m_signal_execute_datetime_correct():
    subprocess.run([sys.executable, "cli.py", "generate-sample-data", "--timeframe", "10m", "--symbol", "601088.SH"], cwd=ROOT, check=True, capture_output=True, text=True)
    subprocess.run([sys.executable, "cli.py", "backtest", "--strategy", "boll_mean_reversion", "--symbol", "601088.SH", "--timeframe", "10m", "--data", "data/parquet/10m/601088.SH.parquet"], cwd=ROOT, check=True, capture_output=True, text=True)
    latest = (ROOT / "reports/latest.txt").read_text(encoding="utf-8").strip()
    with (ROOT / "reports" / latest / "orders.csv").open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            assert row["timeframe"] == "10m"
            assert row["execute_datetime"] > row["signal_datetime"]


def test_missing_morning_bar_detected():
    rows = ParquetStore().load_bars("601088.SH", "10m")
    afternoon_only = [row for row in rows if row["datetime"].hour >= 13][:12]
    findings = DataQualityChecker().check(afternoon_only)["findings"]
    assert any("上午缺失" in f["message"] for f in findings)


def test_missing_afternoon_bar_detected():
    rows = ParquetStore().load_bars("601088.SH", "10m")
    morning_only = [row for row in rows if row["datetime"].hour < 12][:12]
    findings = DataQualityChecker().check(morning_only)["findings"]
    assert any("下午缺失" in f["message"] for f in findings)


def test_csv_backed_parquet_documented():
    text = (ROOT / "docs/architecture/intraday_data_layer.md").read_text(encoding="utf-8")
    assert "CSV-backed" in text
    assert "pyarrow" in text


def test_parquet_store_api_real_parquet_compatible():
    store = ParquetStore()
    for method in ["save_bars", "load_bars", "list_symbols", "has_symbol"]:
        assert hasattr(store, method)


def test_research_plan_records_timeframe():
    subprocess.run([sys.executable, "cli.py", "research", "--direction", "中国神华1小时布林低吸波段，控制回撤", "--symbol", "601088.SH", "--timeframe", "1h", "--adjust", "point_in_time_qfq", "--data", "data/parquet/1h/601088.SH.parquet"], cwd=ROOT, check=True, capture_output=True, text=True)
    latest = (ROOT / "reports/latest.txt").read_text(encoding="utf-8").strip()
    text = (ROOT / "reports" / latest / "research_plan.md").read_text(encoding="utf-8")
    assert "周期：1h" in text


def test_research_plan_records_adjust():
    latest = (ROOT / "reports/latest.txt").read_text(encoding="utf-8").strip()
    text = (ROOT / "reports" / latest / "research_plan.md").read_text(encoding="utf-8")
    assert "复权方式：point_in_time_qfq" in text


def test_final_research_report_explains_timeframe():
    latest = (ROOT / "reports/latest.txt").read_text(encoding="utf-8").strip()
    text = (ROOT / "reports" / latest / "final_research_report.md").read_text(encoding="utf-8")
    assert "研究周期：1h" in text


def test_final_research_report_explains_adjust():
    latest = (ROOT / "reports/latest.txt").read_text(encoding="utf-8").strip()
    text = (ROOT / "reports" / latest / "final_research_report.md").read_text(encoding="utf-8")
    assert "复权方式：point_in_time_qfq" in text


def test_v5_reality_check_doc_exists():
    text = (ROOT / "docs/architecture/v5_reality_check.md").read_text(encoding="utf-8")
    assert "point_in_time_qfq" in text
    assert "CSV-backed" in text

