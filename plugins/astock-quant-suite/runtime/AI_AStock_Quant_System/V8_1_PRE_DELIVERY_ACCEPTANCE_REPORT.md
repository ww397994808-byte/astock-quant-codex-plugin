# V8.1 Pre-Delivery Acceptance Report

## 是否建议进入录课

建议进入录课。

理由：

- `course-demo` 已能一键跑通；
- Quick Start 已覆盖第一天核心路径；
- QMT 未连接时会明确 INVALID 和 dry_run；
- 实盘默认关闭；
- 课程案例包和风险边界文档已齐备；
- 全量测试通过。

## 是否建议开放内测

建议开放 1-3 名小白用户小范围内测。

内测目标不是验证收益，而是验证：

- 是否能安装依赖；
- 是否能运行 course-demo；
- 是否能找到 report_path；
- 是否理解 INVALID；
- 是否能读懂 Quick Start；
- 是否会误解 QMT / 实盘能力。

## 内测前必须修的问题

不阻塞，但建议修：

1. README 第一屏加入 `python3 cli.py course-demo`；
2. README 加 Windows PowerShell 命令说明；
3. README 增加“看到 INVALID 先看原因”的说明；
4. 录课资料中明确 sample data 不是市场数据。

## 录课时应该强调的风险边界

- 不是投资建议；
- 回测不等于实盘；
- sample data 仅用于教学；
- qfq/hfq 有未来函数风险；
- QMT 真实交易默认关闭；
- LIVE_CANDIDATE 不等于直接实盘；
- 所有策略必须先模拟盘；
- AI 不能绕过风控下单。

## 验收命令

已执行：

```bash
python3 cli.py course-demo
```

已执行：

```bash
python3 -m pytest tests/
```

## 最终建议

冻结当前课程基线，进入录制第一个 course-demo 视频。录完后找 1-3 个 0 基础用户试跑，记录真实卡点，再决定 V9 做什么。
