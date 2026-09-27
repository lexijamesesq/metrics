---
tags:
  - type/claude-repo
description: "Claude Code skills for a design-metrics collection framework — NPS, UX bugs, and usage tracking via Pendo, Jira, and Google Sheets."
docs_home: "{workspace_root}/Projects/Metrics"
---

# Metrics

Three Claude Code skills (`/nps`, `/usage`, `/ux-bugs`) that collect design metrics from Pendo and Jira into structured data notes with a Google Sheets push. Public repo: a template other design leaders fork and configure for their own products, not just this operator's tracking.

## Setup

Clone the repo. `.claude/` ships tracked and committed — review its contents (see Security below) before opening the directory in Claude Code. Copy the instance config sample and fill in your own values:

```bash
cp .claude/instance.sample.md .claude/instance.md
cp pendo-config.sample.md pendo-config.md
cp jira-config.sample.md jira-config.md
```

See `.claude/instance.sample.md` for the full configuration contract (1Password credential path, Google Sheets URL, config file pointers) with placeholder values.

## Configuration

Skills read instance-specific values from `.claude/instance.md`'s Configuration section by key name, not hardcoded — `onepassword.pendo_api_key`, `sheets_config`, `spreadsheet_url`. Product-specific IDs (Pendo subscription/guide/poll/segment/page IDs, Jira cloud ID/project keys/custom fields) live in `pendo-config.md` and `jira-config.md`. All three are gitignored — every fork fills in its own.

## Build / Test

No build step (skills are markdown; scripts are stdlib-first Python). Local checks before pushing:

```bash
uvx ruff@latest check .     # Python scripts under NPS/, UX Bugs/
shellcheck **/*.sh          # if any shell scripts are added
pre-commit run --all-files  # gitleaks-staged + the standard hook set
```

## CI

`.github/workflows/ci.yml`, required via the "Protect main" ruleset through `all-checks-passed`: the estate's shared `floor` job, plus this repo's own `ruff` (Python lint) and `shellcheck` (`ludeeus/action-shellcheck`, no-op today — no `.sh` files yet, kept for when scripts are added). PR-time secret scanning is the trusted lane's `trusted-scan` (`gate.yml`), a separate required check.

## Conventions

- Skills are self-contained SKILL.md files under `.claude/skills/{name}/` — no shared runtime beyond the Configuration keys above and the `pendo-config.md`/`jira-config.md` product data.
- Instance-specific values are always config keys, never hardcoded — a skill that hardcodes an ID/URL breaks for every other fork.
- Python scripts are stdlib-first (`fetch-nps-responses.py` uses only stdlib + 1Password CLI for the API key) so they run standalone or as part of a skill pipeline with no dependency install step.
- Commits: gitleaks-staged/-pre-push/-commit-msg (dotty's exported hooks) gate every commit and push locally; `trusted-scan` re-scans the PR's commits, branch, title and body at PR time.
- `.claude/skills/xpl/` — if present locally, it never enters git. It's the operator's own financial/renewal-pipeline slide-prep skill, gitignored (`.claude/skills/xpl/` in `.gitignore`), colocated here only so it loads in the same session as the other skills.

## Key Files

| File | Purpose |
| ---- | ------- |
| `.claude/instance.sample.md` | Configuration contract template — copy to `.claude/instance.md` and fill in your instance's values |
| `.claude/skills/nps/` | `/nps` — monthly NPS analysis: REST API fetch, qualitative theme analysis, structured output |
| `.claude/skills/usage/` | `/usage` — monthly DAU/MAU collection for configured products via Pendo MCP |
| `.claude/skills/ux-bugs/` | `/ux-bugs` — quarterly UX bug metrics: priority breakdown, TTR compliance, Jira due date validation |
| `pendo-config.sample.md`, `jira-config.sample.md` | Per-fork product config templates — copy to the non-`.sample` name and fill in |
| `Infrastructure/` | Google Apps Script web app + deployment guide for the Sheets push |
