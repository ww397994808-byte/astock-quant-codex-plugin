# A/H 比例因子研究归档

归档日期：2026-06-26

## 一句话结论

A/H 比例因子不适合作为全市场统一 Alpha。它在少数标的上可以作为状态变量或辅助过滤器，但不能作为“低 A/H 就买 A、高 A/H 就卖 A”的通用交易规则。

本研究已暂停，不继续投入参数优化。

## 研究初衷

最初问题来自中国神华：

- A 股：中国神华 `601088`
- H 股：中国神华 `1088`
- 想研究 `A/H 比例区间` 对后续股价涨跌的影响。

最初考虑两种买入/交易逻辑：

1. 只做多 A 股。
2. 做多 A 股，同时做空 H 股。

用户后续提出更高要求：策略目标不是高波动收益，而是确定性和低回撤，希望达到：

- 年化收益大于 20%
- 最大回撤低于 5%
- 从 2018 年开始研究

研究过程中又进一步扩展为：

- 监控所有同时有 A 股和 H 股的标的。
- 逐个分析 A/H 比例在该标的上是否有效。
- 如果有效，再进入选股和交易。

## 数据与口径

### 初始单标的数据

用户提供了两份中国神华日线数据：

- `HKEX_DLY_1088, 1D.csv`
- `SSE_DLY_601088, 1D.csv`

字段为：

```text
time, open, high, low, close
```

后续批量下载的数据字段为：

```text
datetime, open, high, low, close, volume
```

系统已兼容 `time`、`datetime`、`date` 三种日期字段。

### 全市场 A/H 数据

用户后续提供：

- `data.zip`

解压后放入：

- `data/ah_downloaded/data/`

文件命名形如：

- A 股：`601088_SSE_A.csv`
- H 股：`01088_HKEX_H.csv`

系统已兼容这种命名方式。

### 股票池

股票池文件：

- `config/ah_universe.csv`

下载核对清单：

- `config/ah_download_checklist.csv`

股票池来源：

- 麦格理 A/H 股价对照页面抓取
- 生成时共得到 124 个 A/H 标的

最终批量分析结果：

- 成功分析：122 个
- 样本不足：2 个，分别为美的集团、宁德时代

### 重要限制

本轮研究没有纳入以下因素：

1. HKD/CNY 汇率。
2. A 股和 H 股复权/总回报价格。
3. 分红税、交易费用差异、印花税差异。
4. 港股卖空可行性、借券成本和保证金要求。
5. A/H 两边实际成交滑点、流动性和停牌差异。
6. 行业基本面变量，例如煤价、油价、利率、指数趋势。

因此本轮结论只评价“原始收盘价比例是否呈现稳定规律”，不构成可实盘交易策略。

## 因子定义

第一版使用最朴素定义：

```text
A/H ratio = A 股收盘价 / H 股收盘价
```

滚动标准化：

```text
ratio_z = (当前 A/H ratio - 过去 252 日均值) / 过去 252 日标准差
```

正式版本如果重启，应改为：

```text
真实 A/H 溢价 = A股人民币价格 / (H股港币价格 * HKD/CNY)
```

并使用复权或总回报价格。

## 第一阶段：中国神华单标研究

### 数据范围

共同交易日：

- 2007-10-09 至 2026-06-25

2018 年后样本：

- 2018-01-02 至 2026-06-25
- 1983 个共同交易日

### 初始结果

输出：

- `reports/ah_shenhua_research/research_report.md`
- `reports/ah_shenhua_research/aligned_ah_ratio.csv`
- `reports/ah_shenhua_research/forward_return_by_ratio_bucket.csv`
- `reports/ah_shenhua_research/strategy_grid_summary.csv`

初始观察：

- 低 A/H 比例区间对中国神华 A 股后续 20-60 日收益有一定提示。
- 高 A/H 比例区间表现偏弱。

初始策略网格中，按 Sharpe 排名前列：

