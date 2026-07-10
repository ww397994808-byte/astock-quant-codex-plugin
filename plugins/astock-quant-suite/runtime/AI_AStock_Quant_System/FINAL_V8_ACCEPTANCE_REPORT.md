# Final V8 Acceptance Report

## 当前系统成熟度

当前系统已达到“课程产品底座”成熟度：可让 0 基础用户通过 CLI 跑通从想法到研究、回测、优化、审计、解释报告的完整流程。

成熟链路：

```text
Intake -> DSL -> Research -> Backtest -> Feedback Loop -> Batch Experiments -> Weekly/Intraday -> Regime Slice -> Audit/Readiness
```

## 能作为课程卖点的功能

- 自然语言策略 Intake；
- Strategy DSL；
- A股交易规则代码化；
- 回测计划/策略范式/数据周期前置预检；
- 未来函数和交易规则审计；
- 学员代码未来函数前置预检；
- Core5 严格 walk-forward 回测和逐月窗口审计；
- point-in-time qfq 风险控制；
- 日线、周线、日内周期；
- 回测后反馈优化闭环；
- 批量实验；
- Regime slice；
- Readiness 分类；
- 一键 course-demo；
- student-course-path 0基础课程路线包；
- student-research-contract 研究假设契约；
- student-contract-check 研究契约对账；
- student-product-audit 动态交付体检；
- 0基础解释报告。

## 暂不能承诺的功能

- 真实 QMT 自动交易；
- 真实行情供应商稳定接入；
- 真实多账户、多策略生产运维；
- 真实事件驱动数据；
- 市场中性配对交易；
- 收益承诺。

## 真实 QMT 接入前必须做什么

1. 准备真实 MiniQMT / XtQuant 环境；
2. 完成 qmt_config.yaml 本地配置；
3. 接通 xtdata / xttrader；
4. 完成 dry-run 对账；
5. 完成真实账户只读同步；
6. 完成模拟盘至少数周观察；
7. 完成异常订单、重复下单、断线、撤单风控；
8. 小资金灰度；
9. 人工复核每个策略；
10. 保持真实下单二次确认。

## V8 验收命令

```bash
python3 cli.py course-demo
python3 cli.py core5-walk-forward --n-random 1 --starts 2021 --out reports/core5_walk_forward_smoke
python3 cli.py student-product-audit
python3 -m pytest tests/
```

## 结论

V8 版本适合作为课程交付基线。课程主线应强调“研究流程、审计意识、规则代码化、风险边界”，而不是承诺自动赚钱或直接实盘。
