# V8.2 Adaptive Research Intake Completion Report

## 当前完成内容

V8.2 新增 Adaptive Research Intake Agent，将小白用户入口从“一次性 quick intake”升级为“自适应澄清问答”。

新增入口：

```bash
python3 cli.py intake-chat
python3 cli.py intake-chat --idea "我想做中国神华，跌多了买，涨回去卖，控制回撤"
```

旧入口仍保留：

```bash
python3 cli.py intake --idea "..."
```

## 新增模块

- intake/adaptive/adaptive_interview_agent.py
- intake/adaptive/question_tree.py
- intake/adaptive/interview_state.py
- intake/adaptive/conversation_memory.py
- intake/adaptive/requirement_builder.py
- intake/adaptive/research_readiness_checker.py
- intake/adaptive/answer_parser.py
- intake/adaptive/clarification_policy.py
- intake/adaptive/adaptive_intake_report.py

## 关键行为

- 模糊想法不会直接进入 Research Agent；
- 未确认前 `research_ready=false`；
- 系统会根据策略范式动态追问；
- 网格不会追问布林线；
- 轮动不会追问单标的出场；
- QMT / 实盘意图只触发风险提醒；
- 输出 StrategyRequirement、Strategy DSL、确认摘要和未回答问题。

## 验收命令

已通过：

```bash
python3 cli.py intake-chat --idea "我想做中国神华，跌多了买，涨回去卖，控制回撤"
```

输出会提示：

- “跌多了”如何量化；
- 使用什么周期；
- 每次买多少；
- 是否只是研究/模拟盘/未来 QMT。

已通过：

```bash
python3 cli.py intake --idea "我想做中国神华，跌多了买，涨回去卖，控制回撤"
```

## 文档更新

- README.md 已加入 intake-chat；
- QUICK_START_FOR_STUDENTS.md 已加入 intake-chat；
- COURSE_DELIVERY_PLAN.md 已改为 Adaptive Intake 教学入口；
- docs/architecture/adaptive_research_intake_agent.md 已新增。

## 测试

新增 V8.2 测试：31 个。

覆盖：

- CLI 启动；
- 标的识别；
- 动态问题树；
- 周期解析；
- 风险偏好；
- 仓位解析；
- QMT 风险提醒；
- research_ready 确认机制；
- 输出文件；
- 旧 intake 保留；
- 文档更新。

## 当前限制

当前 intake-chat 是“单轮生成下一步问题 + 状态文件”的课程版实现，还不是持久化多轮终端聊天。多轮状态续接可作为后续小功能，但不影响当前课程第一入口的正确性。
