from __future__ import annotations

from core.run_manager import RunManager


def test_run_manager_creates_unique_runs_with_same_prefix(tmp_path):
    manager = RunManager(base_dir=tmp_path)
    first = manager.create_run("same")
    second = manager.create_run("same")

    assert first.run_id != second.run_id
    assert first.output_dir.exists()
    assert second.output_dir.exists()
