# 系统架构

```text
自然语言 -> Codex Skill -> Task Layer -> Service Layer -> Engine -> Broker -> XtQuant / MiniQMT
```

CLI、未来 Web、QQ、微信、OpenClaw、QClaw、Codex Skill 都必须调用 `tasks/`。业务逻辑在 `services/` 和下层模块，不能写在入口层。

