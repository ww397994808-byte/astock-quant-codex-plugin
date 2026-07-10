import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from audit.adjustment_leak_checker import AdjustmentLeakChecker
from core.order import Order
from core.portfolio import Portfolio
from core.risk_manager import RiskManager
from data_quality.data_quality_checker import DataQualityChecker
from examples.sample_data_generator import generate_intraday_sample_data, generate_sample_data
from market_data.adjustment import AdjustmentEngine
from market_data.corporate_actions import CorporateAction, write_sample_corporate_actions
from market_data.csv_intraday_provider import CSVIntradayProvider
from market_data.intraday_calendar import IntradayCalendar
from market_data.parquet_store import ParquetStore
from market_data.resampler import Resampler
from market_data.trading_session import TradingSession
from stress_tests.stress_data_generator import StressDataGenerator


ROOT = Path(__file__).resolve().parents[1]


def load_10m_rows():
    path = generate_intraday_sample_data(timeframe="10m")
    return ParquetStore().load_bars("601088.SH", "10m")


def test_10min_sessions_do_not_cross_midday():
    sessions = TradingSession().generate_sessions(datetime(2024, 1, 2).date(), "10m")
    assert all(not (s.time().hour == 11 and e.time().hour == 13) for s, e in sessions)
    assert len(sessions) == 24


def test_1h_sessions_do_not_cross_midday():
    sessions = TradingSession().generate_sessions(datetime(2024, 1, 2).date(), "1h")
    assert len(sessions) == 4
    assert sessions[1][1].strftime("%H:%M") == "11:30"
    assert sessions[2][0].strftime("%H:%M") == "13:00"


def test_resample_10m_to_1h():
    rows = load_10m_rows()[:24]
    out = Resampler().resample(rows, "1h")
    assert len(out) == 4
    assert out[0]["timeframe"] == "1h"


def test_resample_10m_to_1d():
    rows = load_10m_rows()[:24]
    out = Resampler().resample(rows, "1d")
    assert len(out) == 1
    assert out[0]["volume"] == sum(r["volume"] for r in rows)


def test_non_trading_time_bar_detected():
    rows = load_10m_rows()[:1]
    rows[0]["datetime"] = datetime(2024, 1, 2, 12, 0)
    assert DataQualityChecker().check(rows)["status"] == "INVALID"


def test_midday_bar_detected():
    rows = load_10m_rows()[:1]
    rows[0]["datetime"] = datetime(2024, 1, 2, 11, 30)
    assert DataQualityChecker().check(rows)["status"] == "INVALID"


def test_duplicate_datetime_detected():
    rows = load_10m_rows()[:2]
    rows[1]["datetime"] = rows[0]["datetime"]
    assert DataQualityChecker().check(rows)["status"] == "INVALID"


def test_missing_bar_detected():
    rows = load_10m_rows()[:23]
    report = DataQualityChecker().check(rows)
    assert any("bar 数量异常" in f["message"] for f in report["findings"])


