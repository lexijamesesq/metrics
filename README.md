A Claude Code project that tracks five design metrics -- NPS qualitative feedback, UX bugs, DAU/MAU usage, experimentation, and design system adoption -- to demonstrate Design's impact on product engagement and quality. Built for design leaders who need repeatable, automated metrics collection using Pendo, Jira, and Google Sheets, orchestrated through Claude Code skills.

## Installation

Clone the repo, then set up the Claude Code directory:

```
mv claude .claude
```

Copy the sample config and fill in your paths:

```
cp CLAUDE.sample.md CLAUDE.md
```

Copy the external config files and fill in your IDs:

```
cp pendo-config.sample.md pendo-config.md
cp jira-config.sample.md jira-config.md
```

### Required Configuration

**`CLAUDE.md`** (from `CLAUDE.sample.md`):
- `onepassword.pendo_api_key` -- 1Password item path for your Pendo REST API key (used by `/nps`)
- `spreadsheet_url` -- Google Sheets URL for your metrics spreadsheet
- `sheets_config` -- path to your deployed Apps Script web app URL file

**`pendo-config.md`** (from `pendo-config.sample.md`):
- `subscription_id` -- Pendo subscription ID
- NPS product entries with guide IDs, poll IDs, and surface filters
- Usage app entries with app IDs and entity types
- Segment IDs for teacher/student role breakdown
- Page IDs for page-level product tracking

**`jira-config.md`** (from `jira-config.sample.md`):
- `cloud_id` -- Atlassian Cloud ID
- `base_url` -- your Jira instance URL
- UX Bug project keys
- Custom field IDs for Salesforce count, requirement type, and JPD fields
- TTR (Time to Remediation) windows per priority level

### Optional Configuration

**Google Sheets push** requires deploying the included Apps Script web app. See `Infrastructure/metrics-api-deployment.md` for step-by-step instructions. If not configured, skills output data locally and skip the Sheets push silently.

## What's Included

### Skills

| Artifact | Type | Description |
|----------|------|-------------|
| `claude/skills/nps/SKILL.md` | Skill | Fetches NPS responses via Pendo REST API, cross-validates with MCP aggregate, performs qualitative theme analysis from CSV data, queries Jira for recently-completed features, and generates a monthly analysis document with structured data note |
| `claude/skills/usage/SKILL.md` | Skill | Collects MAU, DAU, and DAU/MAU ratio for all configured products via Pendo MCP, calculates month-over-month and year-over-year change, and writes individual data notes per product |
| `claude/skills/ux-bugs/SKILL.md` | Skill | Queries Jira for open and resolved UX bugs across configured projects, calculates quarterly metrics (priority breakdown, remediation rate, TTR compliance), validates and updates due dates in Jira, and writes quarterly data notes and TTR violation files |

### Scripts

| Artifact | Description |
|----------|-------------|
| `NPS/Scripts/fetch-nps-responses.py` | Fetches NPS poll responses from Pendo REST API, correlates numeric scores with text comments by visitor, outputs CSV (stdlib only, uses 1Password CLI for API key) |
| `NPS/Scripts/02_update_tracking.py` | Calculates NPS score and promoter/passive/detractor percentages from extracted CSV |
| `NPS/Scripts/01_extract_data.py` | Legacy CSV extraction fallback (retained for manual download workflow) |
| `NPS/Scripts/lib/data_processing.py` | Shared NPS calculation library (score computation, response grouping) |
| `UX Bugs/Scripts/collect-ux-bugs.py` | Core quarterly calculation logic for UX bug metrics (referenced by skill) |

### Infrastructure

| Artifact | Description |
|----------|-------------|
| `Infrastructure/metrics-api-appscript.js` | Google Apps Script web app that accepts POST requests and upserts NPS, Usage, and UX Bugs data into Google Sheets |
| `Infrastructure/metrics-api-deployment.md` | Step-by-step deployment guide for the Apps Script web app |

### Process Documentation

| Artifact | Description |
|----------|-------------|
| `UX Bugs/Process/ux-bug-priority-levels.md` | P1-P4 priority definitions and TTR window criteria |

## Configuration

Skills read configuration at runtime from three sources:

1. **`CLAUDE.md`** -- project-level config (1Password path, Sheets URL). Skills read the `## Configuration` section by key name.
2. **`pendo-config.md`** -- all Pendo connection details, product definitions, segment IDs, and page IDs. Used by `/nps` and `/usage`.
3. **`jira-config.md`** -- Atlassian connection, project keys, custom field IDs, and TTR windows. Used by `/ux-bugs` and `/nps`.

The `.sample.md` versions of each file are tracked in the repo with placeholder values. The actual config files are gitignored. Copy the samples, fill in your values, and the skills will find them at the project root.

### Data Architecture

- **Source of truth:** Individual structured notes in `{Metric}/Tracking/` with YAML frontmatter
- **Google Sheets:** Derived output pushed automatically by each skill (non-blocking -- local notes are written regardless)
- **Analysis documents:** Monthly markdown files in `{Metric}/Analysis/` (NPS only)
- **JSON snapshots:** Immutable monthly snapshots in `{Metric}/Data/` (UX Bugs)

## Usage

### Monthly: Collect Usage Metrics

```
/usage 2026-02
```

Collects MAU, DAU, and engagement ratio for all configured products. Takes ~2-3 minutes. Defaults to previous month if no argument given.

### Monthly: Run NPS Analysis

```
/nps 2026-02 mc
/nps 2026-02 cq
```

Runs the full NPS pipeline for one product: REST API fetch, metric calculation, qualitative theme analysis, and structured output. Takes ~25-45 minutes per product. Both arguments (month and product short code) are required.

### Quarterly: Collect UX Bug Metrics

```
/ux-bugs
/ux-bugs 2026-03-31
```

Queries Jira for all UX bugs, calculates quarterly metrics, validates TTR due dates, and optionally updates Jira. Takes ~30-45 minutes. Defaults to today's date.

### Manual Updates

Experimentation and Design System metrics are updated manually by the team in the Google Sheet. No skills are provided for these -- the spreadsheet tabs exist and are populated directly.

## Security

Review skills before installing. They load into Claude's context and execute with your permissions. Audit the contents of `claude/skills/` before use.

The `/nps` skill accesses your Pendo API key via 1Password CLI -- it never stores the key in a file. The `/ux-bugs` skill can update Jira issues (due dates and comments) when you approve the changes during a run.

Config files containing your org-specific IDs (`pendo-config.md`, `jira-config.md`, `Infrastructure/sheets-api-config.md`) are gitignored. Only the `.sample.md` templates are tracked.

## License

MIT License. See [LICENSE](LICENSE) for details.
