from __future__ import annotations

from dataclasses import asdict, dataclass, field
from itertools import product
from typing import Any


@dataclass
class StrategyVariant:
    variant_id: str
    pattern: str
    template_name: str
    components: dict[str, str]
    params: dict[str, Any]
    description: str
    expected_behavior: str
    strategy_name: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["params"] = dict(self.params)
        return data


class StrategyVariantGenerator:
    TEMPLATE_BY_PATTERN = {
        "swing": "swing_template",
        "timing": "timing_template",
        "grid": "grid_template",
        "stock_selection": "stock_selection_template",
        "rotation": "rotation_template",
        "portfolio": "portfolio_rebalance_template",
    }

    STRATEGY_BY_PATTERN = {
        "swing": "boll_mean_reversion",
        "timing": "ma_cross",
        "grid": "ma_cross",
        "stock_selection": "ma_cross",
        "rotation": "ma_cross",
        "portfolio": "ma_cross",
    }

    def generate(self, pattern: str, search_space: dict[str, list[Any]], max_variants: int = 12) -> list[StrategyVariant]:
        if pattern in {"pair_trading", "event_driven"}:
            return []
        keys = list(search_space)
        variants: list[StrategyVariant] = []
        for idx, values in enumerate(product(*[search_space[k] for k in keys]), start=1):
            if idx > max_variants:
                break
            params = dict(zip(keys, values))
            variants.append(StrategyVariant(
                variant_id=f"{pattern}_{idx:03d}",
                pattern=pattern,
                template_name=self.TEMPLATE_BY_PATTERN.get(pattern, "timing_template"),
                components={"entry": self._entry(pattern), "exit": self._exit(pattern), "sizing": "target_percent"},
                params=params,
                description=f"{pattern} variant {idx}: {params}",
                expected_behavior=self._expected(pattern),
                strategy_name=self.STRATEGY_BY_PATTERN.get(pattern, "ma_cross"),
            ))
        return variants

    def _entry(self, pattern: str) -> str:
        return {
            "swing": "低吸/回撤/布林下轨",
            "timing": "趋势或均线信号",
            "grid": "价格下穿网格层级",
            "stock_selection": "因子排名 top_n",
            "rotation": "强弱评分 top_k",
            "portfolio": "权重漂移超过阈值",
        }.get(pattern, "signal")

    def _exit(self, pattern: str) -> str:
        return {
            "swing": "反弹、止损或回到中轨",
            "timing": "反向趋势信号",
            "grid": "价格上穿网格层级",
            "stock_selection": "调仓日剔除",
            "rotation": "评分差触发切换",
            "portfolio": "再平衡到目标权重",
        }.get(pattern, "exit")

    def _expected(self, pattern: str) -> str:
        return "偏稳健，优先控制回撤和样本外退化" if pattern == "swing" else "追求规则稳定和审计可通过"

