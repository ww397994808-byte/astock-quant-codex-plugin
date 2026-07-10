# Student First Day Script

## 老师开场讲什么

今天目标不是赚钱，也不是荐股，而是跑通一条完整的 A股 AI 量化研究链路：

```text
想法 -> Intake -> Research -> Backtest -> Optimize Loop -> Audit -> Explain Report
```

强调三件事：

1. 本系统是教学研究工具，不是投资建议；
2. 回测不等于实盘；
3. 所有策略必须先审计，再模拟盘，最后才可能讨论实盘。

## 学员输入命令

第一条命令：

```bash
python3 cli.py course-demo
```

Windows PowerShell：

```powershell
python cli.py course-demo
```

## 学员应该看到什么

终端应出现：

```text
课程演示已完成：Intake -> Research -> Backtest -> Optimize-loop -> Explain-report
status: VALID
report_path: reports/course_demo_xxx
```

打开 `report_path`，依次看：

1. `COURSE_DEMO_SUMMARY.md`
2. `01_intake/intake_report.md`
3. `02_research/final_research_report.md`
4. `03_backtest/audit_report.md`
5. `03_backtest/readiness_report.md`
6. `04_optimize_loop/final_feedback_loop_report.md`
7. `05_explain_report.md`

## 老师讲解顺序

1. Intake：系统如何把模糊想法变成结构化需求；
2. Research：系统如何选择策略范式；
3. Backtest：订单、成交、权益曲线；
4. Audit：为什么先看审计再看收益；
5. Optimize-loop：失败后如何诊断；
6. Readiness：为什么 RESEARCH_ONLY 不等于能实盘。

## 常见错误处理

### 找不到 python3

Windows 用户改用：

```powershell
python cli.py course-demo
```

### ModuleNotFoundError: yaml

运行：

```bash
pip install -r requirements.txt
```

### 出现 INVALID

先看 `INVALID 原因`。如果是 QMT 未连接，这是正常保护；课程第一天不需要连接 QMT。

### 找不到报告

终端会输出 `report_path`。进入该目录看 `COURSE_DEMO_SUMMARY.md`。

## 第一天下课前学生应掌握

- 能独立运行 course-demo；
- 知道 report_path 在哪里；
- 知道 VALID / INVALID 的含义；
- 知道回测不等于实盘；
- 知道 QMT 真实交易默认关闭。
