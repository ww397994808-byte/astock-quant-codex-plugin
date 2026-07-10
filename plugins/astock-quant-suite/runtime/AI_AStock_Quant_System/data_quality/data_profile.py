from __future__ import annotations


def profile_data(rows: list[dict]) -> dict:
    if not rows:
        return {"row_count": 0}
    dates = [r["date"] for r in rows]
    return {
        "row_count": len(rows),
        "start_date": dates[0].strftime("%Y-%m-%d") if hasattr(dates[0], "strftime") else str(dates[0]),
        "end_date": dates[-1].strftime("%Y-%m-%d") if hasattr(dates[-1], "strftime") else str(dates[-1]),
        "symbols": sorted({r.get("symbol", "") for r in rows}),
    }

