# Final Explanation

这个案例用于讲“研究线索不等于交易系统”。

中国神华 A/H 比例可能提供估值偏离线索，但要变成可执行策略，必须补齐汇率、分红复权、交易时段、港股流动性、融券或港股账户约束。当前版本只能作为研究案例，不能包装成 QMT 可执行策略。

系统应给出的最终状态：

```text
readiness: RESEARCH_ONLY
qmt_allowed: false
reason: A/H 配对/套利类策略第一阶段缺少可执行交易模板和 point-in-time 跨市场数据。
```
