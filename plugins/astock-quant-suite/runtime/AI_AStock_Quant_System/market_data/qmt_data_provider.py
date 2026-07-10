from __future__ import annotations

from market_data.data_provider_base import DataProviderBase


class QMTDataProvider(DataProviderBase):
    def load_bars(self, symbol: str, timeframe: str = "1d", adjust: str = "raw") -> list[dict]:
        raise RuntimeError("QMTDataProvider 需要真实 XtQuant/MiniQMT 环境；当前只提供安全骨架。")

