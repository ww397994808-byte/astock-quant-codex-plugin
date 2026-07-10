# Pre-Delivery Checklist

## 结论

当前 V8 可以进入录课准备和小范围内测，但建议在正式发给学员前更新 README 第一屏，把 `course-demo` 和 `QUICK_START_FOR_STUDENTS.md` 放到最明显位置。

## 检查项

| 检查项 | 状态 | 说明 |
|---|---|---|
| 新手是否能从 README 找到入口 | 部分通过 | README 有快速开始，但仍是旧命令优先；建议把 `python3 cli.py course-demo` 放到第一条。 |
| QUICK_START 是否能一步步跑通 | 通过 | 已覆盖 generate-sample-data、intake、research、backtest、optimize-loop、explain-report。 |
| requirements 是否足够 | 通过 | 课程版依赖轻，当前需要 PyYAML 和 pytest。 |
| Mac / Windows 路径是否有说明 | 部分通过 | 当前命令以 macOS/Linux shell 为主，Windows 用户需说明使用 PowerShell 和 `python` 替代 `python3`。 |
| 是否有中文错误提示 | 通过 | CLI、数据校验、QMT 检查均有中文提示。 |
| course-demo 是否稳定 | 通过 | 已实际运行成功。 |
| sample data 是否自动生成 | 通过 | generate-sample-data 和 course-demo 均会自动生成。 |
| 失败时用户知道怎么办 | 部分通过 | INVALID 会显示原因；建议课程中补充“遇到错误先运行 doctor/course-demo”。 |
| QMT 未连接时是否不会误导 | 通过 | qmt-check 返回 INVALID，并明确 dry_run=True、未连接 QMT。 |
| 实盘默认关闭是否明确 | 通过 | README、SYSTEM_RISK_BOUNDARIES、QMT README 均明确。 |

## 录课前建议修正

1. README 第一屏改成课程入口：

```bash
python3 cli.py course-demo
```

2. README 增加 Windows 说明：

```powershell
python cli.py course-demo
```

3. 第一节课明确：看到 `INVALID` 是保护，不是系统坏了。

## 是否阻塞录课

不阻塞。上述问题属于说明和呈现优化，不是系统功能阻塞。
