# A/H 比例选股与监控策略设计

## 目标

从单一中国神华扩展到所有 A 股和 H 股同时上市的公司，逐个检验 A/H 比例指标是否有效，并形成候选交易清单。

核心不是假设所有 A/H 标的都适用同一阈值，而是逐个标的建立自己的比例分布和有效区间。

## 标准股票池

股票池使用 `config/ah_universe.csv`，字段如下：

- `h_symbol`：港股代码，例如 `1088`
- `a_symbol`：A 股代码，例如 `601088`
- `a_market`：`SSE` 或 `SZSE`
- `name`：公司名称
- `sector`：行业
- `enabled`：是否启用
- `notes`：备注

股票池可以来自网页抓取、人工维护或外部数据商，但进入研究系统前必须统一成这个 CSV。

## 数据要求

每个标的至少需要两份日线：

- H 股：`HKEX_DLY_1088, 1D.csv`
- A 股：`SSE_DLY_601088, 1D.csv` 或 `SZSE_DLY_xxxxxx, 1D.csv`

当前脚本先使用收盘价原始比例：

```text
A/H = A股收盘价 / H股收盘价
```

正式版应替换为：

```text
A/H premium = A股人民币价格 / (H股港币价格 * HKD/CNY)
```

并使用复权或总回报价格。

## 分析逻辑

对每个标的单独计算：

1. 252 日滚动 A/H z-score。
2. 当前比例所处区间。
3. 当前区间历史上后 60 日 A 股平均收益。
4. 当前区间历史上后 60 日 A 股胜率。
5. 当前区间历史上后 60 日平均最大下探。
6. 当前区间历史上后 60 日多 A 空 H 平均收益。

输出排名时，优先看：

- 当前区间样本是否足够。
- 后续收益是否为正。
- 胜率是否高于 55%。
- 平均最大下探是否可接受。
- 多 A 空 H 是否相对更稳定。

## 运行方式

```bash
python3 research/ah_universe_analyzer.py \
  --universe config/ah_universe.csv \
  --data-dir /path/to/ah_csv_folder \
  --out-dir reports/ah_universe_monitor \
  --start-date 2018-01-01 \
  --window 252
```

输出：

- `reports/ah_universe_monitor/ah_universe_monitor_report.md`
- `reports/ah_universe_monitor/ah_universe_scores.csv`
- `reports/ah_universe_monitor/ah_universe_errors.csv`

## 交易前还需要补的层

1. 股票池自动更新。
2. A/H 日线自动下载。
3. HKD/CNY 汇率。
4. 复权/分红处理。
5. 逐年稳定性检验。
6. 候选标的再进入单标的策略回测，而不是直接交易。
7. 多 A 空 H 必须检查港股做空可行性、借券成本和汇率风险。
