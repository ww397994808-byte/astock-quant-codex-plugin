# Research Plan

- 原始方向：煤炭 银行 电力 轮动 每月调仓
- 策略范式：rotation
- 周期：1d
- 复权方式：point_in_time_qfq
- 数据来源：benchmark_local
- 研究假设：轮动策略的关键是评分差足够大再切换，减少频繁换手。

## 变量
- top_k
- switch_threshold
- rebalance_frequency

## 入场候选
- 强弱评分 top_k

## 出场候选
- 评分切换

## 风控候选
- max_drawdown
- stop_loss
- drift_threshold
- switch_threshold

## 搜索空间
```json
{
  "top_k": [
    1,
    2
  ],
  "switch_threshold": [
    0.0,
    0.05
  ],
  "rebalance_frequency": [
    10,
    20
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
