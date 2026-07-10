# Quick Start For Students

## 0. 先确认版本边界

本项目是 A 股/QMT 版本，只支持 A 股、ETF 和指数。BTC、ETH、USDT、交易所合约、永续合约等数字货币策略不要放进这个版本；数字货币版需要单独的数据源、撮合、风控、交易接口和合规规则，不能混用 A 股的 T+1、涨跌停、复权和 QMT 假设。

## 1. 先做学生版体检

```bash
python3 cli.py student-doctor
```

它会检查当前目录是不是完整项目、核心新手命令是否已挂载、样例数据是否存在、skill 文件是否齐全，以及 QMT 配置是否保持 `dry_run=true`、`enable_real_trade=false`。它不会连接 QMT，不会回测，也不会下单。新手先看 `STUDENT_DOCTOR.md` 的“当前结论”和“下一步”。

如果体检提示缺少 `config/qmt_config.yaml`，先初始化一份安全本地配置：

```bash
python3 cli.py qmt-config-init
```

这个命令只写入本地配置，并强制保持 `dry_run=true`、`enable_real_trade=false`。接入 QMT 只读前，可以人工补账号和 miniQMT 路径：

```bash
python3 cli.py qmt-config-init --account-id "<你的QMT账号>" --mini-qmt-path "<miniQMT路径>" --force
```

即使加了 `--force`，它也不会开启真实交易。

补完后先看 QMT 配置行动单：

```bash
python3 cli.py qmt-config-status
```

只有它显示 `READY_FOR_QMT_READONLY` 时，才进入后面的 `qmt-check`。

老师或助教在开课前，可以跑一次产品化体检：

```bash
python3 cli.py student-product-audit
```

它会生成 `STUDENT_PRODUCT_AUDIT.md/json` 和 `student_product_cards.json`，检查环境、课程文档、Codex Skill、命令注册、关键测试、QMT 安全开关、最新 workflow 证据和 session 追踪证据。这个命令只读本地文件和报告，不会回测、不会连接 QMT、不会下单。若显示 `BLOCKED_PRODUCT_DELIVERY`，先处理阻断项；若显示 `PRODUCT_READY_WITH_WARNINGS`，可以内测或课程使用，但要把提醒项作为课前检查清单。

## 2. 生成示例数据

```bash
python3 cli.py generate-sample-data --timeframe 1d --symbol 601088.SH
```

## 3. 让系统像老师一样追问你的策略想法

0 基础学员优先用课程路线入口。它会一次性串起环境体检、想法预检、回测计划预检，并在你提供策略文件或代码时追加未来函数预检：

```bash
python3 cli.py student-course-path --idea "中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究" --session-id student001
```

如果已经有策略文件：

```bash
python3 cli.py student-course-path --idea "中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究" --file path/to/strategy.py --session-id student001
```

它会生成 `STUDENT_COURSE_PATH.md/json` 和 `student_course_path_cards.json`，把路线步骤、阻断项、提醒项、各子报告路径和下一步命令集中到一张路线图里。显示 `COURSE_PATH_READY` 时，只代表可以进入研究 workflow；它不会自动回测、不会连接 QMT、不会下单。

正式开跑前，建议生成研究契约，把本轮研究的标的、策略范式、数据周期、复权方式、撮合假设、未来函数边界和推进门槛固定下来：

```bash
python3 cli.py student-research-contract --idea "中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究" --session-id student001
```

如果已有策略代码，务必把代码一起绑定：

```bash
python3 cli.py student-research-contract --idea "中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究" --file path/to/strategy.py --session-id student001
```

它会生成 `STUDENT_RESEARCH_CONTRACT.md/json`、`student_research_contract_cards.json` 和 `research_contract.json`。报告里的 `contract_id` 用来标记这一轮研究假设；同一轮研究中不要偷换周期、范式、复权或成交假设。若显示 `CONTRACT_BLOCKED`，不能进入回测。

跑完 `student-workflow` 后，用契约对账确认 workflow 没有偏离开跑前假设：

```bash
python3 cli.py student-contract-check --contract reports/<student_research_contract_run> --workflow reports/<student_workflow_run>
```

如果同一个学员一直使用固定 `--session-id`，也可以直接：

