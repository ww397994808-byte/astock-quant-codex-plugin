# V7.2.1 Weekly Regime Reality Check Report

## 当前完成内容

V7.2.1 完成两个真实性补强：

1. Weekly Resampling Layer；
2. Regime Slice Experiments。

## Weekly Resampling Layer

`1w` 已成为真实可用 timeframe：

- market_data/timeframe.py 支持 1w；
- market_data/resampler.py 支持 1d -> 1w；
- AkShareProvider / Data Acquisition 支持自动生成 1w 缓存；
- CLI backtest 支持不传 data 自动获取数据；
- Intake / Research 能识别 周线 / 1w / weekly；
- CrossTimeframeRunner 已包含 1w。

周线 bar 使用周内最后一个交易日作为 datetime，因此 signal_datetime / execute_datetime 不再是抽象周标签。

## Regime Slice Experiments

Regime split 已从标签实验升级为真实区间切片：

- RegimeAnalyzer 输出 regime_slices.csv；
- RegimeSliceRunner 按 start_datetime/end_datetime 切子样本；
- 每个 slice 独立回测；
- 每个 slice 独立 Audit；
- 每个 slice 独立 Readiness；
- 输出 regime_slice_results.csv；
- 输出 best_by_regime_slice.csv；
- 输出 weak_regime_report.md。

bear 区间表现弱会进入 weak_regime_report，并通过 CandidateSelector 的 batch_summary 降权。

## 验收命令

已通过：

```bash
python3 cli.py generate-sample-data --timeframe 1d --symbol 601088.SH
```

已通过：

```bash
python3 cli.py backtest --strategy boll_mean_reversion --symbol 601088.SH --timeframe 1w --adjust point_in_time_qfq
```

已通过：

```bash
python3 cli.py optimize-loop --idea "中国神华周线布林低吸波段，控制回撤，不要太频繁交易" --symbol 601088.SH --timeframe 1w --adjust point_in_time_qfq --max-iterations 8
```

最新周线 optimize-loop 输出：

```text
reports/optimize_loop_20260622_000006
```

## 测试

新增 V7.2.1 测试：20 个。

覆盖：

- 1d -> 1w 聚合；
- 周线 OHLCV；
- 周线不跨自然周；
- 周线 signal_datetime / execute_datetime；
- CLI weekly backtest；
- cross_timeframe 真实包含 1w；
- Research/Intake 周线识别；
- bull/bear/sideways/high_volatility/low_volatility slice；
- regime_slices.csv 字段；
- RegimeSliceRunner 真实切数据并独立回测；
- weak_regime_report；
- CandidateSelector regime slice 降权。

## 当前限制

- 周线仍基于本地日线数据聚合，不单独接周频事件/财务数据；
- Regime 切片第一版使用简单固定窗口和阈值；
- 后续可接指数行情、行业指数和更严格的波动率状态识别。
