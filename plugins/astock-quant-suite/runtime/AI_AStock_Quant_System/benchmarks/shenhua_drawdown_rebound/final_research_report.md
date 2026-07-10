# Final Research Report

研究方向：神华大跌后买 反弹卖 尽量减少回撤
识别范式：timing
研究周期：1d
复权方式：point_in_time_qfq
数据来源：benchmark_local
研究假设：趋势或择时策略应减少震荡区间误交易，并在趋势阶段获得稳定收益。

## 结论
- 当前首选候选：timing_003
- 综合评分：0.135947
- 样本外收益：0.0
- 最大回撤：-0.021233
- 交易次数：8
- 说明：排序不是按总收益，而是按 Calmar、样本外、回撤、稳定性和交易次数综合评分。

## 过拟合提示
- timing_001: 参数 short_window 位于搜索边界；参数 long_window 位于搜索边界
- timing_002: 参数 short_window 位于搜索边界；参数 long_window 位于搜索边界
- timing_003: 参数 short_window 位于搜索边界；参数 long_window 位于搜索边界
- timing_004: 参数 short_window 位于搜索边界；参数 long_window 位于搜索边界

风险提示：研究报告用于教学和研究，不构成投资建议；进入模拟盘或实盘前仍需审计和 pre-trade check。
