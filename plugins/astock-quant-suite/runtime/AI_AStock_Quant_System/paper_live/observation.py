from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PaperObservationPolicy:
    strategy_pattern: str
    timeframe: str
    min_observed_days: int
    min_trades: int
    min_completed_rounds: int
    max_drawdown_limit: float
    max_rejected_order_rate: float
    rationale: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PaperObservationResult:
    status: str
    observed_days: int
    trade_count: int
    completed_rounds: int
    rejected_orders: int
    rejected_order_rate: float
    max_drawdown: float
    policy: dict
    policy_card: dict = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "VALID"

    def to_dict(self) -> dict:
        return asdict(self)


class PaperObservationChecker:
    """Evaluate whether a paper run is strong enough to approach QMT readonly."""

    def policy_for(self, strategy_pattern: str = "timing", timeframe: str = "1d") -> PaperObservationPolicy:
        pattern = (strategy_pattern or "timing").strip()
        tf = (timeframe or "1d").strip()
        if pattern in {"grid"}:
            return PaperObservationPolicy(pattern, tf, 30 if tf in {"1d", "1w"} else 20, 8, 3, 0.25, 0.15, "网格策略必须观察多次分层成交和资金占用。")
        if pattern in {"rotation", "portfolio_rebalance"}:
            return PaperObservationPolicy(pattern, tf, 60 if tf == "1d" else 24, 4, 2, 0.25, 0.10, "轮动/再平衡策略必须观察换仓周期和多标的同步。")
        if pattern in {"stock_selection"}:
            return PaperObservationPolicy(pattern, tf, 90 if tf == "1d" else 36, 5, 3, 0.25, 0.10, "选股策略需要更长观察期，并默认不作为第一阶段 QMT 放行依据。")
        if pattern in {"timing", "swing"} and tf in {"5m", "10m", "30m", "1h"}:
            return PaperObservationPolicy(pattern, tf, 20, 6, 3, 0.20, 0.10, "日内策略必须观察足够多的信号、午休和涨跌停约束。")
        if pattern in {"timing", "swing"} and tf == "1w":
            return PaperObservationPolicy(pattern, tf, 20, 1, 1, 0.30, 0.10, "周线策略成交稀疏，先要求跨多周观察再推进。")
        return PaperObservationPolicy(pattern, tf, 20, 3, 1, 0.30, 0.10, "日线择时/波段策略至少需要多笔成交验证。")

    def check(
        self,
        run_dir: str | Path,
        *,
        strategy_pattern: str = "timing",
        timeframe: str = "1d",
        min_observed_days: int | None = None,
        min_trades: int | None = None,
        max_drawdown_limit: float | None = None,
    ) -> PaperObservationResult:
        root = Path(run_dir)
        policy = self.policy_for(strategy_pattern=strategy_pattern, timeframe=timeframe)
        min_observed_days = int(min_observed_days if min_observed_days is not None else policy.min_observed_days)
        min_trades = int(min_trades if min_trades is not None else policy.min_trades)
        max_drawdown_limit = float(max_drawdown_limit if max_drawdown_limit is not None else policy.max_drawdown_limit)
        equity_rows = self._read_csv(root / "equity_curve.csv")
        trade_rows = self._read_csv(root / "trades.csv")
        order_rows = self._read_csv(root / "orders.csv")
        performance = self._read_json(root / "performance.json")

        observed_days = len({row.get("date") or row.get("datetime") for row in equity_rows if row})
        trade_count = len(trade_rows)
        completed_rounds = self._completed_rounds(trade_rows)
        rejected_orders = sum(1 for row in order_rows if row.get("status") == "REJECTED")
        rejected_order_rate = rejected_orders / len(order_rows) if order_rows else 0.0
        max_drawdown = float(performance.get("max_drawdown") or self._max_drawdown_from_equity(equity_rows))

        failures: list[str] = []
        warnings: list[str] = []
        if observed_days < min_observed_days:
            failures.append(f"模拟观察期不足：{observed_days} < {min_observed_days}")
        if trade_count < min_trades:
            failures.append(f"模拟成交次数不足：{trade_count} < {min_trades}")
        if completed_rounds < policy.min_completed_rounds:
            failures.append(f"完整买卖回合不足：{completed_rounds} < {policy.min_completed_rounds}")
        if abs(max_drawdown) > max_drawdown_limit:
            failures.append(f"模拟最大回撤超过限制：{max_drawdown:.4f} > {max_drawdown_limit:.4f}")
        if rejected_order_rate > policy.max_rejected_order_rate:
            failures.append(f"模拟委托拒单率过高：{rejected_order_rate:.4f} > {policy.max_rejected_order_rate:.4f}")
        if rejected_orders:
            warnings.append(f"存在 {rejected_orders} 笔被交易规则拒绝的模拟委托，需要复核成交假设。")
        policy_dict = PaperObservationPolicy(
            strategy_pattern=policy.strategy_pattern,
            timeframe=policy.timeframe,
            min_observed_days=min_observed_days,
            min_trades=min_trades,
            min_completed_rounds=policy.min_completed_rounds,
            max_drawdown_limit=max_drawdown_limit,
            max_rejected_order_rate=policy.max_rejected_order_rate,
            rationale=policy.rationale,
        ).to_dict()
        policy_card = self._policy_card(
            policy=policy_dict,
            observed_days=observed_days,
            trade_count=trade_count,
            completed_rounds=completed_rounds,
            max_drawdown=max_drawdown,
            rejected_order_rate=rejected_order_rate,
            status="INVALID" if failures else "VALID",
        )

        return PaperObservationResult(
            status="INVALID" if failures else "VALID",
            observed_days=observed_days,
            trade_count=trade_count,
            completed_rounds=completed_rounds,
            rejected_orders=rejected_orders,
            rejected_order_rate=round(rejected_order_rate, 6),
            max_drawdown=max_drawdown,
            policy=policy_dict,
            policy_card=policy_card,
            failures=failures,
            warnings=warnings,
        )

    def write_report(self, run_dir: str | Path, result: PaperObservationResult) -> None:
        root = Path(run_dir)
        (root / "paper_observation.json").write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (root / "paper_observation_policy_card.json").write_text(
            json.dumps(result.policy_card, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        lines = [
            "# Paper Observation Report",
            "",
            f"status: {result.status}",
            "",
            "## Summary",
            f"- observed_days: {result.observed_days}",
            f"- trade_count: {result.trade_count}",
            f"- completed_rounds: {result.completed_rounds}",
            f"- rejected_orders: {result.rejected_orders}",
            f"- rejected_order_rate: {result.rejected_order_rate}",
            f"- max_drawdown: {result.max_drawdown}",
            "",
            "## Policy",
            f"- strategy_pattern: {result.policy.get('strategy_pattern')}",
            f"- timeframe: {result.policy.get('timeframe')}",
            f"- min_observed_days: {result.policy.get('min_observed_days')}",
            f"- min_trades: {result.policy.get('min_trades')}",
            f"- min_completed_rounds: {result.policy.get('min_completed_rounds')}",
            f"- max_drawdown_limit: {result.policy.get('max_drawdown_limit')}",
            f"- max_rejected_order_rate: {result.policy.get('max_rejected_order_rate')}",
            f"- rationale: {result.policy.get('rationale')}",
            "",
            "## Policy Card",
            "- file: paper_observation_policy_card.json",
            f"- learner_message: {result.policy_card.get('learner_message')}",
            "",
            "## Failures",
        ]
        lines.extend([f"- {item}" for item in result.failures] or ["- 未发现模拟观察阻断项。"])
        lines.append("")
        lines.append("## Warnings")
        lines.extend([f"- {item}" for item in result.warnings] or ["- 未发现模拟观察警告。"])
        lines.extend([
            "",
            "说明：模拟观察通过只表示可以进入 QMT 只读检查，不等于可以真实下单。",
        ])
        (root / "paper_observation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _read_csv(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def _read_json(self, path: Path) -> dict:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _completed_rounds(self, rows: list[dict]) -> int:
        open_qty: dict[str, float] = {}
        rounds = 0
        for row in rows:
            symbol = str(row.get("symbol") or "__single__")
            action = str(row.get("action") or row.get("side") or "").upper()
            quantity = self._quantity(row)
            if action == "BUY":
                open_qty[symbol] = open_qty.get(symbol, 0.0) + quantity
            elif action == "SELL" and open_qty.get(symbol, 0.0) > 0:
                rounds += 1
                open_qty[symbol] = max(0.0, open_qty.get(symbol, 0.0) - quantity)
        return rounds

    def _quantity(self, row: dict) -> float:
        for key in ("quantity", "qty", "volume", "shares"):
            value = row.get(key)
            if value not in {"", None}:
                try:
                    parsed = float(value)
                    return parsed if parsed > 0 else 1.0
                except (TypeError, ValueError):
                    return 1.0
        return 1.0

    def _policy_card(
        self,
        *,
        policy: dict,
        observed_days: int,
        trade_count: int,
        completed_rounds: int,
        max_drawdown: float,
        rejected_order_rate: float,
        status: str,
    ) -> dict:
        requirements = [
            self._requirement("observed_days", observed_days, policy.get("min_observed_days"), observed_days >= int(policy.get("min_observed_days") or 0)),
            self._requirement("trade_count", trade_count, policy.get("min_trades"), trade_count >= int(policy.get("min_trades") or 0)),
            self._requirement("completed_rounds", completed_rounds, policy.get("min_completed_rounds"), completed_rounds >= int(policy.get("min_completed_rounds") or 0)),
            self._requirement("max_drawdown", abs(max_drawdown), policy.get("max_drawdown_limit"), abs(max_drawdown) <= float(policy.get("max_drawdown_limit") or 0.0), comparator="<="),
            self._requirement("rejected_order_rate", round(rejected_order_rate, 6), policy.get("max_rejected_order_rate"), rejected_order_rate <= float(policy.get("max_rejected_order_rate") or 0.0), comparator="<="),
        ]
        return {
            "status": status,
            "strategy_pattern": policy.get("strategy_pattern"),
            "timeframe": policy.get("timeframe"),
            "requirements": requirements,
            "can_continue_qmt_readonly": status == "VALID",
            "learner_message": "模拟观察已满足当前策略类型的最低证据，可以进入 QMT 只读检查；仍不能真实下单。" if status == "VALID" else "模拟观察证据还不够，先补齐失败项，不要进入 QMT 或实盘。",
        }

    def _requirement(self, metric: str, actual, required, passed: bool, comparator: str = ">=") -> dict:
        return {
            "metric": metric,
            "actual": actual,
            "required": required,
            "comparator": comparator,
            "status": "PASS" if passed else "FAIL",
        }

    def _max_drawdown_from_equity(self, rows: list[dict]) -> float:
        peak = None
        max_dd = 0.0
        for row in rows:
            try:
                equity = float(row.get("equity") or 0)
            except (TypeError, ValueError):
                continue
            peak = equity if peak is None else max(peak, equity)
            if peak and peak > 0:
                max_dd = min(max_dd, (equity - peak) / peak)
        return max_dd
