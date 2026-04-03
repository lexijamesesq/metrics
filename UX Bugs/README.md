# /ux-bugs -- Quarterly UX Bug Metrics

Collects UX bug metrics for configured Jira projects via Atlassian MCP. Calculates quarterly metrics (total created, priority breakdown, remediation rate, TTR compliance), validates due dates against priority-based SLA windows, and writes quarterly data notes and TTR violation files.

## Invocation

```
/ux-bugs
/ux-bugs 2026-03-31
```

Defaults to today's date as collection date. Takes ~30-45 minutes. The skill queries all projects listed in `jira-config.md`.

## What it produces

- **JSON snapshot:** Immutable monthly snapshot in `UX Bugs/Data/ux-bugs-data-{YYYY-MM-DD}.json`
- **Quarterly data notes:** One per quarter per project in `UX Bugs/Tracking/{project}-uxbugs-{YYYY}-q{N}.md` with YAML frontmatter (created count, P1-P4 breakdown, resolved count, remediation rate, TTR compliance)
- **TTR violation files:** Individual files per overdue bug in `UX Bugs/Tracking/TTR Violations/` with frontmatter for Obsidian Base dashboards
- **Current state notes:** Per-project summary with inline Obsidian Base block for live TTR violation tables
- **Google Sheets push:** Quarterly metrics posted per project to the UXBugs_Data tab (non-blocking)

## TTR (Time to Remediation)

The skill enforces priority-based SLA windows for customer-reported bugs:

| Priority | TTR Window | Scope |
|----------|-----------|-------|
| P1 | 45 days | Customer-reported, SLA-tracked |
| P2 | 60 days | Customer-reported, SLA-tracked |
| P3 | 180 days | Customer-reported, SLA-tracked |
| P4 | None | Tracked but not SLA-bound |

TTR windows are configurable in `jira-config.md`. The skill calculates expected due dates from creation date + TTR window, reports discrepancies, and can update Jira due dates with your approval.

## Configuration

This skill reads `jira-config.md` at Step 0. Required fields:

| Field | Section | What to set |
|-------|---------|-------------|
| `cloud_id` | Connection | Your Atlassian Cloud ID |
| `base_url` | Connection | Your Jira instance URL (for bug links) |
| Project keys | UX Bug Projects | One line per Jira project to track |
| `salesforce_count` | Custom Fields > UX Bugs | Field ID for Salesforce case count (identifies customer-reported bugs) |
| `requirement_type_field` | Custom Fields > UX Bugs | JQL field name for filtering UX bugs |
| `requirement_type_value` | Custom Fields > UX Bugs | Value to match (e.g., "UX") |
| TTR windows | TTR Windows | Days per priority level |

## Prerequisites

- Atlassian MCP server configured in Claude Code
- `jira-config.md` populated with your Jira connection details and project keys
- Jira projects using a "Requirement Type" field to tag UX bugs
