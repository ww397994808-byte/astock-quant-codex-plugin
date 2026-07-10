# AStock Quant Suite Package Manifest

This plugin is designed as a complete local delivery package for Chinese A-share quant research.

## Included

- Codex plugin manifest: `.codex-plugin/plugin.json`
- Marketplace entry: `.agents/plugins/marketplace.json`
- Skill: `skills/astock-quant-research/SKILL.md`
- Agent metadata: `skills/astock-quant-research/agents/openai.yaml`
- Skill references: workflow, future-leak rules, strategy archetypes, paper observation, QMT gate
- Helper script: `skills/astock-quant-research/scripts/run_astock_workflow.py`
- Runtime: `runtime/AI_AStock_Quant_System/`
- Fixed templates: `templates/backtest_templates/`, `templates/strategies/`, `templates/config/`
- Plugin scripts: `scripts/install_runtime.py`, `scripts/doctor.py`, `scripts/run_astock_cli.py`
- Runtime tests under `runtime/AI_AStock_Quant_System/tests/`

## Deliberately Excluded

- User-local QMT config: `config/qmt_config.yaml`
- Generated reports and ledgers
- Large downloaded market data
- Local caches and Python bytecode
- Any real-trade confirmation state

## Default Safety State

- `dry_run=true`
- `enable_real_trade=false`
- Real trading is not enabled by installation.
- QMT access starts with config status and readonly checks.
- Pretrade and handoff commands only create evidence packages and guarded drafts.
