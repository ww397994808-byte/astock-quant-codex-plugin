# Research To QMT Stage Gates

本文档定义 A股版本从研究到 QMT 前检查的硬门槛。它的目标不是让策略更容易通过，而是让 0 基础用户不会在不知道风险的情况下越级。

## 阶段

```text
RESEARCH_ONLY
BACKTEST_VALID
PAPER_READY
PAPER_OBSERVED
QMT_READONLY_READY
PRETRADE_VALID
LIVE_CANDIDATE
```

`INVALID` 可以出现在任何阶段。只要出现 `INVALID`，停止向后推进。

## 硬规则

1. 没有 `backtest_plan.yaml`，最多停在 `RESEARCH_ONLY`。
2. 审计不是 `VALID`，直接 `INVALID`。
3. 策略范式不允许 QMT，最多停在 `RESEARCH_ONLY`。
4. Readiness 未达到 `PAPER_READY`，不能进入模拟盘观察后的推进。
5. 模拟盘观察未通过，不能进入 QMT 只读检查后的推进。
6. QMT 只读检查未通过，不能进入实盘前检查。
7. 实盘前检查未通过，不能讨论真实下单。

## 未来函数准则

信号发生在 bar `t` 时，只允许使用 bar `t` 及以前已经产生的数据。主要包括 OHLCV、交易日历、A股交易规则状态、当时可知的复权或公司行为数据。

以下情况一律按未来函数处理：

- 使用 `shift(-1)`、未来收益、未来标签、明天开盘价或明天收盘价生成信号；
- 使用居中滚动窗口；
- 使用全样本分位数、全样本排名、全样本标准化生成历史信号；
- 信号依赖收盘价，却在同一根 K 线收盘价成交；
- 普通 qfq/hfq 把未来分红送转提前反映到历史价格里；
- 股票池或因子包含当时不可知的成分。

默认执行模型：收盘确认信号，下一根 K 线开盘成交。

## 新增入口

新手优先使用：

```bash
python3 cli.py student-workflow --idea "<包含标的的策略想法>" --timeframe <周期> --adjust point_in_time_qfq
```

该命令生成：

- `workflow_manifest.json`
- `STUDENT_WORKFLOW_SUMMARY.md`
- `NEXT_ACTIONS.md`

如果未提供 `--strategy`，系统会根据 intake 计划和策略想法自动选择已注册的默认策略；无法安全选择时会在 `select-strategy` 阶段阻断。
如果未提供 `--symbol`，系统会先从策略想法里解析标的；无法识别时会在 `resolve-symbol` 阶段阻断。
如果未提供 `--data`，系统会通过数据获取层读取已有缓存或准备课程版本地样例数据。
当 workflow 为 `INVALID` 时，`NEXT_ACTIONS.md` 会把阻断项整理为下一版策略想法和重跑命令；它不是放行凭证。

当前默认策略选择：

- 布林/低吸/回撤：`boll_mean_reversion`
- 均线/趋势：`ma_cross`
- 红利/股息：`dividend_drawdown`
- 网格/分层：`grid`

轮动、组合再平衡和选股需要 point-in-time 多标的数据、评分表或因子表；没有这些证据时不自动伪装成可实盘策略。

手动阶段检查使用：

```bash
python3 cli.py stage-check --run-id latest --plan-run-id <intake_run_id>
```

该命令读取：

- `backtest_plan.yaml`
- `audit_report.md`
- `readiness_report.md`
- `paper_observation.json`
- `qmt_account_snapshot.json`

并生成：

- `stage_gate_report.md`

## 模拟盘观察策略

`paper` 命令应传入 intake 阶段的 `plan_run_id`：

```bash
python3 cli.py paper --strategy <策略名> --symbol <代码> --timeframe <周期> --adjust point_in_time_qfq --plan-run-id <intake_run_id>
```

系统会读取 `backtest_plan.yaml` 里的 `strategy_pattern` 和 `timeframe`，生成对应的观察策略：

- 日线择时/波段：至少 20 个观察 bar、3 笔成交；
- 周线择时/波段：至少 20 个观察 bar、1 笔成交；
- 日内择时/波段：至少 20 个观察 bar、6 笔成交；
- 网格：至少 20 到 30 个观察 bar、8 笔成交；
- 轮动/再平衡：至少 24 到 60 个观察 bar、4 笔成交；
- 选股：至少 36 到 90 个观察 bar、5 笔成交，但第一阶段仍不作为 QMT 放行依据。

观察策略会写入 `paper_observation.json` 和 `paper_observation_report.md`。

## Codex Skill

本地 Skill 已安装在：

```text
~/.codex/skills/astock-quant-research
```

用途：

- 把新手的自然语言策略想法转成固定工作流；
- 自动强调未来函数审计；
- 在每个阶段给出下一条可执行命令；
- QMT 只做 readonly，不直接引导真实下单。

## 仍待增强

1. 多标的组合净值、停牌、涨跌停、现金占用和换仓滑点还需要更细颗粒度的实盘贴近。
2. QMT 写入侧应继续保持隔离，等 readonly 和 pretrade 证据链稳定后再做真实委托封装。
3. `pretrade-check` 已读取 stage/QMT 证据，但真实交易时间、标的可交易、重复下单和异常委托仍需要接入真实券商状态才能完整判断。
