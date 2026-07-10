from __future__ import annotations

from data_acquisition.data_request import DataRequest


class TushareProvider:
    name = "tushare"

    def available(self) -> bool:
        return False

    def fetch(self, request: DataRequest) -> list[dict]:
        return []

