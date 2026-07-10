# AI_AStock_Quant_System

A股 AI 量化研究、回测、参数优化、风控审计、模拟盘和 QMT 实盘安全骨架。

第一版目标是建立可教学、可审计、可复现的本地系统。实盘交易默认关闭，AI / Skill / Agent 只能通过 Task Layer 调用既有代码，不能绕过风控和审计直接下单。

## 快速开始

0基础学员优先使用一键课程演示：

```bash
python3 cli.py course-demo
```

如果你已经有一个模糊策略想法，先使用自适应 Intake：

```bash
python3 cli.py intake-chat --idea "我想做中国神华，跌多了买，涨回去卖，控制回撤"
```

高级用户可使用 quick intake：

```bash
python3 cli.py intake --idea "中国神华周线布林低吸，控制回撤"
```

```bash
python cli.py generate-sample-data
python cli.py backtest --strategy boll_mean_reversion --symbol 601088.SH --data data/sample/601088.csv
python cli.py optimize --strategy boll_mean_reversion --symbol 601088.SH --data data/sample/601088.csv
python cli.py audit --run-id latest
python cli.py paper --strategy boll_mean_reversion --symbol 601088.SH --data data/sample/601088.csv
python cli.py qmt-check
python cli.py pretrade-check --strategy boll_mean_reversion --symbol 601088.SH
pytest tests/
```

## 架构入口

```text
自然语言 -> Codex Skill -> Task Layer -> Service Layer -> Engine -> Broker -> XtQuant / MiniQMT
```

`cli.py` 只负责解析参数并调用 `tasks/`。业务逻辑放在 `services/`、`backtest/`、`audit/`、`core/`。

## 安全边界

- QMT 默认 `dry_run=True`。
- 仓库只提供 `config/qmt_config.example.yaml`。
- 真实配置只能放在 `config/qmt_config.yaml`，并被 `.gitignore` 排除。
- 真实下单必须通过 pre-trade check、审计 VALID、二次确认和 emergency stop 检查。
