# Delivery Checklist

Use this checklist before publishing the plugin marketplace.

## Plugin Shell

- [x] Marketplace file exists at `.agents/plugins/marketplace.json`
- [x] Plugin manifest exists at `plugins/astock-quant-suite/.codex-plugin/plugin.json`
- [x] Plugin name is `astock-quant-suite`
- [x] Manifest points at `./skills/`

## Skill And Agent

- [x] Skill exists at `plugins/astock-quant-suite/skills/astock-quant-research/SKILL.md`
- [x] Agent metadata exists at `plugins/astock-quant-suite/skills/astock-quant-research/agents/openai.yaml`
- [x] Workflow references are included
- [x] Skill helper script is included

## Runtime

- [x] Runtime CLI exists at `plugins/astock-quant-suite/runtime/AI_AStock_Quant_System/cli.py`
- [x] Task layer is included
- [x] Services, audit, backtest, paper, QMT, validators, and tests are included
- [x] Sample data is included
- [x] Generated reports are excluded
- [x] Private QMT config is excluded

## Fixed Templates

- [x] QMT example config is included
- [x] Strategy templates are included
- [x] Backtest templates are included

## Guarded Scripts

- [x] `scripts/install_runtime.py`
- [x] `scripts/doctor.py`
- [x] `scripts/run_astock_cli.py`

## Safety Gates

- [x] Real trading defaults remain disabled
- [x] QMT readonly requires local config
- [x] Pretrade and handoff remain gated by runtime commands
- [x] Skill says bundled runtime is evidence collection, not trading permission
