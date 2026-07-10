# 中国神华 A/H 比例研究路径

## 第一轮已经完成

输出文件：

- `reports/ah_shenhua_research/research_report.md`
- `reports/ah_shenhua_research/aligned_ah_ratio.csv`
- `reports/ah_shenhua_research/forward_return_by_ratio_bucket.csv`
- `reports/ah_shenhua_research/strategy_grid_summary.csv`

## 当前结论

低 A/H 比例区间对 A 股后续 20-60 日收益有正向提示，高 A/H 比例区间表现偏弱。

当前最佳网格来自“只做多 A”：`entry_z=-0.5, exit_z=0.0`。它的收益最高，但最大回撤仍然很大，因此不能直接作为可交易策略。

## 2018 年以来低回撤硬目标检验

用户明确目标是确定性和低回撤：年化收益大于 20%，最大回撤低于 5%。

第一轮低回撤粗搜输出：

- `reports/ah_shenhua_low_dd/optimizer_report.md`
- `reports/ah_shenhua_low_dd/optimizer_summary.csv`
- `reports/ah_shenhua_low_dd/best_trade_log.csv`

结论：

- 当前参数空间没有找到同时满足 `年化 > 20%` 与 `最大回撤 < 5%` 的组合。
- 回撤控制在 5% 以内时，最高年化约 4.36%。
- 年化最高的组合约 8.34%，但最大回撤约 -13.47%。
- 因此，单靠原始 A/H 比例日线信号，暂时无法支撑该硬目标。

## 下一步

1. 补 HKD/CNY 汇率，把原始比例改成真实 A/H 溢价。
2. 补前复权或总回报价格，避免神华分红导致长期价格序列失真。
3. 做样本切分：2007-2014、2015-2020、2021-2026 分别检验。
4. 加风险过滤：趋势过滤、最大持仓天数、止损或波动率仓位。
5. 如果仍然有效，再接入正式回测与审计层。
6. 若坚持 20%/5% 硬目标，下一轮必须引入额外有效因子：股息率、煤价、煤炭指数、沪深 300/恒指趋势、汇率、分红税和融资融券约束。
