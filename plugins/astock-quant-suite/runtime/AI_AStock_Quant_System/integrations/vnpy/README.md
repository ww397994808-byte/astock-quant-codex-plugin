# vn.py / VeighNa Integration Notes

本目录只做 vn.py 设计吸收和兼容映射，不直接依赖 vn.py，也不让 vn.py 接管本项目。

当前边界：

- 不安装 `vnpy`。
- 不把 `vnpy` 放入 `requirements.txt`。
- 不用 vn.py Gateway 绕过本项目风控。
- QMT 真实下单仍必须经过本项目的 `pre_trade_check`、readiness、audit、dry_run 和 `CONFIRM_REAL_TRADE`。

可吸收方向：

- EventEngine 的事件分发模型；
- Gateway/Broker 分层；
- OrderData / TradeData / PositionData 对象语义；
- CTA Strategy 生命周期；
- vnpy_qmt 的 QMT Gateway 结构作为参考。