```bash
python3 cli.py student-contract-check --session-id student001
```

它会生成 `STUDENT_CONTRACT_CHECK.md/json` 和 `student_contract_check_cards.json`，检查标的、资产类型、策略范式、周期、复权、模板和撮合假设是否一致。显示 `CONTRACT_DRIFT` 时，不要把这个 workflow 当成该契约的研究证据；应重新按契约运行，或生成新的契约作为新研究分支。

如果你想从一句想法开始，并让系统自动完成“环境体检 + 想法预检 + 研究命令准备”，使用首跑向导：

```bash
python3 cli.py student-first-run --idea "中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究" --session-id student001
```

它会生成 `STUDENT_FIRST_RUN.md/json` 和 `student_first_run_cards.json`。默认情况下，它只准备好 `student-workflow` 命令，不会真正执行研究流程。确认要开始研究时，再明确加 `--execute`：

```bash
python3 cli.py student-first-run --idea "中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究" --session-id student001 --execute
```

即使加了 `--execute`，它也只允许启动 `student-workflow` 研究链路；不会连接 QMT、不会进入 pretrade、不会生成订单交接、不会下单。

如果你已经有一句想法，但不确定够不够完整，先跑预检：

```bash
python3 cli.py student-idea-preflight --idea "中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究" --session-id student001
```

它会生成 `STUDENT_IDEA_PREFLIGHT.md/json` 和 `student_idea_cards.json`，检查标的是否属于 A 股版本、想法完整度、策略范式、周期、回测计划、数据要求、撮合假设和下一步命令。若显示 `READY_FOR_STUDENT_WORKFLOW`，复制报告里的 `student-workflow` 命令继续；若显示 `NEEDS_CLARIFICATION`，先回答澄清问题或运行报告里的 `intake-chat` 命令；若显示 `WRONG_ASSET_VERSION`，说明这是数字货币等非 A 股版本，不能混用本项目的 QMT、T+1、涨跌停和复权假设。

如果你关心“这个策略到底应该怎么回测”，先单独跑回测计划预检：

```bash
python3 cli.py student-backtest-plan-precheck --idea "中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究" --session-id student001
```

它会生成 `STUDENT_BACKTEST_PLAN_PRECHECK.md/json`、`student_backtest_plan_cards.json` 和 `backtest_plan_precheck.yaml`，明确策略范式、数据周期、回测模板、所需数据、信号/成交时点、A 股交易规则、审计项目和 QMT 推进边界。若显示 `BLOCKED_BACKTEST_PLAN`，不要硬跑回测，先看是周期不匹配、策略范式不支持、缺少 point-in-time 数据，还是误入数字货币版本。老师也可以用 `--strategy-pattern grid|rotation|stock_selection|timing|swing` 明确指定范式来检查。

如果你已经写了策略代码，或者让 Codex 改过策略文件，回测前先做未来函数代码预检：

```bash
python3 cli.py student-future-leak-precheck --file path/to/strategy.py --session-id student001
```

也可以直接粘一小段代码：

```bash
python3 cli.py student-future-leak-precheck --code "signal = close.rolling(20).mean().shift(1)"
```

它会生成 `STUDENT_FUTURE_LEAK_PRECHECK.md/json`、`student_future_leak_cards.json` 和 `submitted_strategy.py`，检查负向 `shift`、`iloc[i+1]`、未来标签、居中 rolling、forward merge、危险导入/IO 等典型未来函数风险。显示 `LEAK_RISK_FOUND` 时不要回测，先按报告修复；显示 `LEAK_CHECK_VALID` 只代表静态预检没有发现 HIGH 风险，后面仍然必须经过完整 workflow 的 audit、模拟观察和 stage-check。

如果研究对象是内置 Core5 相对强弱网格包，并且要做固定池子的 walk-forward 验证，直接运行严格滚动回测入口：

```bash
python3 cli.py core5-walk-forward --out reports/core5_relative_strength_grid_package --starts 2018,2019,2020,2021
```

