from __future__ import annotations


class FailureClassifier:
    def classify(self, analyses: list[dict]) -> list[str]:
        issues = set()
        for analysis in analyses:
            if "analysis" in analysis and isinstance(analysis["analysis"], dict):
                issues.update(analysis["analysis"].get("issues", []))
            issues.update(analysis.get("issues", []))
        failures = []
        if "too_few_trades" in issues:
            failures.append("交易次数太少")
            failures.append("过滤条件过强")
        if "too_many_trades" in issues:
            failures.append("交易次数太多")
        if "drawdown_too_large" in issues:
            failures.append("出场逻辑错误")
        if "low_return" in issues:
            failures.append("入场逻辑错误")
            failures.append("参数空间太窄")
        if "out_sample_degradation" in issues:
            failures.append("样本外退化")
            failures.append("策略结构过于复杂")
        if "concentrated_profit" in issues:
            failures.append("收益集中在少数交易")
        if not failures:
            failures.append("策略方向本身无效")
        return list(dict.fromkeys(failures))
