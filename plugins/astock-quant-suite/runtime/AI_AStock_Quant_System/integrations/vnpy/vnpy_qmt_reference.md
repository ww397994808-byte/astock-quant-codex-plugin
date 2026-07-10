# vnpy_qmt Reference

`ruyisee/vnpy_qmt` 定位为 QMT Gateway for vnpy，公开 README 显示其功能是连接 miniQMT 客户端实现普通买卖，并提供 pip 安装方式。

可参考：

- miniQMT 连接入口组织方式；
- QMT Gateway 与 vn.py MainEngine/Gateway 的集成方式；
- 普通买卖、委托、成交、持仓查询的封装边界；
- Apache-2.0 许可证下的结构参考。

不可直接使用为本项目实盘核心：

- 维护规模小；
- 需要 vn.py 运行环境；
- 可能和本项目 Task/Service/Audit/Readiness/QMT Safety 冲突；
- 不能绕过本项目 `pre_trade_check`、`dry_run`、`CONFIRM_REAL_TRADE`。

最终建议：只参考 Gateway 结构和 miniQMT 连接细节，不直接接管 `QMTBroker`。

