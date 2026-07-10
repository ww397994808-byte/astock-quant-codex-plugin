from __future__ import annotations

from services.paper_service import PaperService


class PaperRunner:
    def run(self, strategy: str, symbol: str, data: str):
        return PaperService().run(strategy, symbol, data)

