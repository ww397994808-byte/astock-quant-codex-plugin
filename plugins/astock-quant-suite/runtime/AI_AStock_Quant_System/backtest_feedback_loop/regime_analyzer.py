from __future__ import annotations

import csv
from pathlib import Path


class RegimeAnalyzer:
    def analyze(self, equity_curve_path: str | Path) -> dict:
        rows = self._read(equity_curve_path)
        if len(rows) < 3:
            return {"trend_regime": "unknown", "market_regime": "unknown", "volatility_regime": "unknown", "regime_performance": {}}
        equity = [float(r["equity"]) for r in rows]
        ret = equity[-1] / equity[0] - 1 if equity[0] else 0
        returns = [curr / prev - 1 for prev, curr in zip(equity, equity[1:]) if prev]
        vol = (sum((r - sum(returns) / len(returns)) ** 2 for r in returns) / len(returns)) ** 0.5 if returns else 0
        trend = "单边上涨" if ret > 0.1 else "单边下跌" if ret < -0.1 else "横盘"
        market = "牛市" if ret > 0.05 else "熊市" if ret < -0.05 else "震荡"
        volatility = "高波动" if vol > 0.02 else "低波动"
        return {"trend_regime": trend, "market_regime": market, "volatility_regime": volatility, "regime_performance": {market: ret, volatility: vol}}

    def generate_slices(self, rows: list[dict], output_dir: str | Path, window: int = 10) -> list[dict]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        slices: list[dict] = []
        if len(rows) < 3:
            self._write_slices(output_dir / "regime_slices.csv", slices)
            return slices
        chunks = [rows[i : i + window] for i in range(0, len(rows), window) if len(rows[i : i + window]) >= 3]
        vol_values = [self._volatility(chunk) for chunk in chunks]
        sorted_vol = sorted(vol_values)
        high_threshold = sorted_vol[int(len(sorted_vol) * 0.7)] if sorted_vol else 0
        low_threshold = sorted_vol[int(len(sorted_vol) * 0.3)] if sorted_vol else 0
        for chunk, vol in zip(chunks, vol_values):
            start = chunk[0]["datetime"]
            end = chunk[-1]["datetime"]
            trend_return = float(chunk[-1]["close"]) / float(chunk[0]["close"]) - 1 if float(chunk[0]["close"]) else 0.0
            if trend_return > 0.03:
                regime = "bull"
                reason = "区间收益超过正阈值"
            elif trend_return < -0.03:
                regime = "bear"
                reason = "区间收益低于负阈值"
            else:
                regime = "sideways"
                reason = "区间收益绝对值较小"
            slices.append(self._slice_row(regime, start, end, reason, vol, trend_return, len(chunk)))
            if vol >= high_threshold:
                slices.append(self._slice_row("high_volatility", start, end, "滚动波动率高于分位数阈值", vol, trend_return, len(chunk)))
            if vol <= low_threshold:
                slices.append(self._slice_row("low_volatility", start, end, "滚动波动率低于分位数阈值", vol, trend_return, len(chunk)))
        self._write_slices(output_dir / "regime_slices.csv", slices)
        return slices

    def _read(self, path: str | Path) -> list[dict]:
        path = Path(path)
        if path.is_dir():
            path = path / "equity_curve.csv"
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def _volatility(self, rows: list[dict]) -> float:
        closes = [float(row["close"]) for row in rows]
        returns = [curr / prev - 1 for prev, curr in zip(closes, closes[1:]) if prev]
        if not returns:
            return 0.0
        mean = sum(returns) / len(returns)
        return (sum((ret - mean) ** 2 for ret in returns) / len(returns)) ** 0.5

    def _slice_row(self, regime: str, start, end, reason: str, volatility: float, trend_return: float, bar_count: int) -> dict:
        return {
            "regime": regime,
            "start_datetime": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end_datetime": end.strftime("%Y-%m-%d %H:%M:%S"),
            "reason": reason,
            "volatility": round(volatility, 8),
            "trend_return": round(trend_return, 8),
            "bar_count": bar_count,
        }

    def _write_slices(self, path: Path, slices: list[dict]) -> None:
        headers = ["regime", "start_datetime", "end_datetime", "reason", "volatility", "trend_return", "bar_count"]
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(slices)