这个入口每个月只允许用调仓日及以前的数据选择参数和排序品种，持有期收益只能从下一期开始计算。结果目录会写出 `start_<年份>_decisions.csv`、`start_<年份>_walk_forward_audit.json` 和 `report.md`；如果窗口出现 `训练结束 > 调仓日` 或 `测试开始 <= 调仓日`，命令会直接返回 `WALK_FORWARD_INVALID`。

0基础学员优先使用：

```bash
python3 cli.py intake-chat --idea "我想做中国神华，周线布林低吸，涨回去卖，控制回撤，不要太频繁交易"
```

它会生成确认摘要。用户确认前，不会自动进入 Research Agent。

高级用户才使用 quick intake：

```bash
python3 cli.py intake --idea "我想做中国神华，周线布林低吸，涨回去卖，控制回撤，不要太频繁交易"
```

## 4. 运行 Research Agent

```bash
python3 cli.py research --direction "中国神华周线布林低吸波段，控制回撤" --symbol 601088.SH --timeframe 1w --adjust point_in_time_qfq
```

## 5. 一条命令跑完整新手工作流

如果你不知道现在应该从哪里继续，先跑学员启动包：

```bash
python3 cli.py student-start
```

它会运行学生版体检、学员控制台、学员名册，并在下一步命令安全时做一次 dry-run 预演，生成 `STUDENT_START.md/json` 和 `student_start_cards.json`。新手只看 `STUDENT_START.md` 的“当前结论”和“下一步”即可；这个命令不会真正执行研究重跑、不会连接 QMT、不会下单。

如果你只想看控制台，不想跑体检和预演，也可以运行：

```bash
python3 cli.py student-control-center
```

控制台会读取最新的学生工作流、回测假设卡、修复 DSL、promotion、QMT 准备度报告、模拟观察政策卡和 `STUDENT_POLICY_ACTION_PLAN.md/json`，生成 `STUDENT_CONTROL_CENTER.md/json` 和 `student_action_cards.json`。新手先看“下一步”和“回测假设卡”，确认策略范式、周期、数据要求和撮合假设，再看“模拟观察政策卡”和“模拟观察行动计划”；如果命令里有 `<...>` 占位符，就不能直接复制，需要先补齐参数。

如果是课堂、训练营或一台电脑上跑多个案例，建议每个学员/案例固定一个 session id：

```bash
python3 cli.py student-workflow --idea "中国神华周线布林低吸，控制回撤，不要太频繁交易" --timeframe 1w --adjust point_in_time_qfq --auto-refine --session-id student001 --case-id shenhua-weekly-boll
python3 cli.py student-start --session-id student001
```

`--session-id` 会写入 `workflow_manifest.json`、修复 DSL、执行账本和复盘报告。之后 `student-start`、`student-control-center`、`student-run-next`、`student-safe-loop`、`student-session-report` 都可以带同一个 `--session-id`，避免测试/演示报告或其他学员报告混进来。

老师想查看当前机器上有哪些学员或案例时，运行：

```bash
python3 cli.py student-session-index
```

它会生成 `STUDENT_SESSION_INDEX.md/json` 和 `student_session_cards.json`，列出每个 session 的最新工作流、当前阶段、回测假设卡状态/策略范式/周期、模拟观察政策卡状态/失败项、失败项修复提示、执行器允许/拒绝次数、风险提示和下一条控制台命令。这个命令只读报告和账本，不会回测、不会连接 QMT、不会下单。

如果你要复盘指定学员或指定案例，不想被测试/演示生成的最新 reports 干扰，可以手动指定报告：

```bash
python3 cli.py student-control-center --workflow reports/<student_workflow_run> --qmt-dashboard reports/<qmt_readiness_dashboard_run>
```

显式传入某个 `--workflow` 时，控制中心只会自动读取这个 workflow 对应的回测假设卡和模拟观察政策卡；不会把其他案例的最新 promotion 或 QMT dashboard 混进来，除非你同时显式传入这些报告，或者它们属于同一个 `--session-id`。

如果 workflow 已经生成 `STUDENT_POLICY_ACTION_PLAN.md/json`，控制台会进入 `POLICY_ACTION_PLAN_READY`，把其中的下一轮 `student-workflow` 研究命令作为安全下一步。你可以先用 `student-run-next --dry-run` 预演；这只会预演研究命令，不会执行 QMT、盘前或下单相关动作。

