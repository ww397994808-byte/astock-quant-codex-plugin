from __future__ import annotations


class QMTValidator:
    def validate(self, config: dict) -> list[str]:
        issues = []
        if config.get("enable_real_trade", False):
            issues.append("真实交易开关已开启，需要人工复核")
        if "dry_run" not in config or config.get("dry_run") is not True:
            issues.append("dry_run 未保持默认 true")
        for key in ["max_single_position_pct", "max_total_position_pct", "max_daily_loss_pct"]:
            if key not in config:
                issues.append(f"缺少风险参数：{key}")
        return issues

