# Code Health Audit

## 检查范围

本次检查覆盖核心代码、任务层、服务层、研究层、回测模板、审计、数据层、QMT 安全骨架、V7/V7.2 批量实验层。

## TODO / FIXME

未发现显式 TODO / FIXME。

## 空实现 / Stub / 工程预留

以下属于明确工程预留，不能在课程中承诺为完整实盘能力：

- `qmt/qmt_broker_stub.py`：dry-run stub；
- `qmt/qmt_broker.py`：真实 QMT 连接骨架，未配置真实账号和路径；
- `market_data/providers/qmt_provider.py`：QMT 数据 provider 骨架；
- `market_data/providers/tushare_provider.py`：Tushare provider 骨架；
- `paper_trading/paper_broker.py`：当前复用 QMTBrokerStub，适合教学演示；
- `backtest_templates/pair_trading_template.py`：A股不支持裸卖空，第一版只保留 blocker；
- `backtest_templates/event_driven_template.py`：需要真实事件数据源，第一版只保留 blocker。

## 只是报告但代码约束不足的地方

V7.2.1 已修正两个重要问题：

- `1w` 不再只是计划，已支持 1d -> 1w 聚合；
- regime split 不再只是标签，已支持真实区间切片。

仍需后续增强：

- 真实 AkShare/Tushare 行情接入；
- 更严格的多标的组合净值；
- 更真实的成交滑点模型；
- 基于指数/行业的 regime 切片；
- QMT 真实连接验收。

## 测试覆盖

当前测试覆盖：

- A股 T+1、涨跌停、手数、费用；
- 回测模板；
- Research Agent；
- Strategy Intake；
- Intraday / Weekly / PIT adjustment；
- Data Acquisition；
- Feedback Loop；
- Strategy Action Compiler；
- Batch Experiment Scheduler；
- Regime Slice；
- vn.py adapter。

## 重复模块和过度工程

存在一定工程预留，例如 agent、storage、vnpy adapter、QMT provider。它们适合作为课程进阶章节，不应在基础课中过早展开。

## 当前代码健康结论

系统适合作为课程工程底座。实盘相关模块仍应明确标记为安全骨架和 dry-run 演示，不能作为真实交易交付承诺。
