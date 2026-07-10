import csv
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from core.readiness import StrategyReadiness, classify_readiness
from data_quality.corporate_action_checker import CorporateActionChecker
from data_quality.data_quality_checker import DataQualityChecker
from data_quality.trading_calendar_checker import TradingCalendarChecker
from examples.sample_data_generator import generate_sample_data
from metrics.metrics_report import build_metrics
from metrics.risk_metrics import calmar, max_drawdown, recovery_time, sortino
from metrics.return_metrics import annual_return, cagr, monthly_returns
from metrics.stability_metrics import monthly_win_rate, rolling_return, rolling_sharpe, yearly_return_distribution
from metrics.trade_metrics import trade_metrics
from services.explain_report_service import ExplainReportService
from stress_tests.stress_data_generator import StressDataGenerator
from stress_tests.stress_runner import StressRunner
from validators.config_validator import ConfigValidator
from validators.qmt_validator import QMTValidator
from validators.research_validator import ResearchValidator
from validators.strategy_validator import StrategyValidator


ROOT = Path(__file__).resolve().parents[1]


def sample_rows():
    return [
        {"date": datetime(2024, 1, 1) + timedelta(days=i), "open": 10 + i, "high": 11 + i, "low": 9 + i, "close": 10 + i, "volume": 1000, "amount": 10000, "symbol": "A", "name": "A", "is_st": False, "board": "main", "paused": False}
        for i in range(5)
    ]


def test_data_quality_detects_duplicate_date():
    rows = sample_rows()
    rows[1]["date"] = rows[0]["date"]
    assert DataQualityChecker().check(rows)["status"] == "INVALID"


def test_data_quality_detects_reverse_date():
    rows = sample_rows()
    rows[2]["date"] = rows[0]["date"] - timedelta(days=1)
    assert DataQualityChecker().check(rows)["status"] == "INVALID"


def test_data_quality_detects_price_invalid():
    rows = sample_rows()
    rows[0]["close"] = 0
    assert DataQualityChecker().check(rows)["status"] == "INVALID"


def test_data_quality_detects_high_low_invalid():
    rows = sample_rows()
    rows[0]["high"] = 8
    assert DataQualityChecker().check(rows)["status"] == "INVALID"


def test_data_quality_detects_open_outside_range():
    rows = sample_rows()
    rows[0]["open"] = 20
    assert DataQualityChecker().check(rows)["status"] == "INVALID"


def test_data_quality_detects_close_outside_range():
    rows = sample_rows()
    rows[0]["close"] = 20
    assert DataQualityChecker().check(rows)["status"] == "INVALID"


def test_data_quality_detects_negative_volume():
    rows = sample_rows()
    rows[0]["volume"] = -1
    assert DataQualityChecker().check(rows)["status"] == "INVALID"


def test_data_quality_detects_negative_amount():
    rows = sample_rows()
    rows[0]["amount"] = -1
    assert DataQualityChecker().check(rows)["status"] == "INVALID"


def test_data_quality_detects_price_jump():
    rows = sample_rows()
    rows[1]["close"] = 20
    report = DataQualityChecker().check(rows)
    assert any("30%" in f["message"] for f in report["findings"])


def test_calendar_detects_weekend_data():
    rows = sample_rows()
    rows[0]["date"] = datetime(2024, 1, 6)
    assert TradingCalendarChecker().check(rows)["findings"]


def test_corporate_action_checker_flags_gap():
    rows = sample_rows()
    rows[1]["open"] = rows[1]["close"] = 20
    report = CorporateActionChecker().check(rows)
    assert report["status"] == "WARNING"


def test_readiness_invalid_on_audit_failure():
    assert classify_readiness("INVALID") == StrategyReadiness.INVALID


def test_readiness_research_only_for_low_trade_count():
    assert classify_readiness("VALID", trade_count=1) == StrategyReadiness.RESEARCH_ONLY


def test_readiness_paper_ready():
    assert classify_readiness("VALID", trade_count=5, backtest_days=100) == StrategyReadiness.PAPER_READY


def test_readiness_live_candidate():
    assert classify_readiness("VALID", trade_count=10, backtest_days=600, multi_period_verified=True, multi_symbol_verified=True, risk_ok=True) == StrategyReadiness.LIVE_CANDIDATE


def test_return_metrics():
    equity = [100, 110, 121]
    assert cagr(equity) > 0
    assert annual_return(equity) > 0


def test_risk_metrics():
    equity = [100, 120, 90, 130]
    mdd = max_drawdown(equity)
    assert mdd < 0
    assert calmar(0.3, mdd) > 0
    assert recovery_time(equity) >= 1
    assert isinstance(sortino([0.01, -0.02, 0.03]), float)


def test_trade_metrics():
    result = trade_metrics([{"action": "SELL", "amount": 1000, "total_fee": 5}])
    assert result["win_rate"] == 1


def test_stability_metrics():
    rows = [{"date": f"2024-{m:02d}-01", "equity": 100 + m} for m in range(1, 13)]
    assert monthly_win_rate(rows) >= 0
    assert yearly_return_distribution(rows)


def test_build_metrics_contains_sections():
    rows = [{"date": f"2024-01-{i+1:02d}", "equity": 100 + i} for i in range(30)]
    metrics = build_metrics(rows, [])
    assert {"return", "risk", "trade", "stability"}.issubset(metrics)


def test_stress_generator_has_eight_scenarios():
    scenarios = StressDataGenerator().generate(sample_rows() * 10)
    assert {"limit_up", "limit_down", "paused_30d", "extreme_volatility", "zero_volume", "gap", "bull", "bear"}.issubset(scenarios)


def test_stress_runner_writes_report(tmp_path):
    StressRunner().run(sample_rows() * 10, tmp_path)
    assert (tmp_path / "stress_report.md").exists()


def test_strategy_validator_detects_invalid_ma_params():
    assert StrategyValidator().validate({"short_window": 20, "long_window": 5})


def test_research_validator_detects_large_space():
    issues = ResearchValidator().validate_search_space({"a": list(range(20)), "b": list(range(20))}, max_experiments=100)
    assert issues


def test_qmt_validator_flags_real_trade():
    issues = QMTValidator().validate({"enable_real_trade": True, "dry_run": False})
    assert issues


def test_config_validator_passes_required_files(monkeypatch):
    monkeypatch.chdir(ROOT)
    assert ConfigValidator().validate() == []


def test_doctor_cli_generates_report():
    result = subprocess.run([sys.executable, "cli.py", "doctor"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0
    assert (ROOT / "doctor_report.md").exists()


def test_explain_report_generates_user_friendly_file(monkeypatch):
    monkeypatch.chdir(ROOT)
    subprocess.run([sys.executable, "cli.py", "backtest", "--strategy", "boll_mean_reversion", "--symbol", "601088.SH", "--data", "data/sample/601088.csv"], cwd=ROOT, check=True, capture_output=True, text=True)
    result = ExplainReportService().run("latest")
    text = Path(result.report_path).read_text(encoding="utf-8")
    assert "每承担 1 单位最大回撤" in text or "审计解释" in text


def test_backtest_generates_v4_reports():
    result = subprocess.run([sys.executable, "cli.py", "backtest", "--strategy", "boll_mean_reversion", "--symbol", "601088.SH", "--data", "data/sample/601088.csv"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0
    latest = (ROOT / "reports/latest.txt").read_text(encoding="utf-8").strip()
    run_dir = ROOT / "reports" / latest
    for name in ["data_quality_report.md", "readiness_report.md", "metrics_report.md", "stress_report.md"]:
        assert (run_dir / name).exists()
