from pathlib import Path

from core.order import Order
from core.stage_gate import ResearchStage, StageGateEvaluator
from qmt.readonly import QMTReadonlyChecker


class FakeBroker:
    def __init__(self, connected: bool = True, dry_run: bool = True) -> None:
        self.connected = connected
        self.dry_run = dry_run

    def connect(self) -> bool:
        return self.connected

    def get_account(self) -> dict:
        return {"connected": self.connected, "dry_run": self.dry_run, "account_id": "test"}

    def get_positions(self) -> list[dict]:
        return [{"symbol": "601088.SH", "quantity": 100}]

    def get_cash(self) -> float:
        return 100000.0

    def get_orders(self) -> list[dict]:
        return []

    def get_trades(self) -> list[dict]:
        return []

    def place_order(self, order: Order) -> dict:
        return {"status": "DRY_RUN"}

    def cancel_order(self, order_id: str) -> bool:
        return False

    def sync_positions(self) -> None:
        return None


def valid_plan() -> dict:
    return {
        "status": "VALID",
        "blockers": [],
        "promotion_policy": {"qmt_allowed": True},
    }


def test_qmt_readonly_checker_passes_when_all_read_paths_work(tmp_path: Path):
    checker = QMTReadonlyChecker(FakeBroker())
    snapshot = checker.collect()
    assert snapshot.ok is True
    checker.write_report(tmp_path, snapshot)
    assert (tmp_path / "qmt_readonly_report.md").exists()
    assert (tmp_path / "qmt_account_snapshot.json").exists()


def test_qmt_readonly_checker_fails_when_not_connected():
    snapshot = QMTReadonlyChecker(FakeBroker(connected=False)).collect()
    assert snapshot.ok is False
    assert any("QMT 未连接" in item for item in snapshot.failures)


def test_qmt_readonly_checker_requires_dry_run_safe_default():
    snapshot = QMTReadonlyChecker(FakeBroker(dry_run=False)).collect()
    assert snapshot.ok is False
    assert any("dry_run" in item for item in snapshot.failures)


def test_stage_gate_stops_at_backtest_valid_without_paper_observation():
    result = StageGateEvaluator().evaluate(
        backtest_plan=valid_plan(),
        audit_status="VALID",
        readiness="PAPER_READY",
        paper_observed=False,
    )
    assert result.stage == ResearchStage.PAPER_READY
    assert "模拟盘" in result.reasons[0]


def test_stage_gate_reaches_qmt_readonly_ready_after_paper_and_qmt_readonly():
    result = StageGateEvaluator().evaluate(
        backtest_plan=valid_plan(),
        audit_status="VALID",
        readiness="PAPER_READY",
        paper_observed=True,
        qmt_readonly_ok=True,
        pretrade_ok=False,
    )
    assert result.stage == ResearchStage.QMT_READONLY_READY


def test_stage_gate_blocks_non_qmt_strategy():
    plan = {"status": "VALID", "blockers": [], "promotion_policy": {"qmt_allowed": False}}
    result = StageGateEvaluator().evaluate(backtest_plan=plan, audit_status="VALID")
    assert result.stage == ResearchStage.RESEARCH_ONLY
