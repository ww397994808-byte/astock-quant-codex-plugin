# QMT实盘前检查

```bash
python cli.py qmt-check
python cli.py pretrade-check --strategy boll_mean_reversion --symbol 601088.SH
```

真实下单默认关闭。没有 QMT 真实配置、审计 VALID、二次确认和全部风控通过时，系统只能 dry_run。

