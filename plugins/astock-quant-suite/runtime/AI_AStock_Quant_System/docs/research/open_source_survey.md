# AI_AStock_Quant_System 开源项目调研

调研日期：2026-06-21  
目标：为 A股 AI 量化研究、回测、参数优化、风控审计、模拟盘、QMT 实盘系统选择可复用组件。  
结论先行：本项目第一版不建议把任何通用开源框架直接作为实盘核心。建议采用“自研 A股交易规则、审计、QMT 安全层 + 参考/二次封装成熟研究与回测项目”的架构。

## 评分口径

- A：可作为重要底层或重点二次封装对象。
- B：适合局部复用或深度参考。
- C：只适合参考设计、教学或非核心工具。
- D：不建议纳入核心依赖。

商用判断只基于公开 License 与项目形态做工程初筛，不构成法律意见；商业交付前仍需法务复核。

## 调研总表

| 项目 | Github 地址 | Stars | 最近更新时间 | License | 是否仍在维护 | 支持 A股 | 支持 QMT | 支持回测 | 支持参数优化 | 支持模拟盘 | 支持实盘 | AI Agent / 自然语言工作流 | 适合商用 | 适合课程化交付 | 适合作为底层核心 | 适合作为参考 | 推荐等级 | 结论 |
|---|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| QuantDinger | https://github.com/brokermr810/QuantDinger | 8,407 | 2026-06-21 | Apache-2.0 | 是 | 部分，未见 A股规则/QMT 原生支持 | 否 | 是 | 部分 | 是 | 是 | 是，Agent Gateway / MCP | 较适合，需复核依赖与商标/云服务边界 | 适合参考产品形态 | 不建议直接作为 A股/QMT 底层核心 | 是 | B | 二次封装/重点参考 |
| XtQuant / MiniQMT 官方接口 | https://dict.thinktrader.net/nativeApi/start_now.html / https://pypi.org/project/xtquant/ | N/A | PyPI 2025-06-11 | PyPI 标注 GPLv3；官方商业条款需单独核验 | 是 | 是 | 是 | 否 | 否 | 依赖外部系统 | 是 | 否 | 条款需核验 | 适合实盘接口教学 | 是，限 QMT 适配层 | 是 | A | QMT 实盘优先接口 |
| vn.py | https://github.com/vnpy/vnpy | 41,897 | 2026-06-21 | MIT | 是 | 是，国内量化生态成熟 | 需插件/网关 | 是 | 部分 | 是 | 是 | 有 AI-Powered 定位，但非 NL 策略核心 | 适合 | 适合进阶课程 | 不建议第一版直接承载全部系统 | 是 | B | 二次封装/参考架构 |
| vnpy_qmt | https://github.com/ruyisee/vnpy_qmt | 115 | 2026-06-11 | Apache-2.0 | 低频维护，最近 push 2024-03-08 | 是 | 是 | 依赖 vn.py | 否 | 依赖 vn.py | 是 | 否 | 较适合，需实测 | 适合 QMT 网关章节 | 不建议作为唯一实盘核心 | 是 | C | 只参考/可选适配 |
| xtquantai | https://github.com/dfkai/xtquantai | 136 | 2026-06-20 | MIT | 是 | 是 | 是 | 脚本/技能级 | 脚本/技能级 | 否 | 否，不应直接实盘 | 是，Agent Skills | 较适合，需边界控制 | 适合 Codex Skill 参考 | 否 | 是 | C | 只参考 |
| qmt-trading-skill | https://github.com/atorber/qmt-trading-skill | 4 | 2026-06-10 | MIT | 新项目，样本少 | 是 | 是 | 否 | 否 | 可能支持 | 可能支持 | 是 | 风险高，不能作核心 | 可做反例/参考 | 否 | 是 | C | 只参考 |
| miniqmt-skills | https://github.com/nnquant/miniqmt-skills | 37 | 2026-05-26 | 未声明 | 低频维护 | 是 | 是 | 不明确 | 不明确 | 不明确 | 不明确 | 是 | 不适合，License 不清 | 可参考 | 否 | 是 | D | 不建议使用 |
| QMT Bridge | https://github.com/atompilot/qmt-bridge | 100 | 2026-06-21 | MIT | 是 | 是 | 是，HTTP/WebSocket 包装 xtquant | 否 | 否 | 可能支持 | 可能支持 | 否 | 较适合，需安全审计 | 适合作为跨平台部署案例 | 不作为核心下单链路 | 是 | C | 只参考/可选桥接 |
| quant-qmt-proxy | https://github.com/liqimore/quant-qmt-proxy | 182 | 2026-06-14 | MIT | 是 | 是 | 是，RESTful proxy | 否 | 否 | 可能支持 | 可能支持 | 否 | 较适合，需安全审计 | 适合作为部署参考 | 不作为核心下单链路 | 是 | C | 只参考/可选桥接 |
| Backtrader | https://github.com/mementum/backtrader | 22,068 | 2026-06-21 | GPL-3.0 | 维护偏弱，最近 push 2024-08-19 | 可自定义 | 否 | 是 | 有优化能力 | 支持 broker 模型 | 可接 broker，但非 QMT | 否 | GPL 对闭源商用不友好 | 适合教学 | 否 | 是 | C | 只参考 |
| VectorBT | https://github.com/polakowo/vectorbt | 7,987 | 2026-06-21 | Apache-2.0 with Commons Clause | 是 | 可接入数据 | 否 | 是，强项 | 是，强项 | 否 | 否 | README 称适合 AI agent-driven workflows | Commons Clause 限制再销售，商用需谨慎 | 适合研究课 | 否 | 是 | B/C | 只参考或研究端可选 |
| Qlib | https://github.com/microsoft/qlib | 44,897 | 2026-06-21 | MIT | 是 | 是，支持 cn_data | 否 | 是 | 是，ML/Auto Quant 强 | 有在线/执行框架 | 非 QMT | 是，RD-Agent/Auto Quant | 适合 | 适合高阶课程 | 可作为研究/ML 子系统参考，不作交易规则核心 | 是 | A/B | 二次封装研究端 |
| RQAlpha | https://github.com/ricequant/rqalpha | 6,495 | 2026-06-21 | Other / NOASSERTION | 是 | 是 | 否 | 是 | 部分 | 支持交易框架 | 非 QMT | 否 | License 需核验 | 适合 A股回测教学参考 | 不作为核心 | 是 | B | 二次封装/参考 |
| PyBroker | https://github.com/edtechre/pybroker | 3,430 | 2026-06-20 | Apache-2.0 with Commons Clause | 是 | 通过 AKShare/自定义数据间接支持 | 否 | 是 | Walkforward 强 | 否 | 否 | 否 | Commons Clause 限制，需谨慎 | 适合 ML 回测课程 | 否 | 是 | C | 只参考 |
| Zipline | https://github.com/quantopian/zipline | 19,894 | 2026-06-21 | Apache-2.0 | 弱维护，最新 release 2020-10-05 | 不原生 | 否 | 是 | 有 pipeline | 历史上支持 | 历史上支持 | 否 | License 友好但生态老 | 适合历史案例 | 否 | 是 | D | 不建议使用 |
| QuantConnect Lean | https://github.com/QuantConnect/Lean | 20,001 | 2026-06-21 | Apache-2.0 | 是 | 非 A股/QMT 原生 | 否 | 是 | 有研究工具链 | 是 | 是，多市场 broker | 否 | 适合，但体系重 | 适合架构参考 | 不适合作为本项目第一版底座 | 是 | B/C | 只参考 |

