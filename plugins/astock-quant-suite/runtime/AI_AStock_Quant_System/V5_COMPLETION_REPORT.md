# V5 Completion Report

V5 增加 Intraday Data Layer 和 Point-in-Time Adjustment Engine，把系统从日线研究推进到 1h / 10m 日内研究基础设施。

## 已完成

- `market_data/` 日内 bar schema、timeframe、A股交易时段、resampler、parquet store、provider、adjustment engine。
- 支持 `1d / 1h / 30m / 10m / 5m`。
- 1h 一天 4 根，10m 一天 24 根，30m 一天 8 根。
- 禁止跨午休聚合。
- `point_in_time_qfq` 只使用 `known_date <= 当前bar时间` 的 corporate action。
- 普通 `qfq/hfq` 标记 `FUTURE_LEAK_RISK` 并由审计拦截。
- orders.csv 增加 `signal_datetime / execute_datetime / timeframe`。
- CLI 支持 `--timeframe` 和 `--adjust`。

## 仍需后续增强

- 真 parquet 依赖可在 V6 替换当前轻量 CSV-backed store。
- QMTDataProvider 需要真实 MiniQMT 环境联调。
- point-in-time 因子模型第一版较保守，后续需接真实分红送转/配股数据。

