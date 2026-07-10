from __future__ import annotations


class HypothesisGenerator:
    def generate(self, direction: str, pattern: str) -> str:
        if pattern == "swing":
            return "在稳健偏好下，低吸/回撤类波段策略应优先降低最大回撤，并在样本外保持不过度退化。"
        if pattern == "timing":
            return "趋势或择时策略应减少震荡区间误交易，并在趋势阶段获得稳定收益。"
        if pattern == "grid":
            return "网格策略适合区间震荡，核心是层级间距、单层仓位和回撤控制。"
        if pattern == "stock_selection":
            return "选股策略的关键是因子排序稳定性、调仓频率和组合分散度。"
        if pattern == "rotation":
            return "轮动策略的关键是评分差足够大再切换，减少频繁换手。"
        if pattern == "portfolio":
            return "组合再平衡策略应在目标权重、漂移阈值和现金缓冲之间取得稳定折中。"
        return f"{direction} 当前存在不可自动研究的 blocker。"