def test_cli_generate_1h():
    result = subprocess.run([sys.executable, "cli.py", "generate-sample-data", "--timeframe", "1h", "--symbol", "601088.SH"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0
    assert (ROOT / "data/parquet/1h/601088.SH.parquet").exists()


def test_cli_generate_10m():
    result = subprocess.run([sys.executable, "cli.py", "generate-sample-data", "--timeframe", "10m", "--symbol", "601088.SH"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0
    assert (ROOT / "data/parquet/10m/601088.SH.parquet").exists()


def test_t_plus_1_intraday_same_day_sell_blocked():
    p = Portfolio(100000)
    p.positions.buy("601088.SH", 100, datetime(2024, 1, 2, 10, 0))
    order = Order("601088.SH", "SELL", 100, datetime(2024, 1, 2, 13, 50), datetime(2024, 1, 2, 14, 0), timeframe="10m")
    assert not RiskManager().check_order(order, p, 10, 5).ok


def test_t_plus_1_next_day_sell_allowed():
    p = Portfolio(100000)
    p.positions.buy("601088.SH", 100, datetime(2024, 1, 2, 10, 0))
    p.positions.release_after_close(datetime(2024, 1, 3, 9, 30))
    order = Order("601088.SH", "SELL", 100, datetime(2024, 1, 3, 9, 40), datetime(2024, 1, 3, 9, 50), timeframe="10m")
    assert RiskManager().check_order(order, p, 10, 5).ok


def test_parquet_store_save_load_has_symbol():
    rows = load_10m_rows()[:2]
    path = ParquetStore().save_bars("TEST.SH", "10m", rows)
    assert path.exists()
    assert ParquetStore().has_symbol("TEST.SH", "10m")


def test_csv_intraday_provider_loads_rows():
    path = generate_intraday_sample_data(timeframe="1h")
    rows = CSVIntradayProvider(path).load_bars("601088.SH", "1h")
    assert rows and rows[0]["timeframe"] == "1h"


def test_research_classifier_recognizes_intraday_terms():
    from research.pattern_classifier import PatternClassifier

    assert PatternClassifier().classify("1小时布林低吸").pattern == "swing"
    assert PatternClassifier().classify("10min波段").pattern == "swing"


def test_intraday_quality_report_written(tmp_path):
    DataQualityChecker().check(load_10m_rows()[:24], tmp_path)
    assert (tmp_path / "data_quality_report.md").exists()


def test_intraday_stress_scenarios_include_new_cases():
    scenarios = StressDataGenerator().generate(load_10m_rows()[:24])
    assert "morning_gap_limit_up" in scenarios
    assert "ten_min_limit_down_near" in scenarios


def test_signal_execute_datetime_in_orders():
    subprocess.run([sys.executable, "cli.py", "backtest", "--strategy", "boll_mean_reversion", "--symbol", "601088.SH", "--timeframe", "1h", "--data", "data/parquet/1h/601088.SH.parquet"], cwd=ROOT, check=True, capture_output=True, text=True)
    latest = (ROOT / "reports/latest.txt").read_text(encoding="utf-8").strip()
    text = (ROOT / "reports" / latest / "orders.csv").read_text(encoding="utf-8")
    assert "signal_datetime" in text and "execute_datetime" in text


def test_expected_bar_counts():
    cal = IntradayCalendar()
    assert cal.expected_bar_count("1h") == 4
    assert cal.expected_bar_count("10m") == 24
    assert cal.expected_bar_count("30m") == 8


def test_point_in_time_qfq_does_not_use_future_dividend():
    rows = load_10m_rows()[:2]
    action = CorporateAction("601088.SH", ex_date=datetime(2024, 1, 2), known_date=datetime(2024, 12, 1), action_type="cash", cash_dividend=10)
    adjusted = AdjustmentEngine().adjust(rows, [action], "point_in_time_qfq")
    assert adjusted[0]["adjust_factor"] == 1.0


def test_qfq_marks_future_leak_risk():
    rows = load_10m_rows()[:2]
    adjusted = AdjustmentEngine().adjust(rows, [], "qfq")
    assert adjusted[0]["FUTURE_LEAK_RISK"]
    assert AdjustmentLeakChecker().check(adjusted)["status"] == "INVALID"


def test_build_adjustment_factors_cli():
    generate_sample_data(symbol="601088.SH")
    result = subprocess.run([sys.executable, "cli.py", "build-adjustment-factors", "--symbol", "601088.SH", "--corporate-actions", "data/sample/corporate_actions_601088.csv"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0
    assert (ROOT / "data/adjustment_factors/601088.SH.parquet").exists()


def test_adjustment_leak_checker_detects_source_qfq(tmp_path):
    path = tmp_path / "s.py"
    path.write_text("data = load_all_history_qfq()", encoding="utf-8")
    assert AdjustmentLeakChecker().check(source_paths=[path])["status"] == "INVALID"


def test_cli_backtest_1h_point_in_time():
    subprocess.run([sys.executable, "cli.py", "generate-sample-data", "--timeframe", "1h", "--symbol", "601088.SH"], cwd=ROOT, check=True, capture_output=True, text=True)
    result = subprocess.run([sys.executable, "cli.py", "backtest", "--strategy", "boll_mean_reversion", "--symbol", "601088.SH", "--timeframe", "1h", "--adjust", "point_in_time_qfq", "--data", "data/parquet/1h/601088.SH.parquet"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0
    assert "status: VALID" in result.stdout


def test_cli_research_1h_point_in_time():
    result = subprocess.run([sys.executable, "cli.py", "research", "--direction", "中国神华1小时布林低吸波段，控制回撤", "--symbol", "601088.SH", "--timeframe", "1h", "--adjust", "point_in_time_qfq", "--data", "data/parquet/1h/601088.SH.parquet"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0
    assert "Research Agent V2 完成" in result.stdout

