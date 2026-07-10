from __future__ import annotations

from pathlib import Path

from services.qmt_config_status_service import QMTConfigStatusService


def test_qmt_config_status_suggests_init_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = QMTConfigStatusService().run()

    assert result.status == "VALID"
    assert result.artifacts["status"] == "NEEDS_QMT_CONFIG"
    assert result.artifacts["next_command"] == "python3 cli.py qmt-config-init"
    assert Path(result.report_path, "QMT_CONFIG_STATUS.md").exists()


def test_qmt_config_status_warns_for_missing_account_and_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "config" / "qmt_config.yaml"
    config.parent.mkdir()
    config.write_text("dry_run: true\nenable_real_trade: false\naccount_id: ''\nmini_qmt_path: ''\n", encoding="utf-8")

    result = QMTConfigStatusService().run()

    assert result.status == "VALID"
    assert result.artifacts["status"] == "NEEDS_QMT_CONFIG"
    assert result.artifacts["can_run_qmt_check"] is False
    warning_ids = {item["id"] for item in result.artifacts["warnings"]}
    assert {"account_id", "mini_qmt_path"} <= warning_ids


def test_qmt_config_status_blocks_unsafe_switches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "config" / "qmt_config.yaml"
    config.parent.mkdir()
    config.write_text("dry_run: false\nenable_real_trade: true\naccount_id: x\nmini_qmt_path: /tmp\n", encoding="utf-8")

    result = QMTConfigStatusService().run()

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BLOCKED_UNSAFE_QMT_CONFIG"
    blocker_ids = {item["id"] for item in result.artifacts["blockers"]}
    assert {"dry_run", "enable_real_trade"} <= blocker_ids
    assert result.artifacts["next_command"] == "python3 cli.py qmt-config-init --force"


def test_qmt_config_status_ready_when_config_complete(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mini = tmp_path / "mini_qmt"
    mini.mkdir()
    config = tmp_path / "config" / "qmt_config.yaml"
    config.parent.mkdir()
    config.write_text(
        f"dry_run: true\nenable_real_trade: false\naccount_id: acct\nmini_qmt_path: {mini}\n",
        encoding="utf-8",
    )

    result = QMTConfigStatusService().run()

    assert result.status == "VALID"
    assert result.artifacts["status"] == "READY_FOR_QMT_READONLY"
    assert result.artifacts["can_run_qmt_check"] is True
    assert result.artifacts["next_command"] == "python3 cli.py qmt-check"
    assert result.artifacts["action_cards"][0]["id"] == "run_qmt_check"