| 模式 | 入场z | 出场z | 总收益 | 年化 | 最大回撤 | Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| 只做多A | -0.50 | 0.00 | 619.32% | 12.17% | -45.38% | 0.66 |
| 只做多A | -0.50 | 0.50 | 540.42% | 11.41% | -45.38% | 0.60 |
| 多A空H | -1.00 | 0.00 | 309.27% | 8.55% | -39.09% | 0.54 |

这个结果说明：

- 因子有一些择时信息。
- 但裸策略回撤极大，完全不符合“确定性和低回撤”目标。

## 第二阶段：2018 年后低回撤目标检验

目标：

- 年化收益大于 20%
- 最大回撤低于 5%

输出：

- `reports/ah_shenhua_low_dd/optimizer_report.md`
- `reports/ah_shenhua_low_dd/optimizer_summary.csv`
- `reports/ah_shenhua_low_dd/best_trade_log.csv`

尝试加入的控制变量：

- 仓位比例
- 止损
- 止盈
- 最大持仓天数
- A 股趋势过滤
- 多 A 空 H 与只做多 A 两种模式

结论：

当前参数空间没有找到同时满足硬目标的组合。

关键结果：

| 情况 | 年化 | 最大回撤 | 说明 |
|---|---:|---:|---|
| 最接近收益目标 | 8.34% | -13.47% | 收益不够，回撤超标 |
| 回撤压到 5% 内较优 | 4.36% | -4.32% | 回撤合格，但收益远低于目标 |
| 最低回撤类组合 | 0.75% | -1.08% | 几乎失去收益能力 |

判断：

单靠中国神华 A/H 比例，无法支撑 `20% 年化 / 5% 回撤` 的硬目标。

## 第三阶段：中国神华区间与路径分析

用户指出应该先看数据规律，不应急着优化策略。

于是进行了区间分析。

输出：

- `reports/ah_shenhua_interval_analysis/interval_analysis_report.md`
- `reports/ah_shenhua_interval_analysis/raw_ratio_interval_forward_returns.csv`
- `reports/ah_shenhua_interval_analysis/zscore_interval_forward_returns.csv`
- `reports/ah_shenhua_interval_analysis/raw_ratio_interval_60d_path.csv`
- `reports/ah_shenhua_interval_analysis/zscore_interval_60d_path.csv`

2018 年以来，中国神华最新位置：

- 日期：2026-06-25
- A/H：0.975
- z-score：-1.014
- 原始比例低于 2018 年以来 10% 分位

z-score 区间后续收益：

| 区间 | 样本 | A后20日 | 胜率 | A后60日 | 胜率 | A后120日 | 胜率 | 多A空H后60日 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| < -1.5 | 218 | 1.67% | 51.38% | 1.78% | 54.13% | 8.41% | 69.80% | 2.44% |
| -1.5~-1.0 | 260 | 2.83% | 62.20% | 5.17% | 71.95% | 7.59% | 71.16% | 1.93% |
| -1.0~-0.5 | 201 | 1.31% | 57.07% | 3.48% | 54.97% | 8.14% | 68.35% | 1.76% |
| >= 1.5 | 215 | -1.93% | 35.81% | -1.52% | 32.09% | -2.01% | 33.95% | -4.28% |

路径特征：

| 区间 | A60日均值 | A胜率 | A期间平均最大跌幅 | 多A空H60日均值 |
|---|---:|---:|---:|---:|
| -1.5~-1.0 | 5.17% | 71.95% | -5.80% | 1.93% |
| < -1.5 | 1.78% | 54.13% | -6.63% | 2.44% |
| >= 1.5 | -1.52% | 32.09% | -9.86% | -4.28% |

阶段结论：

- 中国神华上，低 z-score 区间确实有一定后续 A 股上涨倾向。
- 但路径最大下探仍然接近或超过 5%，不天然低回撤。
- 低比例信号适合当状态指标，不适合单独交易。