## 重点项目分析

### 1. QuantDinger

公开 README 显示 QuantDinger 定位为开源 AI 量化基础设施，覆盖“AI research -> Strategy code -> Backtest -> Paper/Live execution -> Monitoring”。它包含 Flask 后端、Vue 前端、PostgreSQL、Redis、Docker Compose、Agent Gateway、MCP、审计日志、paper-only 默认 token、安全开关、多经纪商执行适配等能力。

优势：

- 产品闭环完整，适合参考本项目“0基础用户 + AI 工作流 + 回测/模拟/实盘监控”的用户路径。
- Apache-2.0 对商业化相对友好。
- Agent Gateway 与 paper-only 默认机制符合“AI 不能绕过风控直接下单”的方向。
- Docker Compose、PostgreSQL、Redis、多用户和审计日志适合作为未来商业版参考。

不足：

- 主要覆盖 crypto、IBKR、MT5、Alpaca 等，未发现 A股 T+1、涨跌停、停牌、100 股手数、印花税、QMT 官方接口的核心实现。
- 对本项目最关键的未来函数审核、A股交易规则审核、QMT 实盘前检查仍需自研。
- 直接引入完整栈会增加第一版复杂度，不利于 CLI/课程化最小闭环。

建议：推荐等级 B。重点参考 AI Agent 工作流、Docker 部署、审计日志、安全默认值、研究到执行的产品闭环；不建议直接作为 A股/QMT 实盘底座。

### 2. XtQuant / MiniQMT 官方接口

迅投知识库说明：XtQuant 是基于 MiniQMT 的 Python 策略运行框架，对外提供行情和交易 API；XtData 是行情模块，提供历史/实时 K线、分笔、财务数据、合约基础信息、板块和行业分类；XtTrader 是交易模块，可与 MiniQMT 客户端交互进行报单、撤单、查询资产、委托、成交、持仓，并接收变动推送。PyPI 上 xtquant 最新可见版本为 250516.1.1，发布日期 2025-06-11。

建议：推荐等级 A。QMT 实盘部分必须优先基于官方 xtdata/xttrader 适配，第三方 bridge/skill 只能参考，不应成为核心下单链路。

### 3. vn.py 与 vnpy_qmt

vn.py 是国内成熟 Python 量化交易平台框架，MIT License，社区规模大，适合作为交易系统架构、事件引擎、网关设计、课程高级章节参考。`ruyisee/vnpy_qmt` 是 QMT Gateway for vnpy，Apache-2.0，但规模较小且最近 push 较旧。

