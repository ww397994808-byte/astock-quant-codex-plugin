from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_acquisition.symbol_resolver import SymbolResolver
from services.student_workflow_service import StudentWorkflowService


def test_symbol_resolver_rejects_crypto_for_astock_workflow():
    with pytest.raises(ValueError) as exc:
        SymbolResolver().resolve("BTCUSDT 日线突破策略")

    assert "非 A 股标的" in str(exc.value)
    assert "数字货币版本需要单独工作流" in str(exc.value)


def test_student_workflow_explains_wrong_asset_version(tmp_path: Path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)

    result = StudentWorkflowService().run(
        idea="BTCUSDT 日线突破策略，控制回撤",
        timeframe="1d",
        adjust="point_in_time_qfq",
    )

    assert result.status == "INVALID"
    workflow_dir = Path(result.report_path)
    manifest = json.loads((workflow_dir / "workflow_manifest.json").read_text(encoding="utf-8"))
    next_actions = (workflow_dir / "NEXT_ACTIONS.md").read_text(encoding="utf-8")

    assert manifest["steps"][0]["step"] == "resolve-symbol"
    assert manifest["steps"][0]["status"] == "INVALID"
    assert manifest["diagnostics"][0]["type"] == "wrong_asset_version"
    assert any("数字货币版本需要单独工作流" in warning for warning in manifest["steps"][0]["warnings"])
    assert "切换到正确资产版本" in next_actions
    assert "不能混用 A 股数据" in next_actions
    assert "QMT 只读还没有运行" not in next_actions
    assert "当前工作流不提供重跑命令" in next_actions
    assert 'student-workflow --idea "BTCUSDT' not in next_actions
