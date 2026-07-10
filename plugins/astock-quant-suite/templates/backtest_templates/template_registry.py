from __future__ import annotations

from backtest_templates.grid_template import GridTemplate
from backtest_templates.rotation_template import RotationTemplate
from backtest_templates.stock_selection_template import StockSelectionTemplate
from backtest_templates.swing_template import SwingTemplate
from backtest_templates.timing_template import TimingTemplate


STRATEGY_TEMPLATE_MAP = {
    "ma_cross": TimingTemplate,
    "boll_mean_reversion": SwingTemplate,
    "dividend_drawdown": SwingTemplate,
    "grid": GridTemplate,
    "rotation": RotationTemplate,
    "stock_selection": StockSelectionTemplate,
    "timing": TimingTemplate,
    "swing": SwingTemplate,
}


def create_backtest_template(strategy, strategy_name: str, symbol: str, initial_cash: float, template_name: str | None = None, template_params: dict | None = None):
    key = template_name or strategy_name
    template_cls = STRATEGY_TEMPLATE_MAP.get(key, STRATEGY_TEMPLATE_MAP.get(strategy_name, TimingTemplate))
    if template_cls is GridTemplate:
        params = template_params or {}
        allowed = {"grid_step", "levels", "layer_percent", "base_price", "grid_base", "ma_window", "max_position_percent"}
        grid_params = {key: value for key, value in params.items() if key in allowed}
        return template_cls(strategy=strategy, symbol=symbol, initial_cash=initial_cash, **grid_params)
    return template_cls(strategy=strategy, symbol=symbol, initial_cash=initial_cash)
