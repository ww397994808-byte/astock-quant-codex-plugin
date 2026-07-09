# A股量化研究教练 Codex 插件

这是一个本地可安装、可通过 GitHub 分发的 Codex 插件。它把 Codex 约束为中文 A 股量化研究教练，带用户按标准流程完成：

```text
学习入门 -> 策略想法整理 -> 数据获取 -> 严格回测 -> 审计 -> 阶段裁判 -> 模拟盘 -> QMT 只读 -> 实盘前检查 -> 真实运行人工确认
```

## 适合谁

- 完全不懂量化、需要中文引导的小白。
- 想按 A 股交易规则做研究、回测和模拟盘的人。
- 想避免未来函数、过拟合、复权泄漏和交易规则错误的人。
- 想把研究流程推进到 QMT 实盘前检查，但不希望 AI 绕过风控的人。

## 安装方式

在 Codex 中让它执行：

```powershell
codex plugin marketplace add https://github.com/ww397994808-byte/astock-quant-codex-plugin.git
```

然后重启 Codex，打开插件页面，在 `A股量化插件` 中安装：

```text
A股量化研究教练
```

## 使用方式

安装后新开一个 Codex 线程，输入：

```text
使用 A股量化研究教练。我是小白，想研究中国神华周线布林低吸策略，请按严格教学模式带我走完整流程。
```

也可以输入：

```text
使用 astock-quant-coach，带我从一个 A 股策略想法开始，按标准流程完成研究、回测、审计、模拟盘和实盘前检查。
```

## 插件能力

- 中文输出，不向小白直接展示英文状态码。
- 默认严格教学模式，防止用户无限研究、无限调参。
- 支持研究员模式，但继续研究必须限定目的。
- 引导用户先准备数据，再回测。
- 强制强调 A 股规则：T+1、涨跌停、停牌、100 股、费用、成交时点。
- 强制检查未来函数、复权泄漏、过拟合和回测假设漂移。
- 在每个阶段输出“是否进入下一阶段”的明确判断。
- 真实实盘阶段只允许人工确认和安全门控，不允许 AI 静默下单。

## 重要风险声明

本插件是量化研究学习和流程辅助工具，不构成投资建议，不承诺收益。回测、模拟盘和实盘结果均由用户自行承担风险。

真实交易必须由用户人工确认，并遵守券商、交易所、数据源和当地法律法规要求。

## 仓库结构

```text
.agents/plugins/marketplace.json
plugins/astock-quant-coach/
  .codex-plugin/plugin.json
  skills/astock-quant-coach/
    SKILL.md
    references/
      data-acquisition.md
      strict-backtest.md
      phase-controller.md
      live-trading.md
```
