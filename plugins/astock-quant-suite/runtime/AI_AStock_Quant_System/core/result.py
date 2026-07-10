from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskResult:
    status: str
    message: str
    run_id: str | None = None
    report_path: str | None = None
    audit_status: str | None = None
    warnings: list[str] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
