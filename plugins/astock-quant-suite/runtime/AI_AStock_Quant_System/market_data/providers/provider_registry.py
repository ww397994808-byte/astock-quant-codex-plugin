from __future__ import annotations

from market_data.providers.akshare_provider import AkShareProvider
from market_data.providers.local_provider import LocalProvider
from market_data.providers.qmt_provider import QMTProvider
from market_data.providers.tushare_provider import TushareProvider


def provider_chain(preferred_source: str | None = None):
    providers = [LocalProvider(), QMTProvider(), AkShareProvider(), TushareProvider()]
    if preferred_source:
        providers = sorted(providers, key=lambda p: 0 if p.name == preferred_source else 1)
    return providers

