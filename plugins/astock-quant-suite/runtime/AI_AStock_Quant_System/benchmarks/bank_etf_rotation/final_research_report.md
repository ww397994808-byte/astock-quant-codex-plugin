# Final Research Report

研究方向：银行ETF 红利ETF 轮动
识别范式：rotation
研究周期：1d
复权方式：point_in_time_qfq
数据来源：benchmark_local
研究假设：轮动策略的关键是评分差足够大再切换，减少频繁换手。

## 结论
- 当前首选候选：rotation_001
- 综合评分：-0.002245
- 样本外收益：0.000846
- 最大回撤：-0.048124
- 交易次数：9
- 说明：排序不是按总收益，而是按 Calmar、样本外、回撤、稳定性和交易次数综合评分。

## 过拟合提示
- rotation_001: 参数 top_k 位于搜索边界；参数 switch_threshold 位于搜索边界；参数 rebalance_frequency 位于搜索边界
- rotation_002: 参数 top_k 位于搜索边界；参数 switch_threshold 位于搜索边界；参数 rebalance_frequency 位于搜索边界
- rotation_003: 参数 top_k 位于搜索边界；参数 switch_threshold 位于搜索边界；参数 rebalance_frequency 位于搜索边界
- rotation_004: 参数 top_k 位于搜索边界；参数 switch_threshold 位于搜索边界；参数 rebalance_frequency 位于搜索边界
- rotation_005: 参数 top_k 位于搜索边界；参数 switch_threshold 位于搜索边界；参数 rebalance_frequency 位于搜索边界
- rotation_006: 参数 top_k 位于搜索边界；参数 switch_threshold 位于搜索边界；参数 rebalance_frequency 位于搜索边界
- rotation_007: 参数 top_k 位于搜索边界；参数 switch_threshold 位于搜索边界；参数 rebalance_frequency 位于搜索边界
- rotation_008: 参数 top_k 位于搜索边界；参数 switch_threshold 位于搜索边界；参数 rebalance_frequency 位于搜索边界

风险提示：研究报告用于教学和研究，不构成投资建议；进入模拟盘或实盘前仍需审计和 pre-trade check。
