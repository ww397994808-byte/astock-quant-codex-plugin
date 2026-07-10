from __future__ import annotations


class SearchSpaceBuilder:
    def build(self, pattern: str, direction: str) -> dict[str, list]:
        conservative = any(word in direction for word in ["稳健", "控制回撤", "低回撤"])
        if pattern == "swing":
            return {
                "window": [20, 30] if conservative else [10, 20, 30],
                "num_std": [1.8, 2.0, 2.2],
                "stop_loss": [0.05, 0.08] if conservative else [0.06, 0.10],
            }
        if pattern == "timing":
            return {"short_window": [5, 10], "long_window": [20, 30]}
        if pattern == "grid":
            if "MA5" in direction.upper() or "均线" in direction:
                intraday = any(word in direction for word in ["10分钟", "10min", "30分钟", "1小时", "1h"])
                return {
                    "grid_base": ["ma"],
                    "ma_window": [5],
                    "grid_step": [0.001, 0.002, 0.003, 0.004, 0.005] if intraday else [0.005, 0.01, 0.015, 0.02, 0.03],
                    "levels": [3, 5],
                    "layer_percent": [0.1, 0.2],
                    "max_position_percent": [0.5, 0.7, 1.0],
                }
            return {"grid_step": [0.02, 0.03], "levels": [2, 3], "layer_percent": [0.08, 0.12]}
        if pattern == "stock_selection":
            return {"top_n": [3, 5], "rebalance_frequency": [20, 40]}
        if pattern == "rotation":
            return {"top_k": [1, 2], "switch_threshold": [0.0, 0.05], "rebalance_frequency": [10, 20]}
        if pattern == "portfolio":
            return {"drift_threshold": [0.03, 0.05], "rebalance_frequency": [20, 40], "cash_buffer": [0.02, 0.05]}
        return {}
