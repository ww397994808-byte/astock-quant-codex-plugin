from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class FeeBreakdown:
    commission: float
    stamp_tax: float
    transfer_fee: float

    @property
    def total(self) -> float:
        return round(self.commission + self.stamp_tax + self.transfer_fee, 6)


class FeeCalculator:
    def __init__(self, config_path: str | Path = "config/fees.yaml") -> None:
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> dict:
        if self.config_path.exists():
            return yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        return {
            "commission_rate": 0.0003,
            "min_commission": 5.0,
            "stamp_tax_rate": 0.0005,
            "transfer_fee_rate": 0.00001,
            "allow_zero_fee": False,
        }

    def calculate(self, action: str, price: float, quantity: int) -> FeeBreakdown:
        amount = price * quantity
        commission = max(amount * float(self.config.get("commission_rate", 0.0003)), float(self.config.get("min_commission", 5.0)))
        stamp_tax = amount * float(self.config.get("stamp_tax_rate", 0.0005)) if action == "SELL" else 0.0
        transfer_fee = amount * float(self.config.get("transfer_fee_rate", 0.00001))
        fees = FeeBreakdown(round(commission, 6), round(stamp_tax, 6), round(transfer_fee, 6))
        if fees.total <= 0 and not bool(self.config.get("allow_zero_fee", False)):
            raise ValueError("手续费为 0，配置未显式允许，禁止继续。")
        return fees

