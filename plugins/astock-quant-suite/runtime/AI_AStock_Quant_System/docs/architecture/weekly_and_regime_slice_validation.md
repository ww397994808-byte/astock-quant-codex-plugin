# Weekly And Regime Slice Validation

## Weekly Resampling Layer

V7.2.1 已将 `1w` 从占位周期升级为真实可用 timeframe。

周线由日线聚合生成，规则为：

- open = 周内第一个交易日 open
- high = 周内最高 high
- low = 周内最低 low
- close = 周内最后一个交易日 close
- volume = 周内求和
- amount = 周内求和
- symbol / board / is_st / adjust_type 保留

周线按自然周分桶，不跨自然周。若周内交易日不足 5 天，Resampler 会记录 warning，但不直接报错，因为 A股存在节假日和临时休市。

周线 bar 的 `datetime` 使用该周最后一个交易日，因此 signal_datetime / execute_datetime 均落在真实交易日上。T+1 仍由原 ExecutionEngine / Position 系统按 A股交易日逻辑执行。

## CLI 支持

以下命令现在可直接运行：

```bash
python3 cli.py backtest --strategy boll_mean_reversion --symbol 601088.SH --timeframe 1w --adjust point_in_time_qfq
```

如果未提供 `--data`，BacktestService 会通过 Data Acquisition Agent 自动获取或生成缓存数据。

## Research / Intake 识别

Intake Agent 和 Research Agent 已能识别：

- 周线
- 1w
- weekly

## Regime Slice Experiments

V7.2.1 已将 regime split 从标签化实验升级为真实区间切片。

RegimeAnalyzer 会输出：

```text
regime_slices.csv
```

字段：

- regime
- start_datetime
- end_datetime
- reason
- volatility
- trend_return
- bar_count

支持 regime：

- bull
- bear
- sideways
- high_volatility
- low_volatility

## Regime 定义

第一版采用简单、可审计的代码化规则：

- bull：区间收益大于正阈值；
- bear：区间收益小于负阈值；
- sideways：区间收益绝对值较小；
- high_volatility：滚动波动率高于分位数阈值；
- low_volatility：滚动波动率低于分位数阈值。

## RegimeSliceRunner

RegimeSliceRunner 会：

1. 根据 regime_slices.csv 生成子样本；
2. 每个子样本独立回测；
3. 每个子样本独立 Audit；
4. 每个子样本独立 Readiness；
5. 输出 regime_slice_results.csv；
6. 输出 best_by_regime_slice.csv；
7. 输出 weak_regime_report.md。

如果策略在 bear 区间表现较弱，weak_regime_report.md 会明确说明，并通过 batch_summary 进入 CandidateSelector 降权逻辑。

## 当前限制

周线由日线聚合生成，尚未单独处理复杂周频财务/事件数据。Regime 切片第一版采用固定窗口和简单阈值，后续可升级为更严格的市场状态识别模型。
