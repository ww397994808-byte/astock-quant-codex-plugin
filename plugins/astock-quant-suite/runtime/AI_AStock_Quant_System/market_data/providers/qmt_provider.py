from __future__ import annotations

from data_acquisition.data_request import DataRequest


class QMTProvider:
    name = "qmt"

    def available(self) -> bool:
        try:
            import xtquant  # type: ignore
            return xtquant is not None
        except Exception:
            return False

    def fetch(self, request: DataRequest) -> list[dict]:
        return []

