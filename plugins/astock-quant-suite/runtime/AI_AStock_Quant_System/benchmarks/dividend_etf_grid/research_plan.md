# Research Plan

- 原始方向：红利ETF 网格 跌5%加仓 涨5%减仓
- 策略范式：grid
- 周期：1d
- 复权方式：point_in_time_qfq
- 数据来源：benchmark_local
- 研究假设：网格策略适合区间震荡，核心是层级间距、单层仓位和回撤控制。

## 变量
- grid_step
- levels
- layer_percent

## 入场候选
- 价格下穿网格层级

## 出场候选
- 价格上穿网格层级

## 风控候选
- max_drawdown
- stop_loss
- drift_threshold
- switch_threshold

## 搜索空间
```json
{
  "grid_step": [
    0.02,
    0.03
  ],
  "levels": [
    2,
    3
  ],
  "layer_percent": [
    0.08,
    0.12
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