如果控制台显示 `safe_to_copy: True`，可以让系统执行这条安全下一步：

```bash
python3 cli.py student-run-next --workflow reports/<student_workflow_run> --dry-run
```

先加 `--dry-run` 只做安全检查；去掉 `--dry-run` 才会真正执行。`student-run-next` 只允许执行研究修复、QMT 只读、阶段检查和 dashboard 这类白名单命令；不会执行 QMT 交接、pretrade、沙盒或任何真实委托相关命令。每次运行都会生成 `STUDENT_NEXT_STEP_RUN.md/json`、`execution_decision.json`，并向 `reports/student_session_ledger.jsonl` 追加一条审计记录，方便老师回看学员每一步是被允许、被拒绝，还是只做了 dry-run。

老师复盘学员操作记录时，运行：

```bash
python3 cli.py student-session-report --limit 20 --session-id student001
```

它会生成 `STUDENT_SESSION_REPORT.md/json`，汇总最近步骤、允许/拒绝次数、dry-run 次数和风险提示。

课堂结束或助教要给学员一个集中入口时，生成交付包：

```bash
python3 cli.py student-handoff-pack --session-id student001
```

它会生成 `STUDENT_HANDOFF_PACK.md/json` 和 `student_handoff_cards.json`，集中放置当前阶段、下一步命令、报告入口、学员检查清单、执行复盘和产品化体检提醒。这个命令只读报告，不会执行研究、不会连接 QMT、不会 pretrade、不会下单。

如果你希望系统把“控制台 -> 安全下一步 -> session 复盘”串起来，先用安全循环预演：

```bash
python3 cli.py student-safe-loop --workflow reports/<student_workflow_run> --max-steps 3 --session-id student001
```

默认不执行，只生成 `STUDENT_SAFE_LOOP.md/json` 展示下一步会做什么。只有明确加 `--execute` 才会连续执行白名单里的安全研究/只读命令；每一步都会先预演，再执行。遇到任何阻断、占位符、非白名单命令，或者下一步命令与本轮已经执行过的命令重复，都会停下。

```bash
python3 cli.py student-workflow --idea "中国神华周线布林低吸，控制回撤，不要太频繁交易" --timeframe 1w --adjust point_in_time_qfq --auto-refine
```

这个命令会自动跑 intake、选择默认策略、数据准备、回测、审计、模拟盘观察和阶段检查，并生成 `workflow_manifest.json`、`STUDENT_WORKFLOW_SUMMARY.md`、`NEXT_ACTIONS.md`、`STUDENT_ACCEPTANCE_CHECKLIST.md`、`STUDENT_DIAGNOSTICS.md`、`BACKTEST_ASSUMPTION_CARD.md/json` 与 `STUDENT_POLICY_ACTION_PLAN.md/json`。`BACKTEST_ASSUMPTION_CARD.md` 会说明本次策略范式、周期、数据要求、撮合假设、A 股规则和推进边界；日内、网格、轮动、选股不会共用同一套假设。`STUDENT_POLICY_ACTION_PLAN.md` 会把模拟观察政策卡的失败项翻译成下一轮研究动作和安全重跑命令。如果诊断发现观察期够但信号太少，`--auto-refine` 还会生成 `STUDENT_EXPERIMENTS.md`，自动跑少量候选实验、排序，并给出下一轮命令。候选会同时包含参数微调和策略范式切换，例如从布林低吸切到均线或网格；若候选收益为负，报告会分析完整买卖回合、胜率、亏损和费用占比，并生成下一轮修复动作，例如趋势过滤、二次确认、冷却期和风险收紧。报告会标明这些动作是已由当前代码执行、组件可用但需编译实现，还是仅为研究假设。对组件可用的修复动作，系统会额外生成 `STUDENT_REPAIR_DSL.md`、`STUDENT_REPAIR_DSL.yaml` 和 `STUDENT_REPAIR_DSL.json`，作为下一轮编译策略研究分支；`STUDENT_REPAIR_DSL.md` 里会直接给出 `repair-dsl-backtest` 命令。
`--auto-refine` 会在第一轮被规则拦住后，自动补一版更完整的想法再跑一次。它只补研究约束，不会绕过未来函数、模拟盘或 QMT 阶段门。
如果想法里有“中国神华、神华、红利ETF”等名称，系统会自动解析成标准代码。
如果没有传 `--data`，系统会自动准备本地样例数据或读取已有缓存。

