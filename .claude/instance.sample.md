# Design Metrics Framework — [YOUR_PRODUCT_AREA]

Copy to `.claude/instance.md` and fill in your values — gitignored, one per fork. This is instance/state scaffolding for your own metrics setup, separate from the repo's own `CLAUDE.md` (which orients a session working on the skills themselves).

**Owner:** [YOUR_NAME] ([YOUR_TITLE])
**Timeline:** Initiated [START_DATE], ongoing monthly/quarterly tracking

---

## Project State

**Last Updated:** [DATE]

### Re-entry Cue
[What is the current state? What was the last thing you did?]

### Operational Status
- TODO: Track operational status per metric (NPS, UX Bugs, Usage, Experimentation, Design System)

### Next Steps (Prioritized)
1. TODO

### Blocked / Pending
- TODO

---

## Knowledge Sources & Prioritization

Two fork-local folders (gitignored — see this repo's `.gitignore`) hold your own synthesis, not the operator's:

- **`Knowledge/`** — durable reference docs (methodology notes, framework decisions, per-product quirks). When a session produces synthesis worth keeping, file it here rather than leaving it in chat history.
- **`Context/`** — per-backlog-item scratch only, not persistent knowledge. Empty at steady state.

### Writing posture

These docs exist for me to load context efficiently across sessions; you are a secondary reader. Terse and dense over polished prose, tables over paragraphs, no hesitation to prune.

### Reading posture

When I load a `Knowledge/` page, I check its `updated` frontmatter. Older than 90 days: surface the staleness before relying on the content — validate against live data sources (Pendo, Jira) and bump `updated` if still accurate, or edit/delete if not.

---

## Configuration

Values referenced by skills at runtime. Skills read these from this section by key name.

### Credentials

```yaml
onepassword.pendo_api_key: op://YOUR_VAULT/YOUR_ITEM/credential
```

> The 1Password item path for your Pendo REST API key. The `/nps` skill uses this to fetch NPS response data.

### Google Sheets

```yaml
sheets_config: Infrastructure/sheets-api-config.md
spreadsheet_url: https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit
```

> **sheets_config:** Path to the file containing your deployed Apps Script web app URL. Create this file after deploying `Infrastructure/metrics-api-appscript.js` (see `Infrastructure/metrics-api-deployment.md`).
> **spreadsheet_url:** Direct link to your metrics spreadsheet. Used in NPS analysis document links.

### External Config Files

Skills read product-specific IDs from these config files at Step 0. Copy the `.sample.md` versions and fill in your values:

- `pendo-config.md` (from `pendo-config.sample.md`) — Pendo subscription ID, guide IDs, poll IDs, segment IDs, page IDs, YoY lookup table. Used by `/nps` and `/usage`.
- `jira-config.md` (from `jira-config.sample.md`) — Atlassian cloud ID, base URL, project keys, custom field IDs, JPD field IDs. Used by `/ux-bugs` and `/nps`.

Referenced by: `/nps`, `/usage`, `/ux-bugs`.

---

## Key Files

| File | Purpose |
|------|---------|
| `.claude/instance.sample.md` | This file — copy to `.claude/instance.md` and fill in your instance's values |
| `.claude/skills/nps/SKILL.md` | `/nps` skill for monthly NPS analysis (REST API + MCP pipeline) |
| `.claude/skills/usage/SKILL.md` | `/usage` skill for monthly DAU/MAU collection via Pendo MCP |
| `.claude/skills/ux-bugs/SKILL.md` | `/ux-bugs` skill for quarterly UX Bug metrics via Atlassian MCP |
| `NPS/Scripts/fetch-nps-responses.py` | REST API fetch script (stdlib only, 1Password for API key) |
| `UX Bugs/Process/ux-bug-priority-levels.md` | P1-P4 priority definitions and TTR window criteria |
| `Infrastructure/metrics-api-appscript.js` | Google Apps Script web app for Sheets push |
| `Infrastructure/metrics-api-deployment.md` | Deployment guide for the Apps Script API |

## File Naming Convention

Hybrid naming:
- **Folders:** Mac-style (spaces, proper capitalization) — e.g., "Product Name"
- **Files:** kebab-case (lowercase, hyphens) — e.g., "mc-nps-analysis-202601.md"

## Workflow Cadence

### Monthly (Skill-Based Collection)

**Usage / DAU-MAU (All products):**
1. Run `/usage [YYYY-MM]` (~2-3 min total via Pendo MCP)

**UX Bugs (per Jira project):**
1. Run `/ux-bugs` (~30-45 min via Atlassian MCP)
2. Review and approve TTR due date updates

**NPS Analysis (per product):**
1. Run `/nps [YYYY-MM] [product]` (~25-45 min per product)

### Quarterly (End of quarter)
1. Create NPS quarterly rollup (synthesize 3 months)
2. Identify strategic patterns and recommendations

### Manual Team Updates (Ongoing)
- **Experiments:** Design team updates Google Sheets as experiments run
- **Design System:** Engineering or Design team updates adoption percentages
