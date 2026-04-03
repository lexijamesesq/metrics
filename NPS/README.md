# /nps -- Monthly NPS Analysis

Runs the complete NPS monthly analysis workflow for one product. Fetches NPS data via Pendo REST API, cross-validates with MCP aggregate score, queries Jira for recently-completed features as context, performs qualitative theme analysis from CSV data, and generates a structured analysis document with data note.

## Invocation

```
/nps 2026-02 mc
```

Both arguments required: month (`YYYY-MM`) and product short code (must match a product key in `pendo-config.md`). Takes ~25-45 minutes per product.

## What it produces

- **NPS CSV:** Raw response data in `NPS/Data/{product}/nps-{YYYY-MM}.csv`
- **Analysis document:** Monthly markdown in `NPS/Analysis/{product}/{short}-nps-analysis-{YYYYMM}.md` with Summary, Top Pain Points, 3 Things That Matter, What's Working, and The Signal sections
- **Data note:** Structured YAML frontmatter in `NPS/Tracking/{short}-nps-{YYYY-MM}.md` with score, response count, segment percentages, MoM change, and interpretation
- **Google Sheets push:** NPS metrics posted to the NPS_Data tab (non-blocking)

## Analysis methodology

The skill enforces an evidence-based analysis pipeline:

1. **Evidence Base (Step 5):** All comments are read and themed before any analysis begins. Themes are identified organically from user language -- no hardcoded categories. The evidence base is locked before Step 6 proceeds.
2. **Quote constraint:** Every quoted string in the analysis document must appear in the locked evidence base. No quotes may be introduced during writing.
3. **The Signal:** A forward-looking section that raises a testable hypothesis the next month's run will confirm or refute. Not a summary -- a trajectory question with a specific confirmation condition.

## Configuration

This skill reads three config sources at Step 0:

| Source | Required fields |
|--------|----------------|
| `pendo-config.md` | `subscription_id`, product entry with `guide_id`, `numeric_poll_id`, `text_poll_id`, `surface_filter` |
| `jira-config.md` | `cloud_id`, JPD `project_key`, `surface_area` and `target_quarter` field IDs (optional -- watch list is non-blocking) |
| `CLAUDE.md` | `onepassword.pendo_api_key`, `spreadsheet_url` |

## Scripts

| Script | What it does |
|--------|--------------|
| `fetch-nps-responses.py` | Fetches NPS poll responses from Pendo REST API. Accepts `--guide-id`, `--numeric-poll-id`, `--text-poll-id`, `--op-item` for portability. Stdlib only. |
| `02_update_tracking.py` | Calculates NPS score and segment percentages from CSV |
| `01_extract_data.py` | Legacy fallback for manual CSV download workflow |
| `lib/data_processing.py` | Shared NPS calculation library |

## Prerequisites

- Pendo MCP server configured in Claude Code
- 1Password CLI installed and authenticated (`op signin`)
- Atlassian MCP server (optional -- for JPD feature watch list)
- `pendo-config.md` and `CLAUDE.md` populated
