---
tags:
  - type/claude-project
  - project/metrics
status: active
description: >-
  Design metrics framework tracking NPS, UX bugs, usage, experimentation, and
  design system adoption for [YOUR_ORG/PRODUCT_AREA].
---
# Design Metrics Framework - [YOUR_PRODUCT_AREA]

## Project Overview

This project establishes a metrics framework for demonstrating Design's impact on [YOUR_PRODUCTS]. The framework tracks 5 key metrics demonstrating Design's focus on **usage and experimentation**.

**Owner:** [YOUR_NAME] ([YOUR_TITLE])
**Timeline:** Initiated [START_DATE], ongoing monthly/quarterly tracking

## The Five Metrics

**Update Mechanism:**
- **Claude Code Skills:** NPS (`/nps`), UX Bugs (`/ux-bugs`), Usage (`/usage`) — skill-based invocation with structured data notes
- **Manual Team Updates:** Experiments, Design System (spreadsheet tabs exist, populated by team)

**Data Architecture:**
- Individual structured notes per data point in `Data/` (YAML frontmatter matching Google Sheet schema)
- Obsidian Bases for local dashboards (auto-aggregate from frontmatter)
- `spreadsheet-ready.md` files regenerated from data notes each run (derived, not source of truth)
- Skills at `claude/skills/{name}/SKILL.md`

### 1. NPS Qualitative Feedback
**What:** Net Promoter Score comment analysis to identify pain points and feature reception
**Why:** Direct user voice on Design quality and feature impact
**Update Method:** Claude Code (REST API fetch + MCP theme clustering + qualitative analysis)

**Status:**
- TODO: Operational status for your products

**Key docs:**
- `claude/skills/nps/SKILL.md` - Production skill
- `NPS/Scripts/fetch-nps-responses.py` - REST API fetch script (stdlib only, 1Password for API key)
- `NPS/portability-notes.md` - Cross-domain portability analysis

### 2. UX Bugs
**What:** Customer-reported bugs with UX impact, tracked via Jira "Requirement Type = UX"
**Why:** Demonstrates Design accountability for quality and user experience
**Update Method:** Claude Code (queries Atlassian MCP)

**Status:**
- TODO: Operational status for your projects

**Key docs:**
- `claude/skills/ux-bugs/SKILL.md` - Production skill
- `UX Bugs/Process/ux-bug-priority-levels.md` - P1/P2/P3 criteria and TTR windows

### 3. Usage / DAU-MAU
**What:** Daily/Monthly Active Users metrics from Pendo
**Why:** Design's influence on engagement
**Update Method:** Claude Code via Pendo MCP

**Status:**
- TODO: Operational status

**Key docs:**
- `claude/skills/usage/SKILL.md` - Production skill
- `Usage/Process/mcp-collection-guide.md` - Pendo MCP query reference

### 4. Experimentation
**What:** A/B test and design experiment tracking
**Why:** Data-driven design decisions
**Update Method:** Manual team updates

**Status:**
- TODO

### 5. Design System Usage
**What:** % of UI based on your design system components
**Why:** Design system adoption, consistency, efficiency
**Update Method:** Manual team updates

**Status:**
- TODO

## Configuration

Values referenced by skills at runtime. Skills read these from this section by key name.

### Credentials

onepassword.pendo_api_key: op://YOUR_VAULT/YOUR_ITEM/credential

> The 1Password item path for your Pendo REST API key. The `/nps` skill uses this to fetch NPS response data.

### Google Sheets

sheets_config: Infrastructure/sheets-api-config.md
spreadsheet_url: https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit

> **sheets_config:** Path to the file containing your deployed Apps Script web app URL. Create this file after deploying `Infrastructure/metrics-api-appscript.js` (see deployment guide).
> **spreadsheet_url:** Direct link to your metrics spreadsheet. Used in NPS analysis document links.

### External Config Files

Skills read product-specific IDs from these config files at Step 0. Copy the `.sample.md` versions and fill in your values:

