# System Risk Boundaries

## 非投资建议

本系统用于课程教学、策略研究流程训练和工程化演示，不构成任何投资建议。

## 回测不等于实盘

回测结果依赖数据质量、成交假设、费用模型、涨跌停处理、停牌处理和参数选择。回测通过不代表实盘能盈利。

## Sample Data 不代表真实市场

课程版默认 sample-backed 数据用于离线可运行。sample data 只能帮助学生学习流程，不能用于真实投资判断。

## qfq / hfq 风险

普通 qfq/hfq 可能把未来分红送转信息提前反映到历史价格里。可信研究优先使用 `raw` 或 `point_in_time_qfq`。

## QMT 真实交易默认关闭

QMTBroker 默认 dry_run。真实下单必须同时满足配置开启、dry_run=false、pre-trade check 通过、审计 VALID、未触发 emergency stop，并由用户输入 `CONFIRM_REAL_TRADE`。

## LIVE_CANDIDATE 不等于可直接实盘

LIVE_CANDIDATE 只表示研究结果可能进入更严格的模拟盘和人工审查阶段，不代表可以直接实盘。

## 所有策略必须先模拟盘

任何策略进入实盘前必须至少完成：

- 数据质量检查；
- FutureLeak / TradeRule / AdjustmentLeak 审计；
- Readiness 检查；
- 压力测试；
- 模拟盘观察；
- 人工复核；
- QMT pretrade-check。

## AI 不能绕过风控

Codex / Skill / Agent 只能调用 Task Layer 和 Service Layer，不能直接调用真实 `place_order` 绕过风控。