当前自动策略选择支持布林低吸、均线趋势、红利回撤和单标的网格。网格虽然可以跑，但模拟盘观察门槛更高，成交不足时会停在模拟盘阶段。

如果要复跑某个候选实验，可以使用报告里的 `--strategy-params` 命令，例如：

```bash
python3 cli.py student-workflow --idea "中国神华日线布林低吸波段，控制回撤" --symbol 601088.SH --strategy boll_mean_reversion --strategy-params '{"window":15,"num_std":1.8,"stop_loss":0.08}' --timeframe 1d --adjust point_in_time_qfq --auto-refine
```

## 6. 运行修复 DSL 分支

如果 `STUDENT_REPAIR_DSL.md` 存在，先打开它，复制里面的命令。命令形如：

```bash
python3 cli.py repair-dsl-backtest --dsl reports/<workflow_run>/STUDENT_REPAIR_DSL.yaml --symbol 601088.SH --timeframe 1d --adjust point_in_time_qfq --paper-observation --stage-check --auto-repair
```

它会重新生成 `compile_report.md`、`compiled_strategy.json`、`audit_report.md`、`future_leak_report.md`、`readiness_report.md`、`paper_observation_report.md`、`stage_gate_report.md`、`repair_dsl_run_report.md` 和 `repair_dsl_next_actions.md`。只有这条分支重新跑完并且审计 `VALID`，修复动作才算有第一层证据；如果成交次数为 0 或模拟盘不过，先看 `repair_dsl_next_actions.md` 调整 DSL，不要推进 QMT。启用 `--auto-repair` 后，系统还会生成 `repair_dsl_auto_repair.md/json`，自动尝试几条保守的小步修订并排序。若排名靠前候选已经 `audit_status: VALID`、`paper_status: VALID` 且成交数达标，系统会额外生成 `REPAIR_DSL_PROMOTION.md/json` 和 `promotion_candidate/`，集中放置 `SELECTED_REPAIR_DSL.yaml`、关键报告、`qmt_next_command` 和 QMT 后的 `stage_check_after_qmt_command`。

## 7. 手动运行回测

```bash
python3 cli.py backtest --strategy boll_mean_reversion --symbol 601088.SH --timeframe 1w --adjust point_in_time_qfq
```

## 8. 运行审计和阶段检查

```bash
python3 cli.py audit --run-id latest
python3 cli.py stage-check --run-id latest --plan-run-id <intake_run_id>
```

`stage-check` 会告诉你现在最多走到哪个阶段，以及为什么不能继续往后推。

## 9. 运行模拟盘观察

```bash
python3 cli.py paper --strategy boll_mean_reversion --symbol 601088.SH --timeframe 1w --adjust point_in_time_qfq --plan-run-id <intake_run_id>
python3 cli.py stage-check --run-id latest --plan-run-id <intake_run_id>
```

模拟盘会根据 `backtest_plan.yaml` 里的策略范式和周期选择观察标准。日内、网格、轮动、选股不会共用同一套门槛。除了观察期、成交次数和回撤，还会检查完整买卖回合是否足够、模拟委托拒单率是否过高，并生成 `paper_observation_policy_card.json` 给学员解释每一项 PASS/FAIL。模拟盘通过只代表可以继续做 QMT 只读检查，不代表允许真实下单。

## 10. QMT 只读检查

```bash
python3 cli.py qmt-config-status
python3 cli.py qmt-check
python3 cli.py stage-check --run-id <paper_run_id> --plan-run-id <intake_run_id> --qmt-run-id <qmt_run_id>
```

`qmt-config-status` 只读本地配置，不连接 QMT。它确认账号、miniQMT 路径和安全开关后，才建议运行 `qmt-check`。QMT 只读检查只读取连接、账户、资金、持仓、当日委托和当日成交，不做真实下单。

如果来自 `REPAIR_DSL_PROMOTION.md` 的候选已经完成 QMT 只读检查，先生成实盘前证据包：

