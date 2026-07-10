# Research Plan

- 原始方向：神华大跌后买 反弹卖 尽量减少回撤
- 策略范式：timing
- 周期：1d
- 复权方式：point_in_time_qfq
- 数据来源：benchmark_local
- 研究假设：趋势或择时策略应减少震荡区间误交易，并在趋势阶段获得稳定收益。

## 变量
- short_window
- long_window

## 入场候选
- 短均线上穿长均线
- 趋势突破

## 出场候选
- 短均线下穿长均线

## 风控候选
- max_drawdown
- stop_loss
- drift_threshold
- switch_threshold

## 搜索空间
```json
{
  "short_window": [
    5,
    10
  ],
  "long_window": [
    20,
    30
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
