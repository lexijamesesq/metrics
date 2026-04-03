A Claude Code project that tracks five design metrics -- NPS qualitative feedback, UX bugs, DAU/MAU usage, experimentation, and design system adoption -- to demonstrate Design's impact on product engagement and quality. Built for design leaders who need repeatable, automated metrics collection using Pendo, Jira, and Google Sheets, orchestrated through Claude Code skills.

## Installation

Clone the repo, then set up the Claude Code directory:

```
mv claude .claude
```

Copy the sample configs and fill in your values:

```
cp CLAUDE.sample.md CLAUDE.md
cp pendo-config.sample.md pendo-config.md
cp jira-config.sample.md jira-config.md
```

### Required configuration

| Field | Location | What to set |
|-------|----------|-------------|
| `onepassword.pendo_api_key` | `CLAUDE.md` | 1Password item path for your Pendo REST API key |
| `spreadsheet_url` | `CLAUDE.md` | Google Sheets URL for your metrics spreadsheet |
| `sheets_config` | `CLAUDE.md` | Path to your deployed Apps Script web app URL file |
| `subscription_id` | `pendo-config.md` | Your Pendo subscription ID |
| NPS product entries | `pendo-config.md` | Guide IDs, poll IDs, and surface filters per product |
| Usage app entries | `pendo-config.md` | App IDs, entity types, segment IDs, and page IDs |
| `cloud_id` | `jira-config.md` | Your Atlassian Cloud ID |
| `base_url` | `jira-config.md` | Your Jira instance URL |
| UX Bug project keys | `jira-config.md` | Jira project keys to track |
| Custom field IDs | `jira-config.md` | Salesforce count, requirement type, JPD fields |
| TTR windows | `jira-config.md` | Time to Remediation days per priority level |

### Optional configuration

| Field | Location | What to set |
|-------|----------|-------------|
| Google Sheets push | `Infrastructure/sheets-api-config.md` | Deploy the included Apps Script (`metrics-api-appscript.js`), then save the web app URL. See `metrics-api-deployment.md` for instructions. If not configured, skills output data locally and skip the Sheets push silently. |
| YoY lookup table | `pendo-config.md` | Historical MAU data for year-over-year calculations when Pendo tracking notes don't cover the prior year. Only needed if you migrated analytics sources mid-stream. |
| JPD fields | `jira-config.md` | Jira Product Discovery project key and custom fields for the NPS feature watch list. If not configured, the watch list step is skipped. |

## What's Included

### Skills

| Skill | What it does | Details |
|-------|--------------|---------|
| `/nps` | Monthly NPS analysis -- REST API fetch, qualitative theme analysis, structured output | [NPS/README.md](NPS/README.md) |
| `/usage` | Monthly DAU/MAU collection for all configured products via Pendo MCP | [Usage/README.md](Usage/README.md) |
| `/ux-bugs` | Quarterly UX bug metrics -- priority breakdown, TTR compliance, Jira due date validation | [UX Bugs/README.md](UX%20Bugs/README.md) |

### Supporting files

| Artifact | Type | What it does |
|----------|------|--------------|
| `NPS/Scripts/fetch-nps-responses.py` | Script | Fetches NPS responses from Pendo REST API, correlates scores with comments, outputs CSV |
| `NPS/Scripts/02_update_tracking.py` | Script | Calculates NPS metrics from extracted CSV |
| `UX Bugs/Scripts/collect-ux-bugs.py` | Script | Quarterly bug calculation logic -- reference implementation for the `/ux-bugs` skill |
| `Infrastructure/metrics-api-appscript.js` | Apps Script | Google Sheets web app for automated data push (upsert by product + period) |
| `Infrastructure/metrics-api-deployment.md` | Guide | Step-by-step Apps Script deployment instructions |
| `UX Bugs/Process/ux-bug-priority-levels.md` | Reference | P1-P4 priority definitions and TTR window criteria |

## Configuration

Skills read configuration at runtime from three sources:

**You configure:** `CLAUDE.md` (project-level settings like 1Password path and Sheets URL), `pendo-config.md` (all Pendo IDs -- subscriptions, guides, polls, segments, pages), and `jira-config.md` (Atlassian connection, project keys, custom fields, TTR windows).

**Skills handle:** Reading the config files at Step 0, validating that required values exist, stopping with setup instructions if a config file is missing, and referencing values by name throughout execution.

See `CLAUDE.sample.md`, `pendo-config.sample.md`, and `jira-config.sample.md` for the complete configuration surface with documentation for every field.

## Usage

### Monthly: usage metrics

Collects MAU, DAU, and engagement ratio for all configured products. Takes ~2-3 minutes. Defaults to previous month if no argument given.

```
/usage 2026-02
```

### Monthly: NPS analysis

Runs the full NPS pipeline for one product: REST API fetch, metric calculation, qualitative theme analysis, and structured output. Takes ~25-45 minutes per product. Both arguments (month and product short code) required.

```
/nps 2026-02 mc
```

### Quarterly: UX bug metrics

Queries Jira for all UX bugs, calculates quarterly metrics, validates TTR due dates, and optionally updates Jira. Takes ~30-45 minutes. Defaults to today's date.

```
/ux-bugs
```

### Manual updates

Experimentation and Design System metrics are updated manually by the team in the Google Sheet. No skills are provided for these -- the spreadsheet tabs exist and are populated directly.

## How It Works

Three skills collect metrics from two external platforms (Pendo and Jira) and write structured data notes with YAML frontmatter. Each skill runs independently -- invoke whichever metrics you need, on whatever cadence works for your team.

The data architecture has three layers. Individual structured notes in `{Metric}/Tracking/` are the source of truth, with YAML frontmatter matching the Google Sheet schema. Google Sheets is a derived output pushed automatically by each skill at the end of a run (non-blocking -- local notes are written regardless). NPS analysis documents are monthly markdown files with qualitative theme analysis, evidence-based insights, and forward-looking signals.

Each skill reads its configuration at Step 0 from markdown config files at the project root. Pendo skills read `pendo-config.md`; Jira skills read `jira-config.md`; both check `CLAUDE.md` for project-level settings. If a config file is missing, the skill stops with setup instructions rather than failing silently.

The Python scripts handle data fetching (REST API) and calculation (NPS metrics, quarterly bug aggregation). Skills invoke them with config values passed as CLI arguments, so the scripts work standalone or as part of the skill pipeline.

## Customization

- **Different products or platforms:** Edit `pendo-config.md` to add your product entries with the correct Pendo IDs. The `/usage` skill demonstrates three query patterns (visitor-level, page-level single, page-level multi) -- adapt the steps to match your products' Pendo configuration.
- **Without Google Sheets:** Skip the Apps Script deployment. Skills write local data notes regardless and skip the Sheets push silently when `sheets-api-config.md` is absent.
- **Without Jira / JPD:** The `/nps` skill's JPD watch list step is non-blocking -- if Jira config is missing or the query returns no results, the analysis proceeds without feature context. The `/ux-bugs` skill requires Jira.
- **Different TTR windows:** Edit `jira-config.md` to set priority-to-days mappings that match your organization's SLA commitments.

## Security

Review skills before installing. They load into Claude's context and execute with your permissions. Audit the contents of `claude/skills/` before use.

The `/nps` skill accesses your Pendo API key via 1Password CLI -- it never stores the key in a file. The `/ux-bugs` skill can update Jira issues (due dates and comments) when you approve the changes during a run. Config files containing your org-specific IDs are gitignored.

## License

MIT. See [LICENSE](LICENSE).