## 第四阶段：扩展到全市场 A/H 股票池

目标从单标中国神华扩展到全部 A/H 标的。

新增说明文档：

- `docs/research/ah_ratio_universe_strategy.md`

批量分析脚本：

- `research/ah_universe_analyzer.py`
- `research/ah_universe_classifier.py`

批量分析输出：

- `reports/ah_universe_monitor_downloaded/ah_universe_monitor_report.md`
- `reports/ah_universe_monitor_downloaded/ah_universe_scores.csv`
- `reports/ah_universe_classification/ah_universe_classification_report.md`
- `reports/ah_universe_classification/ah_universe_classification.csv`

### 全市场监控结果

成功分析：

- 122 个标的

失败/样本不足：

- 美的集团：样本不足 162
- 宁德时代：样本不足 10

初始评分 Top 结果里，出现一个重要现象：

- 一些标的低比例有效。
- 一些标的高比例有效。
- 一些标的适合多 A 空 H。
- 很多标的无明显规律。

这直接否定了“统一 A/H 比例 Alpha”的假设。

### 有效性分层结果

输出：

- `reports/ah_universe_classification/ah_universe_classification_report.md`
- `reports/ah_universe_classification/ah_universe_classification.csv`

分层数量：

| 类型 | 数量 |
|---|---:|
| 无明显A/H效应 | 59 |
| 低比例多A空H有效 | 18 |
| 低比例做多A有效 | 17 |
| A/H区间偏无效或反向 | 15 |
| 高比例做多A有效 | 8 |
| 高比例多A空H有效 | 5 |

核心判断：

- 59 个无明显效应。
- 15 个偏无效或反向。
- 合计 74 个，占 122 个可分析标的的 60.66%。
- 因此，A/H 比例不是全市场稳定 Alpha。

### 当前触发候选示例

| 标的 | 类型 | 当前z | 逻辑 | 关键历史特征 |
|---|---|---:|---|---|
| 中信建投 | 高比例做多A有效 | 2.55 | long_a_when_high | 高区间 A 后60日均值 11.99% |
| 潍柴动力 | 低比例做多A有效 | -2.23 | long_a_when_low | 低区间 A 后60日均值 10.06%，胜率 64.97% |
| 青岛啤酒 | 低比例多A空H有效 | -1.84 | long_a_short_h_when_low | 低区间多A空H后60日均值 4.35% |
| 工商银行 | 低比例多A空H有效 | -1.20 | long_a_short_h_when_low | 低区间多A空H后60日均值 3.23% |
| 农业银行 | 低比例多A空H有效 | -0.72 | long_a_short_h_when_low | 低区间多A空H后60日均值 4.34% |
| 中国神华 | 低比例多A空H有效 | -1.07 | long_a_short_h_when_low | 低区间多A空H后60日均值 2.06% |

注意：

这些不是交易建议，只说明当前区间在历史上有某种统计倾向。它们尚未通过交易成本、滑点、真实卖空、复权、汇率和样本外检验。

## 最终结论

### 1. A/H 比例不是通用 Alpha

如果一个因子是通用 Alpha，它应当在多数标的、同一方向、相似规则下表现出稳定预测力。

本研究显示：

- 超过一半标的没有明显 A/H 效应或偏反向。
- 有效标的中，方向也不一致。
- 有些是低比例有效。
- 有些是高比例有效。
- 有些只在多 A 空 H 上有相对收益。

因此不能把 A/H 比例作为全市场统一选股 Alpha。

### 2. 它更像“标的特异性的状态变量”

对于少数标的，A/H 比例可以提示：

- 当前 A 股相对 H 股是否处于历史偏离位置。
- 未来 20-60 日 A 股或 A/H 相对表现是否可能有均值回归。
- 某些标的是否适合进入进一步回测名单。

但这只是辅助状态，不是独立交易系统。

### 3. 它不满足低回撤高确定性目标

