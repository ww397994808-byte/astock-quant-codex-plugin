# vn.py / VeighNa 模块化吸收评估

调研对象：

- `vnpy/vnpy`
- `ruyisee/vnpy_qmt`
- `vnpy/vnpy_ctastrategy`

本报告只评估模块化吸收，不建议整体引入 vn.py，也不让 vn.py 接管当前项目。

## 1. vn.py 哪些模块值得吸收

### EventEngine

值得吸收事件驱动思想：行情、订单、成交、持仓、日志都通过事件分发，解耦 Gateway、策略、监控和 UI。

本项目目前 Task/Service/Engine 多为同步调用。对于回测和课程 CLI 足够，但未来模拟盘、QMT 实盘、监控和异常订单处理会需要事件流。

建议：先使用本项目新增的 `VnpyEventAdapter` 做轻量兼容，不引入 vn.py EventEngine 运行时。

### Gateway / Broker 设计

vn.py Gateway 把不同交易接口统一成 connect、subscribe、send_order、cancel_order、query、callback。这个结构非常适合未来 QMT、paper、remote bridge 的统一适配。

本项目应吸收 Gateway 生命周期和回调命名，但真实下单仍必须经过本项目 QMT Safety。

### OrderData / TradeData / PositionData

vn.py 数据对象比本项目当前对象更贴近实盘：

- OrderData 有 orderid、status、traded、exchange；
- TradeData 有 tradeid、orderid、direction、offset；
- PositionData 有 direction、volume、yd_volume、frozen。

本项目应补本地 order_id/trade_id，并把 A股 T+1 的 available_position 映射到 `yd_volume/frozen` 思路。

### CTA 策略模板

vn.py CTA 模板提供策略生命周期、参数、变量、信号生成和委托管理。值得吸收生命周期和参数管理。

但本项目不应吸收“策略直接委托”的方式。本项目策略仍只能输出 Signal / OrderIntent，执行必须通过 ExecutionEngine、RiskManager 和 Audit。

## 2. 哪些模块不适合本项目

1. 不适合整体引入 vn.py GUI/MainEngine 作为课程第一屏。
2. 不适合让 vn.py Gateway 直接真实下单。
3. 不适合引入 CTA 策略直接 send_order 的模式。
4. 不适合用 vn.py 回测替代本项目 A股 T+1、涨跌停、复权审计和 Readiness。
5. 不适合把 vnpy_qmt 作为唯一 QMT 实盘核心。

## 3. 当前 BrokerBase / QMTBroker / ExecutionEngine 和 vn.py Gateway 的差距

当前差距：

- 缺少事件回调：on_order、on_trade、on_position、on_account；
- 缺少行情订阅：subscribe / on_tick / on_bar；
- 缺少 order_id / trade_id 生命周期；
- 缺少委托状态机：SUBMITTING、NOTTRADED、PARTTRADED、ALLTRADED、CANCELLED、REJECTED；
- 缺少异步异常订单处理；
- `QMTBroker.place_order` 当前还是安全骨架，未完成真实 xttrader send_order。

保留优势：

- 本项目已有 pre_trade_check、readiness、audit、dry_run、CONFIRM_REAL_TRADE；
- 本项目 A股规则、复权未来函数、Data Quality、Research Agent 已代码化；
- 本项目更适合课程和 0 基础用户。

## 4. 当前 OrderIntent / Portfolio / Position 和 vn.py 数据对象的差距

`OrderIntent` 是研究意图，不等于实盘 OrderData。它缺少 orderid、exchange、offset、status、traded。

`Portfolio` 更偏回测账户，缺少多方向、多账户、多冻结字段。

`PositionBook` 已适合 A股 T+1 lot 管理，但和 vn.py PositionData 相比，缺少：

- exchange；
- direction；
- frozen；
- yd_volume 标准字段；
- gateway_name。

建议通过 `VnpyOrderMapper` 先做兼容层，后续逐步补本项目内部字段。

## 5. 是否需要引入 EventEngine

短期：不需要引入 vn.py EventEngine。

原因：

- CLI / Research / Backtest 仍以同步 pipeline 更清晰；
- 引入 EventEngine 会增加 0 基础用户理解成本；
- 当前 QMT 未进入真实联调阶段。

中期：需要吸收事件驱动结构。

适用场景：

- paper trading 实时撮合；
- QMT 委托回报；
- 异常订单监控；
- Web UI 监控；
- 研究任务队列。

建议路线：先使用 `integrations/vnpy/vnpy_event_adapter.py`，等 paper/live 稳定后再设计正式事件总线。

## 6. vnpy_qmt 对 QMTBroker 的参考价值

参考价值：

- miniQMT 连接组织方式；
- QMT Gateway 作为独立模块接入交易框架的方式；
- 普通买卖、撤单、查询委托/成交/持仓/资金的接口边界；
- Apache-2.0 结构参考。

不能直接拿来：

- 依赖 vn.py 环境；
- 仓库规模和维护频率有限；
- 本项目需要更强审计、安全门和 0 基础课程文档；
- 实盘下单不能绕过本项目 `pre_trade_check`。

## 7. License 风险

vn.py 主仓库公开为 MIT License，商业友好，但仍需保留版权和许可声明。

vnpy_qmt 公开为 Apache-2.0，商业友好，但需要保留 License/NOTICE，并复核依赖链，尤其是 XtQuant/MiniQMT 官方许可和券商客户端使用条款。

本阶段没有复制 vn.py/vnpy_qmt 源码，只建立兼容映射和参考文档，License 风险较低。

## 8. 最终改造建议

1. 不整体引入 vn.py。
2. 吸收 EventEngine 思想，但先用轻量 adapter。
3. 吸收 Gateway/Broker 生命周期，未来补 `GatewayAdapterBase`。
4. 吸收 OrderData/TradeData/PositionData 字段，补本项目 order_id/trade_id/frozen/yd_volume。
5. 吸收 CTA 生命周期和参数管理，不吸收策略直接下单。
6. vnpy_qmt 只参考 QMT Gateway 结构，真实 QMTBroker 仍基于官方 XtQuant/MiniQMT。
7. 所有实盘链路必须继续经过 audit、readiness、pre_trade_check、dry_run 和 `CONFIRM_REAL_TRADE`。

## 主要来源

- vn.py GitHub: https://github.com/vnpy/vnpy
- vnpy_ctastrategy GitHub: https://github.com/vnpy/vnpy_ctastrategy
- CTA Strategy 文档: https://www.vnpy.com/docs/cn/community/app/cta_strategy.html
- vnpy_qmt GitHub: https://github.com/ruyisee/vnpy_qmt
- vnpy_qmt License: https://github.com/ruyisee/vnpy_qmt/blob/master/LICENSE
- vnpy_qmt setup.py: https://github.com/ruyisee/vnpy_qmt/blob/master/setup.py

