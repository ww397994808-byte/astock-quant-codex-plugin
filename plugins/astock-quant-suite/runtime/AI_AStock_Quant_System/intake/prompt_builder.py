from __future__ import annotations

from pathlib import Path

from intake.strategy_requirement import StrategyRequirement


class PromptBuilder:
    def build(self, req: StrategyRequirement) -> str:
        symbol_text = ", ".join(req.symbols) if req.symbols else "待补充"
        return f"""# Codex Research Prompt

请基于以下结构化策略需求启动 Research Agent，而不是直接手写一次性回测脚本。

- 原始想法：{req.original_idea}
- 市场：{req.market}
- 标的：{symbol_text}
- 周期：{req.timeframe or '待补充'}
- 策略范式：{req.strategy_pattern or '待补充'}
- 入场：{req.entry_logic or '待补充'}
- 出场：{req.exit_logic or '待补充'}
- 仓位：{req.sizing_logic or '待补充'}
- 风险：{req.risk_control}
- 目标：{req.objective}
- 复权：{req.data_adjustment}
- 约束：{req.constraints}

要求：
1. 使用 Task Layer / Research Agent。
2. 使用对应 backtest_template。
3. 审计 INVALID 不进入推荐。
4. 不按总收益排序，优先看 Calmar、样本外、回撤、稳定性、交易次数。
5. 如果有 QMT 实盘意图，只能输出安全提醒，不能真实下单。
"""

    def write(self, path: str | Path, req: StrategyRequirement) -> str:
        text = self.build(req)
        Path(path).write_text(text, encoding="utf-8")
        return text

