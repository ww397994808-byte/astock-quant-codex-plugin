# Research Agent V2 Design

Research Agent V2 的目标不是“帮用户调一个最优参数”，而是像初级量化研究员一样，从自然语言方向生成可审计的研究路径。

## 1. 如何识别策略范式

入口是：

```bash
python3 cli.py research --direction "中国神华周线布林低吸波段策略，偏稳健，控制回撤" --symbol 601088.SH --data data/sample/601088.csv
```

`PatternClassifier` 使用显式规则识别范式：

- “布林低吸 / 回撤买入 / 波段 / 反弹卖出” -> `swing`
- “均线 / MACD / 趋势 / 择时” -> `timing`
- “网格 / 分层买卖 / 区间震荡” -> `grid`
- “选股 / 高股息 / 低波动 / 因子 / TopN” -> `stock_selection`
- “轮动 / 切换 / 强弱 / ETF轮动 / 行业轮动” -> `rotation`
- “组合 / 再平衡 / 等权 / 权重” -> `portfolio`
- “配对 / 套利 / A/H价差” -> `pair_trading` BLOCKER
- “财报 / 分红 / 公告 / 事件” -> `event_driven` BLOCKER

第一版坚持规则可解释，不把范式判断交给不可审计 Prompt。

## 2. 如何选择 backtest_template

`StrategyVariant` 明确包含：

- `pattern`
- `template_name`
- `strategy_name`
- `params`
- `components`

模板映射：

- `swing` -> `swing_template`
- `timing` -> `timing_template`
- `grid` -> `grid_template`
- `stock_selection` -> `stock_selection_template`
- `rotation` -> `rotation_template`
- `portfolio` -> `portfolio_rebalance_template`

所有模板最终仍进入 `ExecutionEngine`，不能绕过 A股交易规则、费用、持仓、T+1 和审计。

## 3. 如何生成策略变体

流程：

1. `HypothesisGenerator` 根据范式生成研究假设。
2. `SearchSpaceBuilder` 根据方向生成参数空间。
3. `StrategyVariantGenerator` 组合参数，生成多个 `StrategyVariant`。
4. `ExperimentRunner` 对每个 Variant 执行 full / in-sample / out-sample 回测。
5. 所有实验写入 `experiment_results.csv`。

示例：稳健布林波段会优先搜索更稳的窗口、标准差和止损：

```json
{
  "window": [20, 30],
  "num_std": [1.8, 2.0, 2.2],
  "stop_loss": [0.05, 0.08]
}
```

## 4. 如何防止只追求最高收益

`ResultRanker` 不按总收益排序。默认综合评分：

```text
score =
0.35 * calmar_score
0.25 * out_sample_score
0.20 * drawdown_score
0.10 * stability_score
0.10 * trade_count_score
```

审计 `INVALID` 的结果不会进入推荐候选。

`OverfitDetector` 检查：

- 样本内好、样本外差；
- 参数在搜索边界；
- 交易次数过少；
- 收益由少数交易贡献；
- Walk Forward 不稳定；
- 审计 INVALID；
- 未来函数 HIGH 风险。

## 5. 如何写成 0 基础用户能看懂的报告

每次研究输出：

```text
reports/research_run_id/
├── research_plan.md
├── hypothesis.md
├── strategy_variants.csv
├── search_space.json
├── experiment_results.csv
├── ranked_results.csv
├── overfit_report.md
├── stability_report.md
├── next_round_suggestions.md
└── final_research_report.md
```

最终报告避免堆术语，直接回答：

- 系统识别成了哪类策略；
- 为什么这么研究；
- 哪个候选更稳；
- 是否有过拟合风险；
- 下一轮应该怎么缩小参数；
- 是否能进入后续模拟盘或实盘前检查。

