# Backtest Feedback Optimization Loop

## 为什么优化闭环必须发生在回测之后

一次性参数搜索只能回答“这些预设参数里哪个最好”，不能回答“策略为什么失败”。V7 把优化放在回测之后：先得到真实成交、费用、T+1、涨跌停、审计、Readiness 和数据质量结果，再决定下一轮改什么。

## 每轮如何提取问题

BacktestResultAnalyzer 读取 performance、trades、metrics、audit、readiness、stress、data quality 等结果，识别回撤过大、交易次数过少、交易过多、收益低、样本外退化、收益集中在少数交易、参数边界和过拟合迹象。

## 如何把问题转成策略修改动作

OptimizationDirector 把问题映射为修改动作。例如回撤过大时增加止损、趋势过滤、降低仓位；交易次数过少时放宽入场条件；样本外退化时简化策略、减少参数并增加 Walk Forward 验证。

## 为什么连续无改善不能简单停止

连续无改善通常说明当前参数空间、入场逻辑、出场逻辑、周期或标的可能不匹配。直接停止会把“没找到”误判成“方向无效”。V7 把连续无改善作为 Deep Diagnosis 的触发信号。

## Deep Diagnosis 如何工作

Deep Diagnosis 会复盘所有失败实验，分类失败原因，并结合 RegimeAnalyzer 判断策略是否只在某些市场状态下有效。随后 ResearchExpander 扩大研究空间，至少安排一轮 expanded experiments。

## 如何扩大研究空间

系统会按失败类型扩展：参数空间太窄就扩大范围，入场无效就替换或增加入场规则，出场无效就测试止盈、移动止盈或持仓天数退出，周期不匹配就测试 10m、30m、1h、1d、1w。

## 如何防止越优化越过拟合

候选选择不按单一收益排序，而综合 Readiness、审计状态、样本外、最大回撤、Calmar、稳定性、交易次数、压力测试、数据质量、策略简洁度、复权风险和 regime robustness。审计 INVALID 不进入候选，普通 qfq/hfq 不允许成为 LIVE_CANDIDATE。

## 如何判断最终候选

CandidateSelector 只允许审计有效、Readiness 合理、样本外和稳定性不差的结果进入 final_candidates。候选用于模拟盘观察，不代表可直接实盘。

## 如何判断方向暂不值得继续

如果 Deep Diagnosis 后仍无候选，并且主要失败原因集中在数据质量、交易规则无法成交、样本外退化、收益集中或策略结构无效，则报告会明确说明该方向暂不值得继续，并输出下一轮可验证的问题。
