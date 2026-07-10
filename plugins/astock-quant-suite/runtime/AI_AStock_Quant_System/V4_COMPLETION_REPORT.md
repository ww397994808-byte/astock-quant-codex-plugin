# V4 Completion Report

## 1. 当前系统可信度提升了什么

- 新增 Data Quality Layer，检查日期、价格、成交量、跳变、日历和复权疑点。
- 新增 Enhanced Metrics，补充 CAGR、Calmar、Sortino、Recovery Time、月度胜率和滚动指标。
- 新增 Readiness Classification，将结果分为 INVALID、RESEARCH_ONLY、PAPER_READY、LIVE_CANDIDATE。
- 新增 Stress Test Engine，生成极端行情场景。
- 新增 Config Validator、CLI Doctor 和 Explain Report。

## 2. 还有哪些风险

- 多标的组合净值统计仍是后续重点。
- 复权判断目前是价格推断，需要真实分红送转数据源增强。
- 压力测试第一版生成场景并输出报告，尚未对每个场景完整重新跑全部策略矩阵。
- QMT 实盘仍需真实 Windows/MiniQMT 环境联调。

## 3. 哪些功能适合课程用户

- `doctor` 自检；
- `data_quality_report.md`；
- `metrics_report.md`；
- `readiness_report.md`；
- `explain-report`；
- Research Agent V2 自动研究报告。

## 4. 哪些功能暂不适合实盘

- pair_trading；
- event_driven；
- 未做多标的验证的组合/选股/轮动结果；
- Readiness 低于 LIVE_CANDIDATE 的策略。

## 5. 下一阶段建议

- V5 增强多标的 Portfolio 和 RebalancePlan 真实执行。
- 接入真实交易日历和复权/分红数据。
- 压力测试从“场景生成”升级为“场景批量回测评分”。
- QMT 在真实环境中做 dry_run 联调。

