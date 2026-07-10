from __future__ import annotations

from pathlib import Path

import yaml

from services.qmt_config_init_service import QMTConfigInitService


def test_qmt_config_init_writes_safe_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "qmt_config.example.yaml").write_text(
        "dry_run: false\nenable_real_trade: true\naccount_id: old\nmini_qmt_path: old\n",
        encoding="utf-8",
    )

    result = QMTConfigInitService().run(account_id="acct", mini_qmt_path="/mini/qmt", session_id=789)

    assert result.status == "VALID"
    config = yaml.safe_load((tmp_path / "config" / "qmt_config.yaml").read_text(encoding="utf-8"))
    assert config["dry_run"] is True
    assert config["enable_real_trade"] is False
    assert config["account_id"] == "acct"
    assert config["mini_qmt_path"] == "/mini/qmt"
    assert config["session_id"] == 789
    assert Path(result.report_path, "QMT_CONFIG_INIT.md").exists()


def test_qmt_config_init_refuses_overwrite_without_force(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "config" / "qmt_config.yaml"
    config.parent.mkdir()
    config.write_text("dry_run: true\nenable_real_trade: false\naccount_id: keep\n", encoding="utf-8")

    result = QMTConfigInitService().run(account_id="new")

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "CONFIG_EXISTS"
    assert yaml.safe_load(config.read_text(encoding="utf-8"))["account_id"] == "keep"


def test_qmt_config_init_force_still_keeps_real_trade_off(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "config" / "qmt_config.yaml"
    config.parent.mkdir()
    config.write_text("dry_run: false\nenable_real_trade: true\naccount_id: risky\n", encoding="utf-8")

    result = QMTConfigInitService().run(force=True)

    assert result.status == "VALID"
    updated = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert updated["dry_run"] is True
    assert updated["enable_real_trade"] is False
