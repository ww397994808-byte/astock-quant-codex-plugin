from __future__ import annotations

from pathlib import Path

import yaml


class ConfigValidator:
    REQUIRED = ["config/market_rules.yaml", "config/fees.yaml", "config/backtest.yaml", "config/risk.yaml", "config/qmt_config.example.yaml"]

    def validate(self) -> list[str]:
        issues = []
        for path in self.REQUIRED:
            p = Path(path)
            if not p.exists():
                issues.append(f"缺少配置文件：{path}")
            else:
                try:
                    yaml.safe_load(p.read_text(encoding="utf-8"))
                except Exception as exc:
                    issues.append(f"配置文件无法解析：{path} {exc}")
        return issues

