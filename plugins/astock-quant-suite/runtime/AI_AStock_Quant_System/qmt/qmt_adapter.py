from __future__ import annotations


class QMTAdapter:
    """Thin wrapper reserved for official xtdata/xttrader integration."""

    def xtdata_available(self) -> bool:
        try:
            from xtquant import xtdata  # type: ignore
            return xtdata is not None
        except Exception:
            return False

