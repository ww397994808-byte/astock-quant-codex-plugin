# Point-in-Time Adjustment Engine

## 1. Point-in-Time QFQ 如何避免未来函数

`point_in_time_qfq` 逐 bar 推进，只允许使用 `known_date <= 当前时间` 的 corporate action。未来才公告的分红、送转、配股不能提前影响历史价格。

## 2. 为什么普通 qfq 不能直接用于可信实盘研究

普通 qfq 往往用全历史 corporate action 一次性重算历史价格。这样历史上某一天的价格可能已经包含未来分红送转信息，属于潜在未来函数。V5 中普通 `qfq/hfq` 会标记 `FUTURE_LEAK_RISK`，审计会 INVALID。

## 3. 支持复权类型

- `raw`：默认，不复权。
- `point_in_time_qfq`：可信研究优先。
- `qfq`：允许读取，但标记未来函数风险。
- `hfq`：允许读取，但标记未来函数风险。

