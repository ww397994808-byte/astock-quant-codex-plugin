from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class RunContext:
    run_id: str
    timestamp: str
    output_dir: Path
    log_dir: Path


class RunManager:
    def __init__(self, base_dir: str | Path = "reports") -> None:
        self.base_dir = Path(base_dir)

    def create_run(self, prefix: str = "run") -> RunContext:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        counter = 1
        while True:
            run_id = f"{prefix}_{timestamp}" if counter == 1 else f"{prefix}_{timestamp}_{counter - 1}"
            output_dir = self.base_dir / run_id
            log_dir = output_dir / "logs"
            try:
                output_dir.mkdir(parents=True, exist_ok=False)
                log_dir.mkdir(parents=True, exist_ok=True)
                break
            except FileExistsError:
                counter += 1
                continue
        self._write_latest(run_id)
        return RunContext(run_id=run_id, timestamp=timestamp, output_dir=output_dir, log_dir=log_dir)

    def resolve_run_dir(self, run_id: str) -> Path:
        if run_id == "latest":
            run_id = self.latest_run_id()
        path = self.base_dir / run_id
        if not path.exists():
            raise FileNotFoundError(f"找不到运行结果：{run_id}。请先运行 backtest/optimize/paper。")
        return path

    def latest_run_id(self) -> str:
        marker = self.base_dir / "latest.txt"
        if marker.exists():
            return marker.read_text(encoding="utf-8").strip()
        runs = sorted([p.name for p in self.base_dir.glob("*") if p.is_dir()])
        if not runs:
            raise FileNotFoundError("还没有任何运行结果。")
        return runs[-1]

    def _write_latest(self, run_id: str) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        (self.base_dir / "latest.txt").write_text(run_id, encoding="utf-8")
