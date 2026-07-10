# Research Plan

- 原始方向：高股息组合 长期持有 年度再平衡
- 策略范式：stock_selection
- 周期：1d
- 复权方式：point_in_time_qfq
- 数据来源：benchmark_local
- 研究假设：选股策略的关键是因子排序稳定性、调仓频率和组合分散度。

## 变量
- top_n
- rebalance_frequency

## 入场候选
- 因子排名 top_n

## 出场候选
- 调仓日剔除

## 风控候选
- max_drawdown
- stop_loss
- drift_threshold
- switch_threshold

## 搜索空间
```json
{
  "top_n": [
    3,
    5
  ],
  "rebalance_frequency": [
    20,
    40
  ]
}
```

## 约束
- A股 T+1
- 涨跌停
- 停牌不可交易
- 100股手数
- 费用计入
- signal_time < execute_time
