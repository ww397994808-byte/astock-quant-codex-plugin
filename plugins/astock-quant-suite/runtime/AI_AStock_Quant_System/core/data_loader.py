from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_COLUMNS = [
    "date", "open", "high", "low", "close", "volume", "amount",
    "symbol", "name", "is_st", "board", "paused",
]


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是"}


def load_csv_data(path: str | Path, symbol: str | None = None) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"找不到数据文件：{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [col for col in REQUIRED_COLUMNS if col not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"CSV 缺少字段：{', '.join(missing)}。请使用标准字段：{', '.join(REQUIRED_COLUMNS)}")
        rows = list(reader)
    parsed: list[dict[str, Any]] = []
    seen_dates: set[datetime] = set()
    for raw in rows:
        raw_datetime = raw.get("datetime") or raw.get("date")
        try:
            dt_full = datetime.strptime(raw_datetime[:19], "%Y-%m-%d %H:%M:%S") if " " in raw_datetime else datetime.strptime(raw["date"], "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(f"日期格式错误：{raw_datetime}，请使用 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS。") from exc
        key_dt = dt_full if raw.get("datetime") else datetime.strptime(raw["date"], "%Y-%m-%d")
        if key_dt in seen_dates:
            raise ValueError(f"发现重复日期/时间：{raw_datetime}。请删除重复 K 线。")
        seen_dates.add(key_dt)
        if symbol and raw["symbol"] != symbol:
            continue
        row = dict(raw)
        row["datetime"] = dt_full
        row["date"] = dt_full
        row["time"] = raw.get("time") or dt_full.strftime("%H:%M:%S")
        row["timeframe"] = raw.get("timeframe", "1d")
        row["source"] = raw.get("source", "csv")
        row["adjust_type"] = raw.get("adjust_type", "raw")
        row["adjust_factor"] = float(raw.get("adjust_factor") or 1.0)
        row["corporate_action_flag"] = _to_bool(raw.get("corporate_action_flag", False))
        for col in ["open", "high", "low", "close", "amount"]:
            if row[col] in {"", None}:
                raise ValueError(f"{raw['date']} 的 {col} 为空，不能用于回测。")
            row[col] = float(row[col])
        row["volume"] = int(float(row["volume"]))
        row["is_st"] = _to_bool(row["is_st"])
        row["paused"] = _to_bool(row["paused"])
        parsed.append(row)
    parsed.sort(key=lambda x: x["datetime"])
    return parsed
