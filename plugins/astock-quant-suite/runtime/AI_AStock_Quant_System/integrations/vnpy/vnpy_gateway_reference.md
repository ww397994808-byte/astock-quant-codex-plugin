# vn.py Gateway Reference

vn.py Gateway 的核心价值是把不同交易接口统一成同一组语义：

- connect
- subscribe
- send_order
- cancel_order
- query_account
- query_position
- on_order
- on_trade
- on_position
- on_account

本项目当前 `BrokerBase` 已有：

- connect
- get_account
- get_positions
- get_cash
- get_orders
- get_trades
- place_order
- cancel_order
- sync_positions

差距：

1. 缺少订阅/行情回调；
2. 缺少 order_id / trade_id 生命周期；
3. 缺少统一 event push；
4. 实盘异常委托回报处理还很薄；
5. QMT 状态同步应更接近 Gateway 的 on_order/on_trade/on_position。

建议：未来新增 `GatewayAdapterBase`，但真实下单仍走 `QMTBroker` 安全门。

