from __future__ import annotations

from data_acquisition.data_request import DataRequest
from market_data.providers.provider_registry import provider_chain


class ProviderRouter:
    def fetch(self, request: DataRequest) -> tuple[str, list[dict]]:
        for provider in provider_chain(request.preferred_source):
            if not provider.available():
                continue
            rows = provider.fetch(request)
            if rows:
                return provider.name, rows
        raise RuntimeError(f"无法获取数据：{request.symbol} {request.timeframe}")

