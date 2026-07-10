# Hard Constraints

The suite must enforce safety in executable code, not only in prompt instructions.

## Runtime Gates

- `student-course-path`, `student-idea-preflight`, and `student-backtest-plan-precheck` must run before beginner workflows.
- `student-future-leak-precheck` blocks obvious future data, centered windows, negative shifts, future labels, and unsafe code patterns.
- `student-workflow` must generate workflow evidence before promotion.
- `stage-check` must stop promotion when audit, data, paper, or QMT evidence is incomplete.
- `student-run-next` must allow only its safe command whitelist and must refuse live-trade, pretrade, sandbox, or handoff shortcuts when not explicitly allowed.
- `qmt-config-init` must create safe config with `dry_run=true` and `enable_real_trade=false`.
- `qmt-config-status` must refuse QMT readonly when `account_id` or `mini_qmt_path` is missing or unsafe.
- `qmt-check` is readonly evidence only. It is not trading approval.
- `pretrade-package`, `pretrade-runbook-refresh`, and `pretrade-check` are required before any handoff draft.
- `qmt-handoff` and batch handoff commands create auditable drafts only.

## Asset Boundary

This package is the A-share/QMT version. It must not reuse A-share assumptions for crypto, perpetuals, USDT, offshore exchanges, or digital currencies.

## Data Boundary

Sample data is for teaching and deterministic smoke tests. Real research must document data source, adjustment policy, missing data, suspensions, price limits, and point-in-time constraints.

## Real Trading Boundary

Installation, doctor checks, student workflows, QMT config status, QMT readonly checks, pretrade packages, handoff drafts, order sandbox, lifecycle, and daily review do not grant live-trading permission. Real trading requires separate local operator confirmation and must not be silently enabled by Codex.
