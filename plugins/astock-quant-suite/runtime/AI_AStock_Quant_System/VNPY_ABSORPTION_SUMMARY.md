# VNPY Absorption Summary

## 1. 该不该直接用 vn.py

不建议直接用 vn.py 接管本项目。

vn.py 很成熟，但本项目已经有自己的 Intake、Research、Backtest Template、Audit、Readiness、Data Quality、Point-in-Time 复权和 QMT Safety。直接接管会把 0 基础课程链路变重，也可能绕开本项目最重要的审计和安全门。

## 2. 应该吸收 vn.py 哪些设计

- EventEngine 的事件解耦思想；
- Gateway/Broker 生命周期；
- OrderData / TradeData / PositionData 字段语义；
- CTA 策略生命周期和参数/变量管理；
- Gateway 回调模型：on_order、on_trade、on_position、on_account。

## 3. vnpy_qmt 能不能直接拿来

不建议直接拿来作为实盘核心。

它可以参考 QMT Gateway 结构和 miniQMT 连接方式，但真实下单仍必须走本项目：

- pre_trade_check；
- readiness；
- audit；
- dry_run；
- CONFIRM_REAL_TRADE；
- QMTBroker 内部 safety gate。

## 4. 如何让本项目未来兼容 vn.py Gateway

当前已新增：

- `integrations/vnpy/vnpy_event_adapter.py`
- `integrations/vnpy/vnpy_order_mapper.py`
- `integrations/vnpy/vnpy_mapping.md`
- `integrations/vnpy/vnpy_gateway_reference.md`
- `integrations/vnpy/vnpy_qmt_reference.md`

下一步建议：

1. 为 `Order` / `Trade` 增加本地 `order_id` / `trade_id`；
2. 为 `PositionBook` 增加 frozen / yd_volume 标准输出；
3. 为 `QMTBroker` 增加 on_order / on_trade / on_position 回调；
4. 等 QMT dry_run 联调稳定后，再考虑正式 GatewayAdapterBase。