```bash
python3 cli.py pretrade-package --promotion reports/<repair_run>/REPAIR_DSL_PROMOTION.json --qmt-run-id <qmt_run_id>
```

它会汇总选中 DSL、审计、模拟盘、阶段门、QMT 只读和 pretrade 阻断项，并生成逐项 `修复清单` 和 `PRETRADE_RUNBOOK.md`。证据包通过也不代表可以下单，只代表可以继续看 `pretrade-check` 还缺哪些安全项。`dry_run`、`enable_real_trade` 和 `CONFIRM_REAL_TRADE` 都是人工安全边界，不能为了让报告变绿而自动改掉。Runbook 会统计 `pending`、`blocked` 和 `verified`；凡是标记为 `stop_trading: True` 或 `status: blocked` 的事项，当天停止推进实盘。

修完 QMT、行情、标的状态或风控配置后，不需要重做整份证据包，可以复查清单：

```bash
python3 cli.py pretrade-runbook-refresh --package reports/<pretrade_package_run> --qmt-run-id <qmt_run_id>
```

它会生成 `PRETRADE_RUNBOOK_REFRESH.md/json`，把本次仍存在的阻断项保持为 `pending` 或 `blocked`，把旧清单里本次已经消失的事项标成 `verified`。`verified` 只说明该阻断项解除，不是下单许可。

## 11. 实盘前检查

```bash
python3 cli.py pretrade-check --strategy boll_mean_reversion --symbol 601088.SH --run-id <paper_run_id> --plan-run-id <intake_run_id> --qmt-run-id <qmt_run_id>
```

即使输入人工确认，只要阶段、QMT、风控或交易安全项未满足，系统仍会返回 `INVALID`。

## 12. QMT 订单交接草案

如果不确定当前卡在哪一步，先生成 QMT 准备度总览：

```bash
python3 cli.py qmt-readiness-dashboard
```

它会自动读取最新的 `PRETRADE_READINESS_PACKAGE.json`、`PRETRADE_RUNBOOK_REFRESH.json`、单笔/批量交接向导和日终复盘报告，生成 `QMT_READINESS_DASHBOARD.md/json`、`QMT_NEXT_ACTIONS.md`、`qmt_action_cards.json` 和 `qmt_blocker_checklist.json`。新手先看 `QMT_NEXT_ACTIONS.md`：它只回答当前卡点、先处理哪个阻断、下一条命令能不能直接复制。它不会连接 QMT，不会发送委托；`DRY_RUN_ONLY` 只代表继续沙盒演练，不代表实盘许可。

新手优先使用单笔交接向导，它会按顺序串起订单草案、沙盒、生命周期追踪和日终复盘：

```bash
python3 cli.py qmt-handoff-wizard --package reports/<pretrade_package_run> --action BUY --quantity 100 --price 25.5 --signal-time 2026-06-29T09:35:00 --execute-time 2026-06-30T09:35:00 --trade-date 2026-06-29 --reason "manual_reviewed_signal"
```

它会生成 `QMT_HANDOFF_WIZARD.md/json`。向导只减少 run id 复制，不跳过任何门；如果 `qmt-handoff`、`qmt-order-sandbox`、`qmt-order-lifecycle` 或 `qmt-daily-review` 任一步阻断，向导会停在对应阶段。

只有盘前证据包、Runbook 复查和 `pretrade-check` 都没有阻断项时，才生成订单交接草案：

```bash
python3 cli.py qmt-handoff --package reports/<pretrade_package_run> --action BUY --quantity 100 --price 25.5 --signal-time 2026-06-29T09:35:00 --execute-time 2026-06-30T09:35:00 --reason "manual_reviewed_signal"
```

它会生成 `QMT_HANDOFF_PACKAGE.md/json` 和 `order_draft.csv/json`。这个命令不调用 QMT broker，不发送委托，只把“拟下什么单、为什么、哪些条件仍阻断”写成可复核证据。买入数量不是 100 股整数倍、执行时间不晚于信号时间、盘前包未通过、存在 `stop_trading` 事项时，都会停在 `BLOCKED_DRAFT_ONLY`。

如果是轮动、组合或多笔调仓，先准备批量订单 CSV，字段为：

