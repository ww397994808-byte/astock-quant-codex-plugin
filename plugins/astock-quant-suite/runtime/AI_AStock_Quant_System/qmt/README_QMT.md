# QMT 安全说明

本目录只提供 QMT 官方 XtQuant / MiniQMT 适配骨架。

- 默认 `dry_run=True`。
- 不硬编码账号、密码、路径。
- 真实配置只能放在 `config/qmt_config.yaml`。
- 真实下单必须满足 enable_real_trade、dry_run=false、二次确认、审计 VALID、pre-trade check 全部通过、未触发 emergency_stop。

第三方 QMT Bridge、proxy、skill 只能参考，不能作为本系统实盘核心。

