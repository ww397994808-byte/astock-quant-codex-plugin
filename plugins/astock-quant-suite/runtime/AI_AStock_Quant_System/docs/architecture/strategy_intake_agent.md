# Strategy Intake Agent

## 1. 为什么 0 基础用户不能直接进入回测

0 基础用户常说的是“跌多了买、涨回去卖、控制回撤”这种方向感。它不是策略定义，缺少标的、周期、入场、出场、仓位、风险、复权和目标。如果直接回测，系统只能猜，猜出来的结果不可信。

## 2. Strategy Intake Agent 如何追问

Intake Agent 使用分层问题：

- 交易对象；
- 策略类型；
- 周期；
- 入场；
- 出场；
- 仓位；
- 风险；
- 目标；
- 数据与复权；
- 实盘意图。

完整度低于 70 分时，不允许直接进入 Research Agent，只输出最多 5 个关键追问。

## 3. 如何从自然语言生成结构化策略需求

`IntentParser` 用显式规则识别：

- 标的，例如中国神华 -> `601088.SH`；
- 周期，例如 1小时 -> `1h`；
- 策略范式，例如跌多了买涨回去卖 -> `swing`；
- 风险偏好，例如控制回撤 -> `max_drawdown`；
- 复权方式，例如前复权 -> `point_in_time_qfq`。

结果写入 `strategy_requirement.json`。

## 4. 如何生成 Strategy DSL

`DSLBuilder` 生成 `strategy_dsl.yaml`，把需求转成结构化研究配置，包括：

- market；
- symbols；
- timeframe；
- adjust；
- pattern；
- entry；
- exit；
- sizing；
- objective；
- constraints。

## 5. 如何生成可交给 Codex 的规范化 Prompt

`PromptBuilder` 生成 `codex_research_prompt.md`。这个 Prompt 不让 Codex 手写一次性脚本，而是要求调用 Task Layer / Research Agent，并遵守审计、样本外、回撤和 QMT 安全边界。

## 6. 如何与 Research Agent 衔接

当 `completeness_score >= 70`，Intake Agent 会生成 DSL 和 Codex Prompt。用户确认后，Research Agent 可读取 DSL 中的方向、标的、周期和复权方式，开始批量研究。