```text
symbol,action,quantity,price,signal_time,execute_time,reason
```

新手优先使用批量交接向导：

```bash
python3 cli.py qmt-batch-handoff-wizard --package reports/<pretrade_package_run> --orders batch_orders.csv --trade-date 2026-06-29
```

它会生成 `QMT_BATCH_HANDOFF_WIZARD.md/json`，自动串起 `qmt-batch-handoff -> qmt-batch-sandbox -> qmt-batch-lifecycle -> qmt-batch-daily-review`。向导只减少 run id 复制，不跳过任何门；任一步阻断，整批停在对应阶段。

然后生成批量交接草案：

```bash
python3 cli.py qmt-batch-handoff --package reports/<pretrade_package_run> --orders batch_orders.csv
```

它会生成 `QMT_BATCH_HANDOFF_PACKAGE.md/json` 和 `batch_order_drafts.csv`。任意一笔订单存在手数、方向、时间或盘前证据阻断时，整批都会停在 `BATCH_BLOCKED_DRAFT_ONLY`，不能进入沙盒或真实委托。

批量交接草案没有阻断后，进入批量沙盒：

```bash
python3 cli.py qmt-batch-sandbox --batch-handoff reports/<qmt_batch_handoff_run>
```

它会生成 `QMT_BATCH_ORDER_SANDBOX.md/json` 和 `batch_order_receipts.csv`。这个命令只生成批量 dry-run 回执，不连接真实 QMT，不发送真实委托；如果批量交接包不是 `BATCH_DRAFT_READY`，或者配置里 `dry_run=false` / `enable_real_trade=true`，整批都会停在 `BATCH_BLOCKED_SANDBOX_ONLY`。

批量沙盒之后，使用 QMT 只读快照逐笔追踪：

```bash
python3 cli.py qmt-batch-lifecycle --batch-sandbox reports/<qmt_batch_sandbox_run> --qmt-run-id <qmt_run_id>
```

它会生成 `QMT_BATCH_ORDER_LIFECYCLE.md/json` 和 `batch_lifecycle_timeline.csv`。状态包括 `BATCH_DRY_RUN_ONLY`、`BATCH_ORDER_OBSERVED`、`BATCH_TRADE_OBSERVED`、`BATCH_PARTIAL_OBSERVED` 和 `BATCH_BLOCKED_NO_TRACKING`。这些都是证据状态，不是交易许可。

批量交易日结束后生成批量日终复盘：

```bash
python3 cli.py qmt-batch-daily-review --batch-lifecycle reports/<qmt_batch_lifecycle_run> --trade-date 2026-06-29 --notes "人工备注"
```

它会生成 `QMT_BATCH_DAILY_REVIEW.md/json` 和 `batch_next_day_actions.csv`，把整批状态和逐笔状态转成下一日动作边界：整批阻断则先修上游证据，只有 dry-run 则继续批量沙盒，部分观察则逐笔对账，成交观察则先复核持仓、成交价和组合风险敞口。

交接草案没有阻断后，先进入 QMT 订单沙盒，记录 dry-run 回执：

```bash
python3 cli.py qmt-order-sandbox --handoff reports/<qmt_handoff_run>
```

它会生成 `QMT_ORDER_SANDBOX.md/json` 和 `order_receipt.json`。这个命令只使用 dry-run stub，不连接真实 QMT，不发送真实委托；即使输入 `CONFIRM_REAL_TRADE` 也只会记录为 `confirmation_ignored: true`。如果配置里 `dry_run=false` 或 `enable_real_trade=true`，沙盒会直接阻断，因为沙盒阶段必须保持安全配置。

沙盒回执生成后，可以做订单生命周期追踪：

```bash
python3 cli.py qmt-order-lifecycle --sandbox reports/<qmt_order_sandbox_run> --qmt-run-id <qmt_run_id>
```

它会生成 `QMT_ORDER_LIFECYCLE.md/json` 和 `lifecycle_timeline.json`。如果没有传 QMT 只读快照，会停在 `DRY_RUN_ONLY`；如果最新只读快照里观察到对应委托，会显示 `ORDER_OBSERVED`；如果观察到对应成交，会显示 `TRADE_OBSERVED`。这个命令只读取 QMT 快照，不发送、撤销或修改任何委托。

