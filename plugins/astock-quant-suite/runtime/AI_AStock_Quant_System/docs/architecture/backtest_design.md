# 回测设计

回测按时间逐 K 线推进：第 i 根已闭合 K 线生成 Signal，第 i+1 根 K 线按开盘价撮合。订单记录 `signal_time` 和 `execute_time`，审计要求 `execute_time > signal_time`。

