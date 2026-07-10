# Intraday Data Layer

## 1. 为什么 A股日内 bar 不能按自然时间聚合

A股有午休，交易时段是 09:30-11:30 和 13:00-15:00。按自然小时或自然 10 分钟直接聚合，会生成 11:30-12:30、12:30-13:30 这类不存在的交易 bar，污染回测。

## 2. 10min / 1h 分桶规则

10min：

- 09:30-09:40 ... 11:20-11:30
- 13:00-13:10 ... 14:50-15:00
- 一天 24 根

1h：

- 09:30-10:30
- 10:30-11:30
- 13:00-14:00
- 14:00-15:00
- 一天 4 根

30m 一天 8 根。所有分桶禁止跨午休、禁止跨交易日。

## 3. T+1 如何在日内周期生效

持仓 lot 记录买入日期。即使 10:00 买入、14:00 出现卖出信号，当天也不会释放为可卖持仓，卖出会被 ExecutionEngine / RiskManager 阻断。

## 4. 涨跌停如何在日内周期生效

日内执行仍使用 A股涨跌停规则：涨停不能买入，跌停不能卖出。日内 bar 的开盘价如果已经触及涨跌停，订单不会成交。

## 5. 当前 ParquetStore 的现实边界

V5 的 `ParquetStore` 是 CSV-backed store：文件扩展名是 `.parquet`，但内容是 CSV。这是为了让 0 基础用户不安装 `pyarrow` 也能跑通课程和测试。

接口已经按真实 parquet 存储设计：

- `save_bars(symbol, timeframe, rows)`
- `load_bars(symbol, timeframe)`
- `list_symbols(timeframe)`
- `has_symbol(symbol, timeframe)`

后续切换到 pyarrow parquet 时，上层 CLI、DataProvider、BacktestEngine 不需要改，只替换 `ParquetStore` 内部读写实现。
