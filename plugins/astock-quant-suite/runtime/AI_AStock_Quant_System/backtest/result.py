from dataclasses import dataclass
from pathlib import Path


@dataclass
class BacktestResult:
    run_id: str
    output_dir: Path
    status: str
    performance: dict
    audit_status: str

