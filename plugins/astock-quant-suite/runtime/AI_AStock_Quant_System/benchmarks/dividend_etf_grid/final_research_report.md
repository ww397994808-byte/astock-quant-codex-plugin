# Final Research Report

研究方向：红利ETF 网格 跌5%加仓 涨5%减仓
识别范式：grid
研究周期：1d
复权方式：point_in_time_qfq
数据来源：benchmark_local
研究假设：网格策略适合区间震荡，核心是层级间距、单层仓位和回撤控制。

## 结论
- 当前首选候选：grid_002
- 综合评分：0.341474
- 样本外收益：0.0
- 最大回撤：-0.003635
- 交易次数：1
- 说明：排序不是按总收益，而是按 Calmar、样本外、回撤、稳定性和交易次数综合评分。

## 过拟合提示
- grid_001: 样本内好、样本外明显退化；参数 grid_step 位于搜索边界；参数 levels 位于搜索边界；参数 layer_percent 位于搜索边界；交易次数过少，结果不稳定；收益可能由少数交易贡献
- grid_002: 样本内好、样本外明显退化；参数 grid_step 位于搜索边界；参数 levels 位于搜索边界；参数 layer_percent 位于搜索边界；交易次数过少，结果不稳定；收益可能由少数交易贡献
- grid_003: 样本内好、样本外明显退化；参数 grid_step 位于搜索边界；参数 levels 位于搜索边界；参数 layer_percent 位于搜索边界；交易次数过少，结果不稳定；收益可能由少数交易贡献
- grid_004: 样本内好、样本外明显退化；参数 grid_step 位于搜索边界；参数 levels 位于搜索边界；参数 layer_percent 位于搜索边界；交易次数过少，结果不稳定；收益可能由少数交易贡献
- grid_005: 参数 grid_step 位于搜索边界；参数 levels 位于搜索边界；参数 layer_percent 位于搜索边界；交易次数过少，结果不稳定
- grid_006: 参数 grid_step 位于搜索边界；参数 levels 位于搜索边界；参数 layer_percent 位于搜索边界；交易次数过少，结果不稳定
- grid_007: 参数 grid_step 位于搜索边界；参数 levels 位于搜索边界；参数 layer_percent 位于搜索边界；交易次数过少，结果不稳定
- grid_008: 参数 grid_step 位于搜索边界；参数 levels 位于搜索边界；参数 layer_percent 位于搜索边界；交易次数过少，结果不稳定

风险提示：研究报告用于教学和研究，不构成投资建议；进入模拟盘或实盘前仍需审计和 pre-trade check。
