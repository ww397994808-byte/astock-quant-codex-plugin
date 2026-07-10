from __future__ import annotations

from data_acquisition.cache_manager import CacheManager
from data_acquisition.data_request import DataRequest


class LocalProvider:
    name = "local"

    def available(self) -> bool:
        return True

    def fetch(self, request: DataRequest) -> list[dict]:
        cache = CacheManager()
        if not cache.has(request):
            return []
        return cache.load(request)

