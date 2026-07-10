# A股量化研究套件 Codex 插件

这是一个可通过 GitHub marketplace 分发的完整 Codex 插件包。它不只是 Skill 提示词，而是把中文教学 Skill、agent 元数据、可执行量化 runtime、硬约束代码、固定模板、安装脚本、体检脚本和测试一起打包。

标准流程：

```text
学习入门 -> 策略想法整理 -> 数据获取 -> 严格回测 -> 审计 -> 阶段裁判 -> 模拟盘 -> QMT 只读 -> 实盘前检查 -> 真实运行人工确认
```

## 包内包含

- `plugins/astock-quant-suite/.codex-plugin/plugin.json`
- `plugins/astock-quant-suite/skills/astock-quant-research/`
- `plugins/astock-quant-suite/skills/astock-quant-research/agents/openai.yaml`
- `plugins/astock-quant-suite/runtime/AI_AStock_Quant_System/`
- `plugins/astock-quant-suite/templates/`
- `plugins/astock-quant-suite/scripts/install_runtime.py`
- `plugins/astock-quant-suite/scripts/doctor.py`
- `plugins/astock-quant-suite/scripts/run_astock_cli.py`
- `plugins/astock-quant-suite/docs/HARD_CONSTRAINTS.md`

## 安装

添加 marketplace：

```bash
codex plugin marketplace add https://github.com/ww397994808-byte/astock-quant-codex-plugin.git
```

安装插件：

```bash
codex plugin add astock-quant-suite@astock-quant
```

新开 Codex 线程后使用：

```text
使用 A股量化研究套件，先帮我做本地体检。
```

## 本地 runtime 安装

插件内置 runtime 可以直接作为只读套件参考，也可以复制到用户本地目录运行：

```bash
python3 plugins/astock-quant-suite/scripts/install_runtime.py --init-qmt-config
```

默认目标：

```text
~/.codex/astock-quant-suite/AI_AStock_Quant_System
```

安装脚本不会复制真实 `config/qmt_config.yaml`，只会通过 runtime 的 `qmt-config-init` 创建安全配置：

```yaml
dry_run: true
enable_real_trade: false
```

## 体检

插件包体检：

```bash
python3 plugins/astock-quant-suite/scripts/doctor.py
```

runtime 体检：

```bash
python3 plugins/astock-quant-suite/scripts/run_astock_cli.py -- student-doctor
python3 plugins/astock-quant-suite/scripts/run_astock_cli.py -- student-product-audit
```

## 使用示例

从一个策略想法开始：

```bash
python3 plugins/astock-quant-suite/scripts/run_astock_cli.py -- \
  student-course-path \
  --idea "中国神华周线布林低吸，控制回撤" \
  --session-id demo
```

检查策略代码未来函数：

```bash
python3 plugins/astock-quant-suite/scripts/run_astock_cli.py -- \
  student-future-leak-precheck \
  --file path/to/strategy.py
```

完整新手 workflow：

```bash
python3 plugins/astock-quant-suite/scripts/run_astock_cli.py -- \
  student-workflow \
  --idea "中国神华周线布林低吸，控制回撤" \
  --timeframe 1d \
  --adjust point_in_time_qfq \
  --auto-refine \
  --session-id demo
```

## 硬边界

硬约束必须由 runtime 代码执行，Skill 只负责引导 Codex 调用正确入口。

- 不允许未 intake / 未 backtest plan 的 raw idea 直接回测。
- 不允许未来函数、复权泄漏、同 K 线信号成交、负向 shift、居中窗口通过审计。
- 不允许审计未通过进入模拟盘。
- 不允许模拟盘观察不足进入 QMT 只读。
- 不允许 QMT 配置不完整或不安全时运行 QMT 只读。
- 不允许跳过 pretrade package / runbook / pretrade check 讨论真实委托。
- 安装插件不会开启实盘，`enable_real_trade=false` 是默认边界。

见 `plugins/astock-quant-suite/docs/HARD_CONSTRAINTS.md`。

## 不打包的内容

- 用户真实 QMT 配置
- 账户号、MiniQMT 本地路径
- 运行报告和 ledgers
- 大型下载行情数据
- 真实交易确认状态

## 风险声明

本插件是量化研究学习和流程辅助工具，不构成投资建议，不承诺收益。回测、模拟盘和实盘结果均由用户自行承担风险。真实交易必须由用户人工确认，并遵守券商、交易所、数据源和当地法律法规要求。
