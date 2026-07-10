# Final Research Report

研究方向：高股息组合 长期持有 年度再平衡
识别范式：stock_selection
研究周期：1d
复权方式：point_in_time_qfq
数据来源：benchmark_local
研究假设：选股策略的关键是因子排序稳定性、调仓频率和组合分散度。

## 结论
- 当前首选候选：stock_selection_001
- 综合评分：-0.002245
- 样本外收益：0.000846
- 最大回撤：-0.048124
- 交易次数：9
- 说明：排序不是按总收益，而是按 Calmar、样本外、回撤、稳定性和交易次数综合评分。

## 过拟合提示
- stock_selection_001: 参数 top_n 位于搜索边界；参数 rebalance_frequency 位于搜索边界
- stock_selection_002: 参数 top_n 位于搜索边界；参数 rebalance_frequency 位于搜索边界
- stock_selection_003: 参数 top_n 位于搜索边界；参数 rebalance_frequency 位于搜索边界
- stock_selection_004: 参数 top_n 位于搜索边界；参数 rebalance_frequency 位于搜索边界

风险提示：研究报告用于教学和研究，不构成投资建议；进入模拟盘或实盘前仍需审计和 pre-trade check。
