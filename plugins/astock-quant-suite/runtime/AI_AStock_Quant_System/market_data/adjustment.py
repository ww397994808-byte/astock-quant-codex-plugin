from __future__ import annotations

from datetime import datetime

from market_data.corporate_actions import CorporateAction


ADJUST_TYPES = {"raw", "point_in_time_qfq", "qfq", "hfq"}


class AdjustmentEngine:
    def calculate_factor(self, bar_time: datetime, actions: list[CorporateAction], point_in_time: bool = True) -> float:
        factor = 1.0
        for action in actions:
            if point_in_time and action.known_date > bar_time:
                continue
            if action.ex_date <= bar_time:
                share_bonus = 1 + action.bonus_share_ratio + action.transfer_share_ratio + action.split_ratio
                if share_bonus > 0:
                    factor /= share_bonus
                if action.cash_dividend:
                    factor *= max(0.01, 1 - action.cash_dividend / 100.0)
        return round(factor, 8)

    def adjust_bars_point_in_time_qfq(self, rows: list[dict], actions: list[CorporateAction]) -> list[dict]:
        adjusted = []
        for row in rows:
            bar_time = row.get("datetime") or row.get("date")
            if isinstance(bar_time, str):
                bar_time = datetime.strptime(bar_time[:19], "%Y-%m-%d %H:%M:%S") if " " in bar_time else datetime.strptime(bar_time[:10], "%Y-%m-%d")
            factor = self.calculate_factor(bar_time, actions, point_in_time=True)
            item = dict(row)
            for col in ["open", "high", "low", "close"]:
                item[col] = round(float(item[col]) * factor, 6)
            item["adjust_type"] = "point_in_time_qfq"
            item["adjust_factor"] = factor
            item["corporate_action_flag"] = any(a.ex_date.date() == bar_time.date() and a.known_date <= bar_time for a in actions)
            adjusted.append(item)
        return adjusted

    def adjust(self, rows: list[dict], actions: list[CorporateAction], adjust_type: str = "raw") -> list[dict]:
        if adjust_type not in ADJUST_TYPES:
            raise ValueError(f"不支持复权类型：{adjust_type}")
        if adjust_type == "raw":
            return [dict(r, adjust_type="raw", adjust_factor=r.get("adjust_factor", 1.0), corporate_action_flag=False) for r in rows]
        if adjust_type == "point_in_time_qfq":
            return self.adjust_bars_point_in_time_qfq(rows, actions)
        # qfq/hfq can be read for research, but must be marked as future leak risk.
        out = []
        for row in rows:
            item = dict(row)
            item["adjust_type"] = adjust_type
            item["adjust_factor"] = self.calculate_factor(datetime.max, actions, point_in_time=False)
            item["FUTURE_LEAK_RISK"] = True
            out.append(item)
        return out

