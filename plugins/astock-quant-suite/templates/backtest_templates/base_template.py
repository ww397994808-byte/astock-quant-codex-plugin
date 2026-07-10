from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from audit.audit_report import write_audit_report
from audit.adjustment_leak_checker import AdjustmentLeakChecker
from audit.future_leak_checker import FutureLeakChecker
from audit.trade_rule_checker import TradeRuleChecker
from backtest.execution import ExecutionEngine
from backtest.performance import calculate_performance
from backtest.report import write_csv, write_json, write_research_readme
from backtest.result import BacktestResult
from core.order import Signal
from core.portfolio import Portfolio
from core.readiness import classify_readiness, write_readiness_report
from core.research_logger import ResearchLogger
from core.run_manager import RunContext
from data_quality.data_quality_checker import DataQualityChecker
from metrics.metrics_report import build_metrics, write_metrics_report
from stress_tests.stress_runner import StressRunner


@dataclass
class OrderIntent:
    symbol: str
    signal_time: Any
    action: str
    reason: str
    target_position: int | None = None
    target_percent: float | None = None
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_signal(self) -> Signal:
        return Signal(
            symbol=self.symbol,
            signal_time=self.signal_time,
            action=self.action,
            confidence=self.confidence,
            reason=self.reason,
            target_position=self.target_position,
            target_percent=self.target_percent,
            metadata=self.metadata,
            timeframe=self.metadata.get("timeframe", "1d"),
        )


@dataclass
class RebalancePlan:
    plan_time: Any
    target_weights: dict[str, float]
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_order_intents(self, default_symbol: str | None = None, current_weights: dict[str, float] | None = None) -> list[OrderIntent]:
        intents: list[OrderIntent] = []
        current_weights = current_weights or {}
        symbols = set(current_weights) | set(self.target_weights)
        for symbol in sorted(symbols):
            target_weight = self.target_weights.get(symbol, 0.0)
            current_weight = current_weights.get(symbol, 0.0)
            if abs(target_weight - current_weight) < 1e-9:
                continue
            action = "BUY" if target_weight > current_weight else "SELL"
            intents.append(OrderIntent(symbol or default_symbol or "", self.plan_time, action, self.reason, target_percent=target_weight, metadata={**self.metadata, "current_weight": current_weight, "target_weight": target_weight}))
        return intents


