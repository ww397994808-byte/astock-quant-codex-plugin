from __future__ import annotations

from strategies.boll_mean_reversion import BollMeanReversionStrategy
from strategies.dividend_drawdown import DividendDrawdownStrategy
from strategies.grid import GridStrategy
from strategies.ma_cross import MACrossStrategy


STRATEGIES = {
    MACrossStrategy.name: MACrossStrategy,
    BollMeanReversionStrategy.name: BollMeanReversionStrategy,
    DividendDrawdownStrategy.name: DividendDrawdownStrategy,
    GridStrategy.name: GridStrategy,
}


def create_strategy(name: str, **params):
    if name not in STRATEGIES:
        raise ValueError(f"未知策略：{name}。可选策略：{', '.join(sorted(STRATEGIES))}")
    return STRATEGIES[name](**params)