交易日结束后生成日终复盘包：

```bash
python3 cli.py qmt-daily-review --lifecycle reports/<qmt_order_lifecycle_run> --trade-date 2026-06-29 --notes "人工备注"
```

它会生成 `QMT_DAILY_REVIEW.md/json` 和 `next_day_actions.json`，把当天状态转成下一日边界：上游阻断则 `STOP_UNTIL_UPSTREAM_FIXED`，只有 dry-run 则 `CONTINUE_DRY_RUN_ONLY`，观察到委托但未成交则先复核委托状态，观察到成交则先复核持仓、成交价和风险敞口。日终复盘不是新的交易许可。

## 12. 使用 Codex Skill 跑新手流程

先安装项目自带的 Skill：

```bash
python3 scripts/install_astock_skill.py --force
```

安装后，在 Codex 里可以直接要求使用 `$astock-quant-research`，或者运行本地 helper：

```bash
python3 ~/.codex/skills/astock-quant-research/scripts/run_astock_workflow.py --idea "中国神华周线布林低吸，控制回撤，不要太频繁交易" --timeframe 1w --adjust point_in_time_qfq --auto-refine
```

这条命令会自动解析标的、选择默认策略、准备数据，并生成 `NEXT_ACTIONS.md`。

## 13. 运行反馈优化闭环

```bash
python3 cli.py optimize-loop --idea "中国神华周线布林低吸波段，控制回撤，不要太频繁交易" --symbol 601088.SH --timeframe 1w --adjust point_in_time_qfq --max-iterations 3
```

## 14. 生成解释报告

```bash
python3 cli.py explain-report --run-id latest
```

## 15. 一键课程演示

```bash
python3 cli.py course-demo
```

## 读报告顺序

优先看：

1. `README_本次研究.md`
2. `audit_report.md`
3. `readiness_report.md`
4. `paper_observation_report.md`
5. `paper_observation_policy_card.json`
6. `stage_gate_report.md`
7. `workflow_manifest.json`
8. `BACKTEST_ASSUMPTION_CARD.md`
9. `STUDENT_START.md`
10. `STUDENT_CONTROL_CENTER.md`
11. `student_action_cards.json`
12. `STUDENT_WORKFLOW_SUMMARY.md`
13. `NEXT_ACTIONS.md`
14. `STUDENT_ACCEPTANCE_CHECKLIST.md`
15. `STUDENT_DIAGNOSTICS.md`
16. `STUDENT_POLICY_ACTION_PLAN.md`
17. `STUDENT_EXPERIMENTS.md`
18. `STUDENT_REPAIR_DSL.md`
19. `qmt_readonly_report.md`
20. `PRETRADE_READINESS_PACKAGE.md`
21. `PRETRADE_RUNBOOK.md`
22. `PRETRADE_RUNBOOK_REFRESH.md`
23. `QMT_READINESS_DASHBOARD.md`
20. `QMT_NEXT_ACTIONS.md`
21. `qmt_action_cards.json`
22. `qmt_blocker_checklist.json`
23. `QMT_HANDOFF_PACKAGE.md`
24. `order_draft.csv`
25. `QMT_HANDOFF_WIZARD.md`
26. `QMT_BATCH_HANDOFF_PACKAGE.md`
27. `batch_order_drafts.csv`
28. `QMT_BATCH_HANDOFF_WIZARD.md`
29. `QMT_BATCH_ORDER_SANDBOX.md`
30. `batch_order_receipts.csv`
31. `QMT_BATCH_ORDER_LIFECYCLE.md`
32. `batch_lifecycle_timeline.csv`
33. `QMT_BATCH_DAILY_REVIEW.md`
34. `batch_next_day_actions.csv`
35. `QMT_ORDER_SANDBOX.md`
36. `order_receipt.json`
37. `QMT_ORDER_LIFECYCLE.md`
38. `lifecycle_timeline.json`
39. `QMT_DAILY_REVIEW.md`
40. `next_day_actions.json`
41. `performance.json`
42. `final_feedback_loop_report.md`
43. `explain_report.md`

看到 `INVALID` 时，不要进入模拟盘或实盘。
