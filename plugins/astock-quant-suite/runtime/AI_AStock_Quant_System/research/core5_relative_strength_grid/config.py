from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


CORE5 = ["601088.SH", "600900.SH", "601288.SH", "601398.SH", "601939.SH"]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_DATA_DIR = "CORE5_DATA_DIR"

EXTERNAL_FILES_30M = {
    "601088.SH": "/Users/shejishi/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/woziji741_18b5/temp/drag/SSE_DLY_601088, 30.csv",
    "600900.SH": "/Users/shejishi/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/woziji741_18b5/temp/drag/SSE_DLY_600900, 30.csv",
    "601288.SH": "/Users/shejishi/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/woziji741_18b5/temp/drag/SSE_DLY_601288, 30.csv",
    "601398.SH": "/Users/shejishi/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/woziji741_18b5/temp/drag/SSE_DLY_601398, 30.csv",
    "601939.SH": "/Users/shejishi/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/woziji741_18b5/temp/drag/SSE_DLY_601939, 30.csv",
}
FILES_30M = EXTERNAL_FILES_30M


def _code(symbol: str) -> str:
    return symbol.split(".")[0]


def market_file_candidates(symbol: str) -> list[Path]:
    code = _code(symbol)
    candidates = []
    env_dir = os.environ.get(ENV_DATA_DIR)
    if env_dir:
        base = Path(env_dir)
        candidates.extend(
            [
                base / f"SSE_DLY_{code}, 30.csv",
                base / f"{code}.SH.csv",
                base / f"{code}.csv",
                base / f"{code}_SSE_A.csv",
            ]
        )
    candidates.extend(
        [
            PROJECT_ROOT / "data" / "core5_raw" / f"SSE_DLY_{code}, 30.csv",
            PROJECT_ROOT / "data" / "core5_raw" / f"{code}.SH.csv",
            PROJECT_ROOT / "data" / "core5_raw" / f"{code}.csv",
            PROJECT_ROOT / "data" / "ah_downloaded" / "data" / f"{code}_SSE_A.csv",
            Path(EXTERNAL_FILES_30M[symbol]),
        ]
    )
    return candidates


def resolve_market_file(symbol: str) -> Path | None:
    for path in market_file_candidates(symbol):
        if path.exists():
            return path
    return None


def missing_market_files() -> dict[str, list[str]]:
    missing = {}
    for symbol in CORE5:
        if resolve_market_file(symbol) is None:
            missing[symbol] = [str(path) for path in market_file_candidates(symbol)]
    return missing

INITIAL_CASH = 1_000_000.0
COMMISSION = 0.0003
TRANSFER_FEE = 0.00001
STAMP_TAX = 0.0005

# Implemented dividends only. Draft/proposal rows without ex-dividend dates are excluded.
# Values are cash dividend per share, converted from public "per 10 shares" records.
DIVIDENDS = {
    "601088.SH": {
        "2021-07-12": 1.81,
        "2022-07-11": 2.54,
        "2023-07-05": 2.55,
        "2024-07-08": 2.26,
        "2025-07-07": 2.26,
        "2025-11-10": 0.98,
    },
    "600900.SH": {
        "2021-07-16": 0.70,
        "2022-07-21": 0.8153,
        "2023-07-21": 0.8533,
        "2024-07-19": 0.82,
        "2025-01-24": 0.21,
        "2025-07-18": 0.733,
        "2026-02-12": 0.21,
    },
    "601288.SH": {
        "2021-06-17": 0.1851,
        "2022-07-15": 0.2068,
        "2023-07-18": 0.2222,
        "2024-06-07": 0.2309,
        "2025-01-08": 0.1164,
        "2025-07-17": 0.1255,
        "2025-12-15": 0.1195,
        "2026-05-13": 0.13,
    },
    "601398.SH": {
        "2021-07-06": 0.266,
        "2022-07-12": 0.2933,
        "2023-07-17": 0.3035,
        "2024-07-16": 0.3064,
        "2025-01-07": 0.1434,
        "2025-07-14": 0.1646,
        "2025-12-15": 0.1414,
        "2026-05-13": 0.1689,
    },
    "601939.SH": {
        "2021-07-15": 0.326,
        "2022-07-08": 0.364,
        "2023-07-14": 0.389,
        "2024-07-12": 0.40,
        "2025-01-10": 0.197,
        "2025-05-09": 0.206,
        "2025-12-11": 0.1858,
    },
}


@dataclass(frozen=True)
class FixedRule:
    param_score_mode: str = "recent3"
    param_lookback_months: int = 12
    symbol_lookback_months: int = 2
    top_weights: tuple[float, ...] = (1.0,)
    start_date: str = "2017-01-01"
    end_date: str = "2026-06-24"
    dividend_factor: float = 1.0


def default_rule() -> FixedRule:
    return FixedRule()
