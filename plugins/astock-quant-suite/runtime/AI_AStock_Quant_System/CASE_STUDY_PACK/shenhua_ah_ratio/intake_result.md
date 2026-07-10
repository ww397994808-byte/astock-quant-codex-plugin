# Intake Result

预期识别：

- market: A股 / 港股对照研究
- symbols: 601088.SH, 01088.HK
- pattern: pair_trading
- timeframe: 1d
- data_required: A/H OHLCV, HKD/CNY 汇率, point-in-time 复权/分红
- live_intent: 禁止直接进入 QMT

这个案例应被标记为 `RESEARCH_ONLY` 或 `BLOCKER`，因为 A/H 比例研究涉及港股交易、汇率、融券/做空约束、交易时段差和分红复权问题。

示例命令：

```bash
python3 cli.py intake --idea "研究中国神华 A/H 比例，低比例买 A，高比例卖出，未来想评估能否实盘"
```