class BaseBacktestTemplate:
    template_name = "base"

    def __init__(self, strategy: Any, symbol: str, initial_cash: float = 1000000) -> None:
        self.strategy = strategy
        self.symbol = symbol
        self.initial_cash = float(initial_cash)
        self.execution = ExecutionEngine()

    def create_intents(self, index: int, history_data: list[dict], portfolio: Portfolio) -> list[OrderIntent]:
        raise NotImplementedError

    def run(self, run_context: RunContext, rows: list[dict], source_paths: list[Path] | None = None) -> BacktestResult:
        if len(rows) < 3:
            raise ValueError("回测至少需要 3 根 K 线。")
        data_quality = DataQualityChecker().check(rows, run_context.output_dir)
        portfolio = Portfolio(self.initial_cash)
        logger = ResearchLogger(run_context.output_dir / "research_log.md")
        logger.log(f"# Research Log\n\nrun_id: {run_context.run_id}\ntemplate: {self.template_name}\nstrategy: {self.strategy.describe()}\nsymbol: {self.symbol}")
        orders: list[dict] = []
        trades: list[dict] = []
        positions: list[dict] = []
        equity_curve: list[dict] = []
        pending_intents: list[OrderIntent] = []

        for i, row in enumerate(rows):
            if pending_intents and i > 0:
                for intent in pending_intents:
                    order = self.execution.signal_to_order(intent.to_signal(), portfolio, row)
                    if order is None:
                        continue
                    prev_close = float(rows[i - 1]["close"])
                    order, trade = self.execution.execute(order, portfolio, row, prev_close)
                    orders.append({
                        "symbol": order.symbol,
                        "action": order.action,
                        "quantity": order.quantity,
                        "signal_time": order.signal_time.strftime("%Y-%m-%d"),
                        "execute_time": order.execute_time.strftime("%Y-%m-%d"),
                        "signal_datetime": order.signal_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "execute_datetime": order.execute_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "timeframe": order.timeframe,
                        "price": order.price,
                        "status": order.status,
                        "reason": order.reason,
                    })
                    if trade:
                        trades.append({
                            "symbol": trade.symbol,
                            "action": trade.action,
                            "quantity": trade.quantity,
                            "price": trade.price,
                            "amount": trade.amount,
                            "signal_time": trade.signal_time.strftime("%Y-%m-%d"),
                            "execute_time": trade.execute_time.strftime("%Y-%m-%d"),
                            "signal_datetime": trade.signal_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "execute_datetime": trade.execute_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "timeframe": trade.timeframe,
                            "commission": trade.commission,
                            "stamp_tax": trade.stamp_tax,
                            "transfer_fee": trade.transfer_fee,
                            "total_fee": trade.total_fee,
                            "reason": trade.reason,
                        })
                pending_intents = []

            close_price = float(row["close"])
            equity_curve.append({
                "date": row["date"].strftime("%Y-%m-%d"),
                "datetime": row["datetime"].strftime("%Y-%m-%d %H:%M:%S"),
                "timeframe": row.get("timeframe", "1d"),
                "cash": round(portfolio.cash, 6),
                "market_value": round(portfolio.market_value(self.symbol, close_price), 6),
                "equity": round(portfolio.equity(self.symbol, close_price), 6),
            })
            snap = portfolio.positions.snapshot(self.symbol)
            positions.append({
                "date": row["date"].strftime("%Y-%m-%d"),
                "datetime": row["datetime"].strftime("%Y-%m-%d %H:%M:%S"),
                "timeframe": row.get("timeframe", "1d"),
                "symbol": self.symbol,
                "total_position": snap["total_position"],
                "available_position": snap["available_position"],
                "cash": round(portfolio.cash, 6),
            })
            portfolio.positions.release_after_close(row["date"])
            if i < len(rows) - 1:
                pending_intents = self.create_intents(i, rows[: i + 1], portfolio)

        performance = calculate_performance(equity_curve, trades, self.initial_cash)
        metrics = build_metrics(equity_curve, trades)
        write_metrics_report(run_context.output_dir / "metrics_report.md", metrics)
        write_csv(run_context.output_dir / "orders.csv", orders, ["symbol", "action", "quantity", "signal_time", "execute_time", "signal_datetime", "execute_datetime", "timeframe", "price", "status", "reason"])
        write_csv(run_context.output_dir / "trades.csv", trades, ["symbol", "action", "quantity", "price", "amount", "signal_time", "execute_time", "signal_datetime", "execute_datetime", "timeframe", "commission", "stamp_tax", "transfer_fee", "total_fee", "reason"])
        write_csv(run_context.output_dir / "positions.csv", positions, ["date", "datetime", "timeframe", "symbol", "total_position", "available_position", "cash"])
        write_csv(run_context.output_dir / "equity_curve.csv", equity_curve, ["date", "datetime", "timeframe", "cash", "market_value", "equity"])
        write_json(run_context.output_dir / "performance.json", performance)

        future_report = FutureLeakChecker().check(output_dir=run_context.output_dir, source_paths=source_paths or [])
        trade_report = TradeRuleChecker().check(run_context.output_dir, rows)
        adjustment_report = AdjustmentLeakChecker().check(rows=rows, source_paths=source_paths or [])
        status = "INVALID" if future_report["status"] == "INVALID" or trade_report["status"] == "INVALID" or adjustment_report["status"] == "INVALID" else "VALID"
        readiness = classify_readiness(
            audit_status=status,
            future_leak_high=any(f.get("severity") == "HIGH" for f in future_report.get("findings", [])),
            trade_rule_violation=trade_report["status"] == "INVALID",
            trade_count=int(performance.get("trade_count", 0)),
            backtest_days=len(rows),
            out_sample_ok=True,
            stability_ok=True,
            risk_ok=abs(float(performance.get("max_drawdown", 0))) < 0.3,
            adjust_type=rows[0].get("adjust_type", "raw") if rows else "raw",
        )
        readiness_reasons = [
            f"审计状态：{status}",
            f"数据质量状态：{data_quality['status']}",
            f"交易次数：{performance.get('trade_count', 0)}",
            f"最大回撤：{performance.get('max_drawdown', 0)}",
        ]
        write_readiness_report(run_context.output_dir / "readiness_report.md", readiness, readiness_reasons)
        StressRunner().run(rows, run_context.output_dir)
        write_audit_report(run_context.output_dir / "audit_report.md", status, future_report, trade_report, performance)
        write_research_readme(run_context.output_dir / "README_本次研究.md", {
            "strategy": getattr(self.strategy, "name", self.strategy.__class__.__name__),
            "symbol": self.symbol,
            "start_date": rows[0]["date"].strftime("%Y-%m-%d"),
            "end_date": rows[-1]["date"].strftime("%Y-%m-%d"),
            "status": status,
            **performance,
        })
        logger.log(f"\nstatus: {status}\nfinal_equity: {performance.get('final_equity')}")
        logger.save()
        return BacktestResult(run_context.run_id, run_context.output_dir, status, performance, status)
