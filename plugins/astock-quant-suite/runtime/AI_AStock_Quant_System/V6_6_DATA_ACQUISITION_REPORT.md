# V6.6 Data Acquisition Report

## 已完成

- 新增 Data Acquisition Agent。
- 新增 SymbolResolver。
- 新增 Local/QMT/AkShare/Tushare provider chain。
- 新增 data_lake 缓存目录。
- CLI 支持 fetch-data、update-data、data-status。
- Research Agent 在本地数据缺失时会自动触发数据获取。

## 当前课程版数据源

课程版默认 AkShare provider，但为了保证离线可运行，当前 AkShareProvider 使用 deterministic sample-backed acquisition。接口保持 provider 形式，后续可接真实 AkShare。

## 是否做到自动化

已做到：一句话研究时，如果 data path 不存在，系统会自动拉取、缓存，再继续 Research Agent。

