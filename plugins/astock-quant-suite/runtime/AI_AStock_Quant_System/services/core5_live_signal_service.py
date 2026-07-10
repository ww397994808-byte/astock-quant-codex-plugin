from __future__ import annotations

import csv
import hashlib
import json
import pickle
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from core.result import TaskResult
from core.run_manager import RunManager


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))

from core5_relative_strength_grid.grid import buy_sell_multipliers, normalize_weights  # noqa: E402
from core5_relative_strength_grid.market import load_market, ma_at, month_last_dates  # noqa: E402
from core5_relative_strength_grid.metrics import daily_equity  # noqa: E402
from core5_relative_strength_grid.params import make_param_pool  # noqa: E402
from core5_relative_strength_grid.walk_forward import score_param  # noqa: E402


class Core5LiveSignalService:
    """Generate live signal and order drafts for the current best Core5+601225 strategy.

    This service intentionally does not call QMT or place orders. It produces auditable
    CSV/JSON/Markdown files that can later be reviewed or handed to a broker adapter.
    """

    SYMBOLS = ["601088.SH", "600900.SH", "601288.SH", "601398.SH", "601939.SH", "601225.SH"]
    DATA_DIR = Path("/Users/shejishi/Desktop/30分钟股票数据")
    INITIAL_CASH = 1_000_000.0
    PARAM_LOOKBACK_MONTHS = 12
    SYMBOL_LOOKBACK_MONTHS = 2
    SWITCH_GAP = 0.02
    MIN_HOLD_MONTHS = 3
    PORTFOLIO_DD_GUARD = 0.08
    SLIP_BPS = 5

    def run(
        self,
        data_dir: str | None = None,
        as_of: str | None = None,
        current_symbol: str | None = None,
        current_shares: int | None = None,
        cash: float | None = None,
        equity: float | None = None,
        current_drawdown: float | None = None,
        start_date: str = "2017-01-01",
        end_date: str = "2026-06-26",
        allow_historical: bool = False,
    ) -> TaskResult:
        data_path = Path(data_dir).expanduser() if data_dir else self.DATA_DIR
        markets = self._load_markets(data_path, start_date, end_date)
        params = make_param_pool(n_random=0)
        param_equities = self._build_param_equities(markets, params, data_path, start_date, end_date)
        common_dates = sorted(set.intersection(*(set(eq) for values in param_equities.values() for eq in values)))
        month_dates = month_last_dates(common_dates)
        decision_idx = self._decision_index(month_dates, as_of)
        decisions = self._walk_decisions(param_equities, month_dates, decision_idx)
        signal = decisions[-1]
        selected = signal["selected"]
        selected_param = params[int(signal["param_rank"]) - 1]
        selected_market = markets[selected]
        selected_row_index = self._last_row_index_on_or_before(selected_market, signal["rebalance_date"])
        live_guarded = bool(signal["guarded"])
        if current_drawdown is not None:
            live_guarded = float(current_drawdown) <= -self.PORTFOLIO_DD_GUARD
        signal["live_guarded"] = live_guarded
        signal["execute_date"] = self._first_trading_date_after(selected_market, signal["rebalance_date"])
        grid_levels = self._grid_levels(selected_market, selected_row_index, selected_param, guarded=live_guarded)

        current_symbol = (current_symbol or "").strip()
        current_shares_int = int(current_shares or 0)
        cash_float = float(cash or 0.0)
        equity_float = float(equity or 0.0)

        warnings = []
        blockers = []
        if signal["rebalance_date"] != month_dates[-1] and not allow_historical:
            blockers.append(
                f"信号不是最新可用月末：signal={signal['rebalance_date']} latest={month_dates[-1]}"
            )
        if signal["rebalance_date"] != month_dates[-1] and allow_historical:
            warnings.append(
                f"历史模拟演练模式：signal={signal['rebalance_date']} latest={month_dates[-1]}，只能用于模拟盘流程测试，不能用于真实交易。"
            )
        if not signal.get("execute_date"):
            blockers.append("本地行情里找不到调仓日之后的下一交易日，不能生成可执行换仓订单。")
        if as_of and as_of > month_dates[decision_idx]:
            warnings.append(f"as_of={as_of} 晚于当前可用月末数据 {month_dates[decision_idx]}；信号只能基于本地已有行情。")
        if not current_symbol:
            warnings.append("未提供 current_symbol/current_shares，订单草稿只能给出目标方向，不能完成持仓差额计算。")
        if current_drawdown is None:
            blockers.append("缺少 current_drawdown；实盘必须使用账户真实回撤决定是否暂停新增网格买入。")
        if current_drawdown is not None:
            live_guarded = float(current_drawdown) <= -self.PORTFOLIO_DD_GUARD
            if live_guarded != bool(signal["guarded"]):
                warnings.append(
                    "实盘传入 current_drawdown 与回测曲线 guard 状态不同；实盘应以账户实际回撤为准。"
                )
        if not current_symbol:
            blockers.append("缺少 current_symbol；不能做换仓差额和订单审核。")
        if equity_float <= 0 and cash_float <= 0:
            blockers.append("缺少 equity/cash；不能计算实盘可买数量。")

        order_drafts = []
        if not blockers:
            order_drafts = self._order_drafts(
                signal=signal,
                selected=selected,
                current_symbol=current_symbol,
                current_shares=current_shares_int,
                cash=cash_float,
                equity=equity_float,
                selected_market=selected_market,
                selected_param=selected_param,
            )
        self._annotate_execution_gate(grid_levels, execution_allowed=not blockers, blockers=blockers)

        ctx = RunManager().create_run("core5_live_signal")
        status = "SIGNAL_READY" if not blockers else "SIGNAL_BLOCKED_DRAFT_ONLY"
        payload = {
            "status": status,
            "mode": "SANDBOX_DEMO_ONLY" if allow_historical else "LIVE_DRAFT",
            "hard_boundary": "只生成信号和订单草稿；不连接 QMT，不发送委托。历史模拟演练模式不能用于真实交易。"
            if allow_historical
            else "只生成信号和订单草稿；不连接 QMT，不发送委托。",
            "data_dir": str(data_path),
            "available_data_end": month_dates[decision_idx],
            "strategy": {
                "name": "core5_plus_601225_relative_strength_grid",
                "symbols": self.SYMBOLS,
                "param_lookback_months": self.PARAM_LOOKBACK_MONTHS,
                "symbol_lookback_months": self.SYMBOL_LOOKBACK_MONTHS,
                "switch_gap": self.SWITCH_GAP,
                "min_hold_months": self.MIN_HOLD_MONTHS,
                "portfolio_dd_guard": self.PORTFOLIO_DD_GUARD,
                "slip_bps": self.SLIP_BPS,
                "dividend_income_counted": False,
                "t_plus_1_sell": True,
                "same_interval_order": "BUY_THEN_SELL",
            },
            "signal": signal,
            "grid_levels": grid_levels,
            "order_drafts": order_drafts,
            "inputs": {
                "as_of": as_of,
                "current_symbol": current_symbol,
                "current_shares": current_shares_int,
                "cash": cash_float,
                "equity": equity_float,
                "current_drawdown": current_drawdown,
                "allow_historical": allow_historical,
            },
            "warnings": warnings,
            "blockers": blockers,
        }
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if not blockers else "INVALID"
        return TaskResult(
            status=result_status,
            message="Core5+601225 实盘信号已生成：只输出信号、网格价位和订单草稿，不发送委托。",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status="LIVE_SIGNAL_DRAFT_ONLY" if not blockers else "LIVE_SIGNAL_BLOCKED",
            warnings=warnings + blockers,
            artifacts=payload,
        )

    def _annotate_execution_gate(
        self,
        grid_levels: list[dict[str, Any]],
        *,
        execution_allowed: bool,
        blockers: list[str],
    ) -> None:
        reason = " | ".join(blockers)
        for row in grid_levels:
            row["strategy_enabled"] = row.get("enabled", True)
            row["execution_allowed"] = execution_allowed
            row["execution_block_reason"] = "" if execution_allowed else reason

    def _symbol_path(self, data_dir: Path, symbol: str) -> Path:
        code = symbol.split(".")[0]
        prefix = "SZSE" if symbol.endswith(".SZ") else "SSE"
        return data_dir / f"{prefix}_DLY_{code}, 30.csv"

    def _load_markets(self, data_dir: Path, start_date: str, end_date: str):
        markets = {}
        missing = []
        for symbol in self.SYMBOLS:
            path = self._symbol_path(data_dir, symbol)
            if not path.exists():
                missing.append(f"{symbol}: {path}")
                continue
            market = load_market(symbol, str(path), start_date, end_date)
            setattr(market, "source_path", path)
            markets[symbol] = market
        if missing:
            raise FileNotFoundError("缺少 30 分钟真实行情文件：" + "; ".join(missing))
        return markets

    def _build_param_equities(
        self,
        markets: dict[str, Any],
        params: list[dict],
        data_dir: Path,
        start_date: str,
        end_date: str,
    ) -> dict[str, list[dict[str, float]]]:
        from core5_relative_strength_grid.grid import simulate_symbol_grid

        cache_dir = ROOT / "reports" / "core5_live_signal_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_key = self._cache_key(markets, data_dir, start_date, end_date, len(params))
        cache_path = cache_dir / f"param_equities_{cache_key}.pkl"
        source_mtime = max(
            Path(getattr(markets[symbol], "source_path", "")).stat().st_mtime
            if getattr(markets[symbol], "source_path", None) and Path(getattr(markets[symbol], "source_path")).exists()
            else 0
            for symbol in self.SYMBOLS
        )
        if cache_path.exists() and cache_path.stat().st_mtime >= source_mtime:
            with cache_path.open("rb") as f:
                cached = pickle.load(f)
            if (
                cached.get("symbols") == self.SYMBOLS
                and cached.get("param_count") == len(params)
                and cached.get("start_date") == start_date
                and cached.get("end_date") == end_date
                and cached.get("data_dir") == str(data_dir)
            ):
                return cached["param_equities"]

        out = {symbol: [] for symbol in self.SYMBOLS}
        for symbol in self.SYMBOLS:
            for param in params:
                result = simulate_symbol_grid(markets[symbol], param, dividend_factor=0.0, keep=True)
                out[symbol].append(daily_equity(result))
        with cache_path.open("wb") as f:
            pickle.dump(
                {
                    "symbols": self.SYMBOLS,
                    "param_count": len(params),
                    "start_date": start_date,
                    "end_date": end_date,
                    "data_dir": str(data_dir),
                    "param_equities": out,
                },
                f,
            )
        return out

    def _cache_key(
        self,
        markets: dict[str, Any],
        data_dir: Path,
        start_date: str,
        end_date: str,
        param_count: int,
    ) -> str:
        items = [str(data_dir), start_date, end_date, str(param_count)]
        for symbol in self.SYMBOLS:
            path = Path(getattr(markets[symbol], "source_path"))
            stat = path.stat()
            items.append(f"{symbol}:{path}:{stat.st_size}:{stat.st_mtime_ns}")
        return hashlib.sha256("|".join(items).encode("utf-8")).hexdigest()[:16]

    def _decision_index(self, month_dates: list[str], as_of: str | None) -> int:
        target = as_of or month_dates[-1]
        candidates = [
            i
            for i, date in enumerate(month_dates)
            if date <= target and i >= self.PARAM_LOOKBACK_MONTHS and i >= self.SYMBOL_LOOKBACK_MONTHS
        ]
        if not candidates:
            raise ValueError(f"没有足够历史数据生成 as_of={target} 的信号。")
        idx = candidates[-1]
        return idx

    def _walk_decisions(self, param_equities: dict[str, list[dict[str, float]]], month_dates: list[str], decision_idx: int) -> list[dict]:
        first_idx = next(
            i
            for i, date in enumerate(month_dates)
            if date[:4] >= "2021"
            and i >= self.PARAM_LOOKBACK_MONTHS
            and i >= self.SYMBOL_LOOKBACK_MONTHS
        )
        current_equity = self.INITIAL_CASH
        peak = current_equity
        current_symbol: str | None = None
        held_months = 0
        decisions = []
        for idx in range(first_idx, decision_idx + 1):
            train_dates = month_dates[idx - self.PARAM_LOOKBACK_MONTHS : idx + 1]
            symbol_start = month_dates[idx - self.SYMBOL_LOOKBACK_MONTHS]
            rebalance_date = month_dates[idx]
            next_date = month_dates[idx + 1] if idx + 1 < len(month_dates) else ""

            selected_param = {}
            scores = {}
            for symbol in self.SYMBOLS:
                best_idx = max(
                    range(len(param_equities[symbol])),
                    key=lambda k: score_param(param_equities[symbol][k], train_dates, "recent3"),
                )
                selected_param[symbol] = best_idx
                scores[symbol] = param_equities[symbol][best_idx][rebalance_date] / param_equities[symbol][best_idx][symbol_start] - 1

            ranked = sorted(self.SYMBOLS, key=lambda s: scores[s], reverse=True)
            top = ranked[0]
            if current_symbol is None:
                selected = top
                switched = True
                reason = "initial"
                held_months = 1
            else:
                lead = scores[top] - scores[current_symbol]
                if top != current_symbol and lead >= self.SWITCH_GAP and held_months >= self.MIN_HOLD_MONTHS:
                    selected = top
                    switched = True
                    reason = "top"
                    held_months = 1
                elif top != current_symbol and held_months < self.MIN_HOLD_MONTHS:
                    selected = current_symbol
                    switched = False
                    reason = "min_hold"
                    held_months += 1
                else:
                    selected = current_symbol
                    switched = False
                    reason = "gap_keep" if top != current_symbol else "top"
                    held_months += 1
            current_symbol = selected
            guarded = current_equity / peak - 1 <= -self.PORTFOLIO_DD_GUARD

            next_return = None
            if next_date:
                eq = param_equities[selected][selected_param[selected]]
                if rebalance_date in eq and next_date in eq:
                    next_return = eq[next_date] / eq[rebalance_date] - 1
                    if switched:
                        next_return -= self.SLIP_BPS / 10000
                    current_equity *= 1 + next_return
                    peak = max(peak, current_equity)

            row = {
                "rebalance_date": rebalance_date,
                "next_date": next_date,
                "selected": selected,
                "top": top,
                "reason": reason,
                "switched": switched,
                "guarded": guarded,
                "held_months": held_months,
                "param_rank": selected_param[selected] + 1,
                "next_return_est": next_return,
                "equity_est": current_equity,
            }
            row.update({f"score_{symbol}": scores[symbol] for symbol in self.SYMBOLS})
            decisions.append(row)
        return decisions

    def _last_row_index_on_or_before(self, market: Any, date: str) -> int:
        candidates = [i for i, row in enumerate(market.rows) if row["date"] <= date]
        if not candidates:
            raise ValueError(f"{market.symbol} 在 {date} 前没有行情。")
        return candidates[-1]

    def _first_trading_date_after(self, market: Any, date: str) -> str:
        for trading_date in market.dates:
            if trading_date > date:
                return trading_date
        return ""

    def _grid_levels(self, market: Any, row_index: int, param: dict, guarded: bool) -> list[dict[str, Any]]:
        row = market.rows[row_index]
        ma = ma_at(market, row_index, param["ma_period"])
        if ma is None:
            return []
        buy_mult, sell_qty_mult, sell_widen = buy_sell_multipliers(market, row_index, param)
        if guarded:
            buy_mult = 0.0
        atr_factor = market.atr_factors[row["date"]] * param["atr_mult"]
        buy_weights = normalize_weights(param["buy_weights"])
        levels = []
        for level_no, discount in enumerate(param["buy_discounts"], start=1):
            levels.append(
                {
                    "symbol": market.symbol,
                    "side": "BUY",
                    "level": level_no,
                    "trigger_price": round(min(ma * (1 - discount * atr_factor), row["close"]), 3),
                    "enabled": buy_mult > 0,
                    "weight": buy_weights[level_no - 1],
                    "ma_period": param["ma_period"],
                    "atr_factor": atr_factor,
                    "asof_bar": row["dt"].isoformat(sep=" "),
                }
            )
        for level_no, premium in enumerate(param["sell_premiums"], start=1):
            levels.append(
                {
                    "symbol": market.symbol,
                    "side": "SELL",
                    "level": level_no,
                    "trigger_price": round(max(ma * (1 + premium * atr_factor * sell_widen), row["close"]), 3),
                    "enabled": True,
                    "qty_multiplier": sell_qty_mult,
                    "ma_period": param["ma_period"],
                    "atr_factor": atr_factor,
                    "asof_bar": row["dt"].isoformat(sep=" "),
                }
            )
        return levels

    def _order_drafts(
        self,
        *,
        signal: dict,
        selected: str,
        current_symbol: str,
        current_shares: int,
        cash: float,
        equity: float,
        selected_market: Any,
        selected_param: dict,
    ) -> list[dict[str, Any]]:
        drafts = []
        signal_time = f"{signal['rebalance_date']}T15:00:00"
        execute_time = f"{signal.get('execute_date')}T09:30:00" if signal.get("execute_date") else ""
        if current_symbol and current_symbol != selected and current_shares > 0:
            drafts.append(
                {
                    "symbol": current_symbol,
                    "action": "SELL",
                    "quantity": int(current_shares // 100 * 100),
                    "price": "",
                    "signal_time": signal_time,
                    "execute_time": execute_time,
                    "reason": f"switch_to_{selected}",
                    "timeframe": "30m",
                    "draft_only": True,
                }
            )
        if current_symbol != selected:
            ref_price = selected_market.daily[signal["rebalance_date"]]["close"]
            base_money = equity if equity > 0 else cash
            target_money = base_money * float(selected_param["initial_position_fraction"])
            qty = int(target_money / ref_price // 100 * 100) if ref_price > 0 and target_money > 0 else 0
            if qty > 0:
                drafts.append(
                    {
                        "symbol": selected,
                        "action": "BUY",
                        "quantity": qty,
                        "price": "",
                        "signal_time": signal_time,
                        "execute_time": execute_time,
                        "reason": "open_target_position" if not current_symbol else f"switch_from_{current_symbol}",
                        "timeframe": "30m",
                        "draft_only": True,
                    }
                )
        return drafts

    def _write_csv(self, path: Path, rows: list[dict[str, Any]]) -> None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def _write_outputs(self, out: Path, payload: dict[str, Any]) -> None:
        (out / "LIVE_SIGNAL.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(out / "grid_levels.csv", payload["grid_levels"])
        self._write_csv(out / "order_drafts.csv", payload["order_drafts"])
        signal = payload["signal"]
        lines = [
            "# Core5 + 601225 Live Signal",
            "",
            f"status: {payload['status']}",
            f"available_data_end: {payload['available_data_end']}",
            f"hard_boundary: {payload['hard_boundary']}",
            "",
            "## Signal",
            f"- rebalance_date: {signal['rebalance_date']}",
            f"- next_date: {signal['next_date']}",
            f"- execute_date: {signal.get('execute_date')}",
            f"- selected: {signal['selected']}",
            f"- top: {signal['top']}",
            f"- reason: {signal['reason']}",
            f"- switched: {signal['switched']}",
            f"- guarded: {signal['guarded']}",
            f"- live_guarded: {signal.get('live_guarded')}",
            f"- param_rank: {signal['param_rank']}",
            "",
            "## Scores",
        ]
        for symbol in self.SYMBOLS:
            lines.append(f"- {symbol}: {signal[f'score_{symbol}']:.4%}")
        lines.extend(["", "## Grid Files", "- grid_levels.csv", "- order_drafts.csv", "", "## Warnings"])
        lines.extend([f"- {item}" for item in payload["warnings"]] or ["- 无"])
        lines.extend(["", "## Blockers"])
        lines.extend([f"- {item}" for item in payload.get("blockers", [])] or ["- 无"])
        lines.extend([
            "",
            "## Safety",
            "- 本命令不调用 QMT，不发送委托。",
            "- 订单草稿必须人工复核持仓、现金、涨跌停、最小交易单位和账户实际回撤。",
        ])
        (out / "LIVE_SIGNAL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
