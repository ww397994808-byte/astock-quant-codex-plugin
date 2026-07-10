from __future__ import annotations


PAPER_POLICY_ADVICE = {
    "observed_days": "补更长历史数据或延长模拟观察期；不要用短样本盈利推进 QMT。",
    "trade_count": "优先调整触发条件、参数或策略范式，让同类市场环境里产生足够成交样本。",
    "completed_rounds": "补足从入场到退出的完整买卖闭环；不要把单边买入或单边卖出当作有效验证。",
    "max_drawdown": "先降低单次仓位、收紧止损或加入暂停交易规则；不要用加仓掩盖回撤。",
    "rejected_order_rate": "先修正价格、数量、T+1、涨跌停、现金和仓位约束；被拒委托不能算有效交易证据。",
}


def advice_for_failed_metrics(metrics: list[str]) -> list[dict[str, str]]:
    advice = []
    seen = set()
    for metric in metrics:
        key = str(metric or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        advice.append({
            "metric": key,
            "advice": PAPER_POLICY_ADVICE.get(key, "回到 paper_observation_report.md 和 STUDENT_DIAGNOSTICS.md，按失败项补证据。"),
        })
    return advice