建议：vn.py 推荐 B，vnpy_qmt 推荐 C。本项目第一版保持轻量 CLI 和自研规则核心；未来可做 vn.py 网关兼容或迁移章节。

### 4. Qlib

Qlib 是 Microsoft 的 AI-oriented Quant 平台，MIT License，支持完整 ML 流水线、数据处理、模型训练、回测、研究分析，并支持 cn_data。README 显示其结合 RD-Agent 做自动因子挖掘和模型优化。

建议：推荐 A/B。适合未来“AI 因子研究 / ML 策略 / 参数与模型评估”子系统参考或二次封装；不负责本项目第一版交易规则和 QMT 下单安全。

### 5. Backtrader / RQAlpha / VectorBT / PyBroker / Zipline / Lean

- Backtrader：事件式回测成熟，但 GPL-3.0 对闭源商业化不友好；A股规则需大量自定义。
- RQAlpha：A股回测经验丰富，但 License 需复核；适合作为 A股回测设计参考。
- VectorBT：参数扫描和向量化研究能力强，但 Commons Clause 对销售限制明显；不适合直接作为商业核心。
- PyBroker：机器学习和 Walkforward 设计值得参考，但同样有 Commons Clause 风险。
- Zipline：历史影响大但维护弱，不建议采用。
- Lean：工程化强，但体系重且非 A股/QMT 原生，不适合第一版底座。

## 复用建议

### 可直接进入技术路线的内容

1. QMT 实盘：使用 XtQuant / MiniQMT 官方接口作为唯一优先实现路径。
2. 文档和产品闭环：参考 QuantDinger 的 AI research -> strategy code -> backtest -> paper/live execution -> monitoring。
3. ML/因子研究：参考 Qlib 的数据、模型、研究流水线。
4. 参数扫描/稳定性：参考 VectorBT、PyBroker 的参数矩阵、Walkforward 和稳定性分析思想，但不把其作为强依赖。
5. A股回测语义：参考 RQAlpha、vn.py 的国内市场经验。

### 必须自研的核心

1. A股交易规则：T+1、涨跌停、停牌、100股、费用、现金/持仓、成交时点。
2. 未来函数审核：静态扫描、订单时间审计、结果审计。
3. 交易规则审核：回测后自动 INVALID 判定。
4. QMT 实盘前检查：dry_run 默认、二次确认、审计通过、风控通过、emergency_stop。
5. 面向 0 基础用户的 CLI、配置、报告、课程文档。

### 不建议第一版采用的内容

1. 不直接迁入 QuantDinger 全栈作为底座，避免 A股规则缺口和复杂度失控。
2. 不把第三方 QMT Bridge / proxy / skill 作为实盘核心。
3. 不把 Prompt 或 Skill 作为交易规则、风控判断、未来函数判断的核心实现。
4. 不将 GPL/Commons Clause 项目作为闭源商业产品核心依赖，除非后续法务确认和架构隔离。

## 最终建议

本项目采用自研核心仓库：

- `core/` 固化 A股市场规则、费用、持仓、资金、风控。
- `backtest/` 固化逐 K 线推进、下一根 K 线成交、可审计输出。
- `audit/` 固化未来函数和交易规则审计，HIGH 风险直接 INVALID。
- `qmt/` 基于 XtQuant/MiniQMT 官方接口封装，默认 dry_run。
- `prompts/` 和 `skills/` 只调用已有 CLI 和代码，不做核心交易判断。

QuantDinger、Qlib、vn.py、RQAlpha、VectorBT、PyBroker 等作为参考和未来二次封装方向，不替代本项目第一版的 A股规则和安全内核。

## 主要来源

- QuantDinger GitHub: https://github.com/brokermr810/QuantDinger
- vn.py GitHub: https://github.com/vnpy/vnpy
- vnpy_qmt GitHub: https://github.com/ruyisee/vnpy_qmt
- XtQuant 快速开始: https://dict.thinktrader.net/nativeApi/start_now.html
- XtQuant XtData: https://dict.thinktrader.net/nativeApi/xtdata.html
- XtQuant XtTrader: https://dict.thinktrader.net/nativeApi/xttrader.html
- xtquant PyPI: https://pypi.org/project/xtquant/
- xtquantai GitHub: https://github.com/dfkai/xtquantai
- qmt-trading-skill GitHub: https://github.com/atorber/qmt-trading-skill
- miniqmt-skills GitHub: https://github.com/nnquant/miniqmt-skills
- QMT Bridge GitHub: https://github.com/atompilot/qmt-bridge
- quant-qmt-proxy GitHub: https://github.com/liqimore/quant-qmt-proxy
- Backtrader GitHub: https://github.com/mementum/backtrader
- VectorBT GitHub: https://github.com/polakowo/vectorbt
- Qlib GitHub: https://github.com/microsoft/qlib
- RQAlpha GitHub: https://github.com/ricequant/rqalpha
- PyBroker GitHub: https://github.com/edtechre/pybroker
- Zipline GitHub: https://github.com/quantopian/zipline
- QuantConnect Lean GitHub: https://github.com/QuantConnect/Lean
