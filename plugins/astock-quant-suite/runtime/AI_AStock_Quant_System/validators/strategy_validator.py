from __future__ import annotations


class StrategyValidator:
    def validate(self, params: dict) -> list[str]:
        issues = []
        if params is None:
            issues.append("策略参数为空")
            return issues
        for key, value in params.items():
            if value is None or value == "":
                issues.append(f"{key} 参数为空")
            if isinstance(value, (int, float)) and value < 0:
                issues.append(f"{key} 参数越界：不能为负")
        if "short_window" in params and "long_window" in params and params["short_window"] >= params["long_window"]:
            issues.append("short_window 必须小于 long_window")
        return issues

