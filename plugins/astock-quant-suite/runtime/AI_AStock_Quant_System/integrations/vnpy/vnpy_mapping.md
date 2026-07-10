# vn.py Mapping

| vn.py 概念 | 本项目对应 | 差距 | 建议 |
|---|---|---|---|
| EventEngine | Task/Service 同步调用，新增 VnpyEventAdapter | 本项目缺少统一异步事件总线 | 先保留 adapter，QMT/paper 需要更多实时事件时再引入 |
| Gateway | `BrokerBase` / `QMTBroker` | 本项目 Gateway 生命周期、订阅、回调较轻 | 吸收 connect/query/order/cancel/callback 结构 |
| OrderData | `Order` / `orders.csv` | vn.py 有 traded/status/vt_orderid/exchange/offset | 通过 VnpyOrderMapper 做兼容映射 |
| TradeData | `Trade` / `trades.csv` | vn.py 有 tradeid/orderid/exchange/offset | 后续补本地 order_id/trade_id |
| PositionData | `PositionBook` / `Portfolio` | vn.py 区分 direction/yd_volume/frozen | A股 T+1 可映射到 yd_volume/frozen |
| CtaTemplate | `StrategyBase` + backtest template | vn.py 策略可直接委托，本项目策略只能输出 Signal | 不吸收直接下单，只吸收生命周期和参数/变量管理 |