- `pendo-config.md` (from `pendo-config.sample.md`) — Pendo subscription ID, guide IDs, poll IDs, segment IDs, page IDs, YoY lookup table. Used by `/nps` and `/usage`.
- `jira-config.md` (from `jira-config.sample.md`) — Atlassian cloud ID, base URL, project keys, custom field IDs, JPD field IDs. Used by `/ux-bugs` and `/nps`.

## Project State

**Last Updated:** [DATE]

### Re-entry Cue
[What is the current state? What was the last thing you did?]

### Operational Status
- TODO: Track operational status per metric

### Next Steps (Prioritized)
1. TODO

### Blocked / Pending
- TODO

## Knowledge Sources & Prioritization

When I need information about how this metrics framework works, I consult these in order:

1. **Live data sources** — your analytics MCP tools. Query, never assume. Current data is always authoritative.
2. **Skills** — collection skills at `claude/skills/`. These contain execution logic, config resolution, and workflow.
3. **Knowledge/** — project-level reference docs. See `Knowledge/index.md` for the current inventory.
4. **Domain-specific process docs** — per-metric `Process/` directories. Co-located with their metric data.

### Writing posture

These docs exist for me to load context efficiently across sessions; the user is a secondary reader. Terse and dense over polished prose, tables over paragraphs, no hesitation to prune.

### Reading posture

When I load a `Knowledge/` page during project work, I check its frontmatter `updated`. If older than 90 days, I surface the staleness before relying on the content — validate against current data sources and bump `updated` if still accurate, or edit/delete if not.

### Operations

- **Query-and-file** — when a session produces durable synthesis, file it as a `Knowledge/` page and update `index.md`. Don't leave synthesis in chat history.
- **Lint** — periodic health check for orphans, malformed frontmatter, contradictions. On demand.

---

## Key Documents

### Knowledge Layer
- `Knowledge/index.md` - Entry point for project-level reference docs

### Skills (`claude/skills/`)
- `claude/skills/usage/SKILL.md` - `/usage` skill for monthly DAU/MAU collection via Pendo MCP
- `claude/skills/ux-bugs/SKILL.md` - `/ux-bugs` skill for quarterly UX Bug metrics via Atlassian MCP
- `claude/skills/nps/SKILL.md` - `/nps` skill for monthly NPS analysis (REST API + MCP pipeline)

### Frameworks & Methodology
- `NPS/Process/nps-monthly-analysis-workflow.md` - NPS workflow reference
- `NPS/portability-notes.md` - Cross-domain portability analysis
- `UX Bugs/Process/ux-bug-priority-levels.md` - TTR criteria and P1-P4 definitions
- `Context/skill-portability-options.md` - Options for sharing skills with other leaders

### Infrastructure
- `Infrastructure/metrics-api-appscript.js` - Google Apps Script web app for Sheets push
- `Infrastructure/metrics-api-deployment.md` - Deployment guide for the Apps Script API
- `Infrastructure/sheets-api-config.md` - Your deployed web app URL (create after deployment; gitignored)

## File Naming Convention

Hybrid naming:
- **Folders:** Mac-style (spaces, proper capitalization) - e.g., "Product Name"
- **Files:** kebab-case (lowercase, hyphens) - e.g., "mc-nps-analysis-202601.md"

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

## Intake

### Tasks
**Method:** backlog-json
**Location:** backlog.json
**Schema:** Minimal (id, title, description, status, source, created, context_doc)

### Knowledge
**Method:** markdown-file
**Location:** `Knowledge/`
**Schema:** `type/knowledge` + `project/metrics` + `updated` frontmatter (+ optional `backlog-item`)
**Index:** `Knowledge/index.md` updated on create/delete/rename
**Writing posture:** Agent-first, user-secondary. See Knowledge Sources & Prioritization > Writing posture.

---

**Note:** To update project state at end of session, use prompt: "Close out this session for Metrics"
