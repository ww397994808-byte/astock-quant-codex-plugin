import json
import subprocess
import sys
from pathlib import Path

from benchmarks.benchmark_runner import BenchmarkRunner
from data_acquisition.acquisition_agent import DataAcquisitionAgent
from data_acquisition.cache_manager import CacheManager
from data_acquisition.data_request import DataRequest
from data_acquisition.provider_router import ProviderRouter
from data_acquisition.symbol_resolver import SymbolResolver
from market_data.providers.provider_registry import provider_chain


ROOT = Path(__file__).resolve().parents[1]


def test_symbol_resolver_china_shenhua():
    assert SymbolResolver().resolve("中国神华")[0] == "601088.SH"


def test_symbol_resolver_dividend_etf():
    assert SymbolResolver().resolve("红利ETF")[0] == "510880.SH"


def test_symbol_resolver_fuzzy_shenhua():
    assert SymbolResolver().resolve("我想研究神华")[0] == "601088.SH"


def test_symbol_resolver_etf_type():
    assert SymbolResolver().resolve("红利ETF")[1] == "etf"


def test_symbol_resolver_index_type():
    assert SymbolResolver().resolve("沪深300")[1] == "index"


def test_provider_chain_order_local_qmt_akshare_tushare():
    names = [p.name for p in provider_chain()]
    assert names == ["local", "qmt", "akshare", "tushare"]


def test_qmt_before_akshare():
    names = [p.name for p in provider_chain()]
    assert names.index("qmt") < names.index("akshare")


def test_fetch_data_auto_download_and_cache():
    request = DataRequest("601088.SH", "1h")
    record = DataAcquisitionAgent().fetch(request)
    assert Path(record["path"]).exists()
    assert CacheManager().has(request)


def test_repeated_request_uses_local_cache():
    request = DataRequest("601088.SH", "1h")
    DataAcquisitionAgent().fetch(request)
    record = DataAcquisitionAgent().fetch(request)
    assert record["source"] == "local"
    assert record["downloaded"] is False


def test_data_status_existing_cache():
    request = DataRequest("601088.SH", "1h")
    DataAcquisitionAgent().fetch(request)
    status = DataAcquisitionAgent().status(request)
    assert status["exists"]
    assert status["latest_datetime"]


def test_fetch_data_cli():
    result = subprocess.run([sys.executable, "cli.py", "fetch-data", "--symbol", "601088.SH", "--timeframe", "1h"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0
    assert "status: VALID" in result.stdout


def test_update_data_cli():
    result = subprocess.run([sys.executable, "cli.py", "update-data", "--symbol", "601088.SH"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0


def test_data_status_cli():
    subprocess.run([sys.executable, "cli.py", "fetch-data", "--symbol", "601088.SH", "--timeframe", "1h"], cwd=ROOT, check=True, capture_output=True, text=True)
    result = subprocess.run([sys.executable, "cli.py", "data-status", "--symbol", "601088.SH", "--timeframe", "1h"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0


def test_research_auto_triggers_download_for_missing_path():
    missing = "data_lake/stocks/1h/nonexistent.parquet"
    result = subprocess.run([sys.executable, "cli.py", "research", "--direction", "中国神华1小时布林低吸波段，控制回撤", "--symbol", "601088.SH", "--timeframe", "1h", "--data", missing], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "Research Agent V2 完成" in result.stdout


def test_research_plan_writes_data_source():
    latest = (ROOT / "reports/latest.txt").read_text(encoding="utf-8").strip()
    text = (ROOT / "reports" / latest / "research_plan.md").read_text(encoding="utf-8")
    assert "数据来源" in text


def test_final_report_writes_data_source():
    latest = (ROOT / "reports/latest.txt").read_text(encoding="utf-8").strip()
    text = (ROOT / "reports" / latest / "final_research_report.md").read_text(encoding="utf-8")
    assert "数据来源" in text


def test_data_quality_acquisition_linked():
    record = DataAcquisitionAgent().fetch(DataRequest("601088.SH", "1h"))
    assert "data_quality_score" in record


def test_provider_router_fallback_to_akshare_or_local():
    source, rows = ProviderRouter().fetch(DataRequest("601088.SH", "10m"))
    assert source in {"local", "akshare"}
    assert rows


def test_csv_backed_parquet_cache_normal():
    record = DataAcquisitionAgent().fetch(DataRequest("601088.SH", "10m"))
    assert record["path"].endswith(".parquet")
    assert Path(record["path"]).read_text(encoding="utf-8").splitlines()[0]


def test_benchmark_runner_single_outputs_files():
    result = BenchmarkRunner().run_one("test_benchmark_tmp", "中国神华 周线 跌多了买 涨回去卖 控制回撤", "data/sample/601088.csv")
    path = ROOT / "benchmarks/test_benchmark_tmp"
    assert result["total_score"] > 0
    assert (path / "benchmark_score.json").exists()


def test_benchmark_review_files_exist():
    path = ROOT / "benchmarks/test_benchmark_tmp"
    assert (path / "benchmark_review.md").exists()
    assert (path / "strategy_dsl.yaml").exists()


def test_benchmark_score_json_has_total_score():
    path = ROOT / "benchmarks/test_benchmark_tmp/benchmark_score.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "total_score" in data


def test_benchmark_gap_report_written():
    BenchmarkRunner().run_all("data/sample/601088.csv")
    assert (ROOT / "benchmarks/benchmark_gap_report.md").exists()


def test_benchmark_validation_report_written():
    assert (ROOT / "BENCHMARK_VALIDATION_REPORT.md").exists()


def test_v65_report_written():
    assert (ROOT / "V6_5_BENCHMARK_REPORT.md").exists()


def test_v66_report_exists():
    assert (ROOT / "V6_6_DATA_ACQUISITION_REPORT.md").exists()


def test_data_acquisition_report_exists_after_fetch():
    DataAcquisitionAgent().fetch(DataRequest("601088.SH", "1h"))
    assert (ROOT / "DATA_ACQUISITION_REPORT.md").exists()


def test_cache_manager_asset_paths():
    assert "stocks" in str(CacheManager().path(DataRequest("601088.SH", "1h")))
    assert "etf" in str(CacheManager().path(DataRequest("510880.SH", "1h")))


def test_data_request_object_fields():
    req = DataRequest("601088.SH", "1h", "raw", "2020-01-01", "2024-01-01", "akshare")
    assert req.preferred_source == "akshare"


def test_preferred_source_prioritized():
    names = [p.name for p in provider_chain("akshare")]
    assert names[0] == "akshare"

