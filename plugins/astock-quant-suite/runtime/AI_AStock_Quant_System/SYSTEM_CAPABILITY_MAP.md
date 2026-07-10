# System Capability Map

## 当前系统能做什么

AI_AStock_Quant_System 当前已经形成完整教学研究链路：

```text
Intake -> Strategy DSL -> Research Agent -> Backtest -> Audit -> Paper Observation -> Stage Gate -> QMT Readonly -> Pretrade Check
```

可用于课程正式讲解的能力：

- 本地 CSV / sample-backed 数据读取；
- 1d、1w、1h、30m、10m、5m 数据周期；
- 1d -> 1w 周线真实聚合；
- point-in-time qfq 复权风险控制；
- A股 T+1、涨跌停、停牌、100股、费用规则；
- Strategy Intake Agent；
- Strategy DSL；
- Research Agent；
- Backtest Templates；
- Feedback Optimization Loop；
- Batch Experiment Scheduler；
- Regime Slice Experiments；
- Data Quality；
- Future Leak / Trade Rule / Adjustment Leak Audit；
- Readiness Classification；
- Paper observation 硬门槛；
- Stage Gate 阶段判断；
- QMT readonly 只读安全检查；
- QMT dry-run / pretrade 安全骨架；
- Codex Skill 新手工作流；
- student-first-run 把环境体检、想法预检和安全 student-workflow 启动准备串成首跑向导；
- student-course-path 把环境体检、想法预检、回测计划预检和可选未来函数代码预检串成 0 基础课程路线包；
- student-research-contract 把开跑前的标的、范式、周期、复权、撮合、审计和推进门槛固化成研究契约；
- student-contract-check 在 workflow 后对账研究契约，检查标的、周期、复权、范式、模板和撮合假设是否漂移；
- student-handoff-pack 把当前阶段、下一步、报告入口、session 复盘和交付体检汇总成学员交付包；
- student-idea-preflight 在完整工作流前检查策略想法质量、资产边界、回测计划和下一步命令；
- student-backtest-plan-precheck 在完整回测前独立检查策略范式、数据周期、回测模板、撮合假设和推进边界；
- student-future-leak-precheck 在完整回测前对学员代码/策略文件做未来函数静态预检；
- core5-walk-forward 对内置 Core5 相对强弱网格包执行严格 walk-forward 回测，并输出逐月因果窗口审计；
- student-workflow 一键编排与 workflow manifest；
- student-workflow 自动选择已注册默认策略，包括布林、均线、红利和网格；
- student-workflow 自动解析中文标的名称；
- student-workflow 默认自动准备本地数据；
- student-workflow 生成 NEXT_ACTIONS.md，把阻断原因转成下一版修改建议；
- student-product-audit 动态检查课程交付状态、QMT 安全边界、Skill 文件、关键测试和最新 workflow 证据；
- CLI 教学入口。

## 当前系统不能做什么

- 不能保证策略盈利；
- 不能替代真实投研；
- 不能直接用于真实下单；
- 不能把 sample data 当真实市场；
- 不能把普通 qfq/hfq 结果当作可信实盘研究；
- 不能完整覆盖所有 A股细则和券商边界；
- 不能承诺多标的组合净值与实盘完全一致；
- 不能用自然语言绕过审计、风控或 QMT 安全确认。
- 不能把 QMT readonly 当成真实下单许可；
- 不能把 pretrade-check 当成收益承诺。

## 工程预留但不适合作为课程承诺的能力

- QMTBroker 真实连接；
- vn.py adapter 兼容层；
- 多标的组合精细净值；
- 真实 AkShare/Tushare 数据接入；
- 并行批量实验；
- 更复杂的 regime 模型；
- 事件驱动策略真实数据源；
- 配对交易市场中性策略。

## 适合课程卖点的能力

- 0基础用户用一句话生成结构化策略需求；
- 0基础用户用 student-course-path 获得从想法到研究开跑的路线图、阻断项和下一步命令；
- 正式研究前用 student-research-contract 生成 contract_id，防止同一轮研究中偷换回测假设；
- 正式研究后用 student-contract-check 确认 workflow 仍然服从 contract_id 对应假设；
- 首跑向导默认只预演，明确 `--execute` 才启动研究 workflow，且不触碰 QMT/pretrade/下单；
- 学员交付包可作为课后/助教复盘入口，减少在 reports 目录里找文件；
- 一句想法先经过 student-idea-preflight，明确是否足够开跑、还缺什么、是否误入数字货币版本；
- 不同策略先经过 student-backtest-plan-precheck，明确网格、轮动、选股、波段、日内等策略不能共用同一套回测周期和撮合假设；
- 学员代码先经过 student-future-leak-precheck，把负向 shift、未来标签、居中窗口、forward merge、危险 IO/import 等典型未来函数风险前置拦截；
- 固定池子轮动/网格研究可用 core5-walk-forward，逐月固化 `参数训练窗口 <= 调仓日 < 测试窗口`，避免无意引入未来函数；
- 一键跑通 intake/research/backtest/optimize-loop/explain-report；
- A股规则代码化；
- 回测后反馈优化闭环；
- 批量实验验证；
- 审计失败不能进入模拟盘或实盘；
- Readiness 告诉学生策略处在哪个阶段。
- Stage Gate 告诉学生下一步为什么能做或不能做；
- Codex Skill 把 intake、回测、审计、模拟盘、QMT 只读串成固定路径。
- student-product-audit 把“还能不能交给学员用、差什么”固化成可重复生成的交付体检报告。
