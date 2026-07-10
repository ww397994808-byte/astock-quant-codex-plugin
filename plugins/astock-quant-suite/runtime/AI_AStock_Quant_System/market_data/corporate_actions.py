from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class CorporateAction:
    symbol: str
    ex_date: datetime
    known_date: datetime
    action_type: str
    cash_dividend: float = 0.0
    bonus_share_ratio: float = 0.0
    transfer_share_ratio: float = 0.0
    rights_issue_ratio: float = 0.0
    rights_issue_price: float = 0.0
    split_ratio: float = 0.0
    source: str = "csv"


def load_corporate_actions(path: str | Path, symbol: str | None = None) -> list[CorporateAction]:
    path = Path(path)
    actions = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if symbol and row["symbol"] != symbol:
                continue
            actions.append(CorporateAction(
                symbol=row["symbol"],
                ex_date=datetime.strptime(row["ex_date"], "%Y-%m-%d"),
                known_date=datetime.strptime(row["known_date"], "%Y-%m-%d"),
                action_type=row.get("action_type", "dividend"),
                cash_dividend=float(row.get("cash_dividend") or 0),
                bonus_share_ratio=float(row.get("bonus_share_ratio") or 0),
                transfer_share_ratio=float(row.get("transfer_share_ratio") or 0),
                rights_issue_ratio=float(row.get("rights_issue_ratio") or 0),
                rights_issue_price=float(row.get("rights_issue_price") or 0),
                split_ratio=float(row.get("split_ratio") or 0),
                source=row.get("source", "csv"),
            ))
    return sorted(actions, key=lambda x: (x.ex_date, x.known_date))

def write_sample_corporate_actions(path: str | Path, symbol: str = "601088.SH") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["symbol", "ex_date", "known_date", "action_type", "cash_dividend", "bonus_share_ratio", "transfer_share_ratio", "rights_issue_ratio", "rights_issue_price", "split_ratio", "source"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({"symbol": symbol, "ex_date": "2024-03-15", "known_date": "2024-03-10", "action_type": "cash_dividend", "cash_dividend": 0.8, "bonus_share_ratio": 0, "transfer_share_ratio": 0, "rights_issue_ratio": 0, "rights_issue_price": 0, "split_ratio": 0, "source": "sample"})
    return path

