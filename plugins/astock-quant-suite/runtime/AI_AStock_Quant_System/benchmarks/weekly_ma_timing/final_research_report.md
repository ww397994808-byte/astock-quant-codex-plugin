# Final Research Report

研究方向：周线均线择时
识别范式：swing
研究周期：1w
复权方式：point_in_time_qfq
数据来源：benchmark_local
研究假设：在稳健偏好下，低吸/回撤类波段策略应优先降低最大回撤，并在样本外保持不过度退化。

## 结论
- 当前首选候选：swing_005
- 综合评分：0.3
- 样本外收益：0.0
- 最大回撤：0.0
- 交易次数：0
- 说明：排序不是按总收益，而是按 Calmar、样本外、回撤、稳定性和交易次数综合评分。

## 过拟合提示
- swing_001: 样本内好、样本外明显退化；参数 window 位于搜索边界；参数 num_std 位于搜索边界；参数 stop_loss 位于搜索边界；交易次数过少，结果不稳定；审计 INVALID
- swing_002: 样本内好、样本外明显退化；参数 window 位于搜索边界；参数 num_std 位于搜索边界；参数 stop_loss 位于搜索边界；交易次数过少，结果不稳定；审计 INVALID
- swing_003: 样本内好、样本外明显退化；参数 window 位于搜索边界；参数 stop_loss 位于搜索边界；交易次数过少，结果不稳定；审计 INVALID
- swing_004: 样本内好、样本外明显退化；参数 window 位于搜索边界；参数 stop_loss 位于搜索边界；交易次数过少，结果不稳定；审计 INVALID
- swing_005: 参数 window 位于搜索边界；参数 num_std 位于搜索边界；参数 stop_loss 位于搜索边界；交易次数过少，结果不稳定
- swing_006: 参数 window 位于搜索边界；参数 num_std 位于搜索边界；参数 stop_loss 位于搜索边界；交易次数过少，结果不稳定
- swing_007: 样本内好、样本外明显退化；参数 num_std 位于搜索边界；参数 stop_loss 位于搜索边界；交易次数过少，结果不稳定；审计 INVALID
- swing_008: 样本内好、样本外明显退化；参数 num_std 位于搜索边界；参数 stop_loss 位于搜索边界；交易次数过少，结果不稳定；审计 INVALID
- swing_009: 样本内好、样本外明显退化；参数 stop_loss 位于搜索边界；交易次数过少，结果不稳定；审计 INVALID
- swing_010: 样本内好、样本外明显退化；参数 stop_loss 位于搜索边界；交易次数过少，结果不稳定；审计 INVALID
- swing_011: 样本内好、样本外明显退化；参数 num_std 位于搜索边界；参数 stop_loss 位于搜索边界；交易次数过少，结果不稳定；审计 INVALID
- swing_012: 样本内好、样本外明显退化；参数 num_std 位于搜索边界；参数 stop_loss 位于搜索边界；交易次数过少，结果不稳定；审计 INVALID

风险提示：研究报告用于教学和研究，不构成投资建议；进入模拟盘或实盘前仍需审计和 pre-trade check。
