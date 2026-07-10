# Research Plan

- 原始方向：1小时布林低吸 波段
- 策略范式：swing
- 周期：1h
- 复权方式：point_in_time_qfq
- 数据来源：benchmark_local
- 研究假设：在稳健偏好下，低吸/回撤类波段策略应优先降低最大回撤，并在样本外保持不过度退化。

## 变量
- window
- num_std
- stop_loss

## 入场候选
- 布林下轨低吸
- N日回撤买入

## 出场候选
- 回到布林中轨
- 止损
- 时间退出

## 风控候选
- max_drawdown
- stop_loss
- drift_threshold
- switch_threshold

## 搜索空间
```json
{
  "window": [
    10,
    20,
    30
  ],
  "num_std": [
    1.8,
    2.0,
    2.2
  ],
  "stop_loss": [
    0.06,
    0.1
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