以中国神华为例：

- 比例低位后确实有正向倾向。
- 但路径中平均最大下探仍接近 6%。
- 低回撤优化后，收益会显著下降。
- 无法达到 `20% 年化 / 5% 回撤` 的目标。

### 4. 继续投入的性价比不高

若继续研究，需要引入：

- 汇率
- 复权
- 股息率
- 行业变量
- 煤价、油价、利率、指数趋势
- 融券可行性
- 交易成本和滑点
- 分段样本和样本外检验

这已经不是“A/H 比例因子”本身，而是另一个多因子项目。

因此本项目在当前阶段归档暂停。

## 归档文件清单

### 主文档

- `docs/research/ah_ratio_factor_archive.md`
- `docs/research/ah_ratio_universe_strategy.md`
- `CASE_STUDY_PACK/shenhua_ah_ratio/original_idea.md`
- `CASE_STUDY_PACK/shenhua_ah_ratio/research_path.md`

### 配置与股票池

- `config/ah_universe.csv`
- `config/ah_download_checklist.csv`

### 核心脚本

- `research/ah_ratio_research.py`
- `research/ah_ratio_optimizer.py`
- `research/ah_ratio_interval_analysis.py`
- `research/ah_universe_analyzer.py`
- `research/ah_universe_classifier.py`
- `research/ah_ratio_event_path_analysis.py`
- `research/ah_ratio_candidate_rules.py`

### 单标中国神华输出

- `reports/ah_shenhua_research/`
- `reports/ah_shenhua_low_dd/`
- `reports/ah_shenhua_interval_analysis/`

### 全市场输出

- `reports/ah_universe_monitor/`
- `reports/ah_universe_monitor_downloaded/`
- `reports/ah_universe_classification/`

## 复现命令

### 中国神华初始研究

```bash
python3 research/ah_ratio_research.py \
  --a-csv data/ah_downloaded/data/601088_SSE_A.csv \
  --h-csv data/ah_downloaded/data/01088_HKEX_H.csv \
  --out-dir reports/ah_shenhua_research \
  --window 252 \
  --cost 0.001
```

### 中国神华低回撤优化

```bash
python3 research/ah_ratio_optimizer.py \
  --a-csv data/ah_downloaded/data/601088_SSE_A.csv \
  --h-csv data/ah_downloaded/data/01088_HKEX_H.csv \
  --out-dir reports/ah_shenhua_low_dd \
  --start-date 2018-01-01 \
  --window 252 \
  --cost 0.001
```

### 中国神华区间路径分析

```bash
python3 research/ah_ratio_interval_analysis.py \
  --a-csv data/ah_downloaded/data/601088_SSE_A.csv \
  --h-csv data/ah_downloaded/data/01088_HKEX_H.csv \
  --out-dir reports/ah_shenhua_interval_analysis \
  --start-date 2018-01-01 \
  --window 252
```

### 全市场监控

```bash
python3 research/ah_universe_analyzer.py \
  --universe config/ah_universe.csv \
  --data-dir data/ah_downloaded \
  --out-dir reports/ah_universe_monitor_downloaded \
  --start-date 2018-01-01 \
  --window 252
```

### 全市场有效性分层

```bash
python3 research/ah_universe_classifier.py \
  --universe config/ah_universe.csv \
  --data-dir data/ah_downloaded \
  --out-dir reports/ah_universe_classification \
  --start-date 2018-01-01 \
  --window 252 \
  --horizon 60
```

## 如果未来重启

不建议从“继续调 A/H 参数”开始。

更合理的重启方式：

1. 先补真实 A/H 溢价：加入 HKD/CNY。
2. 使用复权或总回报价格。
3. 只选少数在本轮里表现出稳定结构的行业，例如能源、银行、高股息。
4. 加入行业基本面因子。
5. 做严格样本外检验。
6. 再决定是否接入正式回测系统。

本研究当前状态：归档，不再主动推进。
