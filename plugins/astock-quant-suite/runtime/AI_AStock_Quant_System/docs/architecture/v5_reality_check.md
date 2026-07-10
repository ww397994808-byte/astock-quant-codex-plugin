# V5 Reality Check

## 1. CSV-backed `.parquet` 是否误导

V5 当前使用 CSV-backed `.parquet`：文件名保留 `.parquet`，内容是 CSV。原因是避免 0 基础用户卡在 pyarrow 安装上。文档已明确说明，这是教学阶段存储实现，不是假装已经使用真实 parquet。

`ParquetStore` 的 API 已保持未来兼容：

- `save_bars`
- `load_bars`
- `list_symbols`
- `has_symbol`

后续真实 parquet 只需替换内部实现。

## 2. point_in_time_qfq 是否逐 bar 生效

`AdjustmentEngine.adjust_bars_point_in_time_qfq()` 对每根 bar 单独计算 factor。计算时只允许使用：

```text
known_date <= 当前 bar datetime
```

因此 corporate action 在 known_date 前不会影响价格，known_date 后才可能影响。

## 3. Strategy history 是否含未来复权价格

回测前会把每根 bar 按 point-in-time 规则逐根调整。策略看到的 `history_data[:i+1]` 中，每根历史 bar 的 factor 都是在该 bar 时间点可知的信息计算出的，不会因为后面的 corporate action 更新而回写未来信息。

## 4. qfq/hfq Readiness 上限

普通 `qfq/hfq` 会被标记 `FUTURE_LEAK_RISK`。Readiness 分类中，`qfq/hfq` 最高只能到 `RESEARCH_ONLY`，不能进入 `PAPER_READY` 或 `LIVE_CANDIDATE`。

## 5. 日内 signal / execute datetime

orders.csv 已包含：

- `signal_datetime`
- `execute_datetime`
- `timeframe`

审计要求 `execute_datetime > signal_datetime`。

