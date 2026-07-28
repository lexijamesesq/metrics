---
name: ux-bugs
description: This skill should be used when the user asks to "collect UX bugs", "run UX bug metrics", "check TTR compliance", or "pull bug data". Collects quarterly UX Bug metrics for configured Jira projects via Atlassian MCP, including TTR validation and due date enforcement.
argument-hint: [YYYY-MM-DD]
context: fork
allowed-tools:
  - mcp__atlassian__searchJiraIssuesUsingJql
  - mcp__atlassian__editJiraIssue
  - mcp__atlassian__addCommentToJiraIssue
  - mcp__atlassian__getAccessibleAtlassianResources
  - mcp__obsidian__delete_note
  - Read
  - Write
  - Glob
  - Bash(python3:*)
  - Bash(date:*)
  - Bash(curl:*)
---

# /ux-bugs — Collect Quarterly UX Bug Metrics

Collects UX Bug metrics for configured Jira projects via Atlassian MCP. Calculates quarterly metrics (total created, priority breakdown, remediation rate, TTR compliance), validates due dates, and writes current-state and TTR violation notes for each project.

## Invocation

```
/ux-bugs [YYYY-MM-DD]
```

- Defaults to **today's date** as collection date if no argument given
- Example: `/ux-bugs 2026-02-23`

## Arguments

Parse `$ARGUMENTS` for a date in `YYYY-MM-DD` format. If empty, use today's date.

Set these variables:
- `COLLECTION_DATE` = "YYYY-MM-DD"
- `CURRENT_YEAR` = year from collection date (for quarterly calculations)

## Step 0: Load Configuration

Read `jira-config.md` from the project root. If the file is not found, stop and tell the user:

> "`jira-config.md` not found in the project root. Copy `jira-config.sample.md` to `jira-config.md` and fill in your values to use this skill."

Extract the following values from the config sections:

**From Connection:**
- `CLOUD_ID` ← `cloud_id`
- `JIRA_BASE_URL` ← `base_url`

**From UX Bug Projects:**
- `PROJECT_KEYS` ← list of project keys (e.g., `["PROJ1", "PROJ2"]`)

**From Custom Fields > UX Bugs:**
- `SALESFORCE_COUNT_FIELD` ← `salesforce_count` (e.g., `customfield_XXXXX`)
- `REQUIREMENT_TYPE_FIELD` ← `requirement_type_field` (e.g., `Requirement Type[Dropdown]`)
- `REQUIREMENT_TYPE_VALUE` ← `requirement_type_value` (e.g., `UX`)

**From TTR Windows:**
- `TTR_WINDOWS` ← dict mapping priority to days (e.g., `{"P1": 45, "P2": 60, "P3": 180, "P4": None}`)

## Step 1: Query Open Bugs

For each project key in `PROJECT_KEYS`, query Atlassian for all open UX bugs:

```
mcp__atlassian__searchJiraIssuesUsingJql(
    cloudId="{CLOUD_ID}",
    jql='statusCategory != Done AND "{REQUIREMENT_TYPE_FIELD}" = {REQUIREMENT_TYPE_VALUE} AND project = {PROJECT_KEY}',
    fields=["key", "summary", "priority", "created", "duedate", "status", "{SALESFORCE_COUNT_FIELD}"],
    maxResults=100
)
```

Store results separately per project key for later processing.

**If timeout:** Stop immediately and tell user:
> "Atlassian MCP timed out. Please exit and resume Claude Code to refresh the connection."

Do NOT retry in the same session.

## Step 2: Query Resolved Bugs

For each project key in `PROJECT_KEYS`, query for resolved customer-reported UX bugs:

```
mcp__atlassian__searchJiraIssuesUsingJql(
    cloudId="{CLOUD_ID}",
    jql='statusCategory = Done AND salesforceAssociatedIds IS NOT empty AND "{REQUIREMENT_TYPE_FIELD}" = {REQUIREMENT_TYPE_VALUE} AND project = {PROJECT_KEY}',
    fields=["key", "summary", "priority", "created", "resolutiondate", "project", "{SALESFORCE_COUNT_FIELD}"],
    maxResults=100
)
```

**Critical:** Use `resolutiondate` field, not `resolved`.

## Step 3: Transform Data

Apply these transformations to each bug:

### Open Bug Transform

```python
def transform_open_bug(jira_bug):
    fields = jira_bug["fields"]
    created_date = fields["created"].split("T")[0]
    salesforce_count = fields.get("{SALESFORCE_COUNT_FIELD}")
    customer_reported = salesforce_count is not None and salesforce_count > 0

    return {
        "key": jira_bug["key"],
        "summary": fields["summary"],
        "priority": fields["priority"]["name"],
        "created": created_date,
        "duedate": fields.get("duedate"),
        "status": fields["status"]["name"],
        "customer_reported": customer_reported
    }
```

### Resolved Bug Transform

```python
def transform_resolved_bug(jira_bug):
    fields = jira_bug["fields"]
    created_date = fields["created"].split("T")[0]
    resolved_date = fields.get("resolutiondate", "").split("T")[0] if fields.get("resolutiondate") else None
    salesforce_count = fields.get("{SALESFORCE_COUNT_FIELD}")
    customer_reported = salesforce_count is not None and salesforce_count > 0

    return {
        "key": jira_bug["key"],
        "summary": fields["summary"],
        "priority": fields["priority"]["name"],
        "created": created_date,
        "resolved": resolved_date,
        "project": fields["project"]["key"],
        "customer_reported": customer_reported
    }
```

## Step 4: Save JSON Snapshot

Write raw data to:
`UX Bugs/Data/ux-bugs-data-{COLLECTION_DATE}.json`

```json
{
  "as_of_date": "{COLLECTION_DATE}",
  "{PROJECT_KEY_1}": {
    "open_bugs": [...transformed open bugs...],
    "resolved_bugs": [...transformed resolved bugs...]
  },
  "{PROJECT_KEY_2}": {
    "open_bugs": [...transformed open bugs...],
    "resolved_bugs": [...transformed resolved bugs...]
  }
}
```

Use the actual project keys from `PROJECT_KEYS` as the JSON section headers.

**NEVER delete previous JSON snapshots.** Each month's snapshot is immutable history.

## Step 5: Calculate Quarterly Metrics

Run the calculation script against the snapshot written in Step 4:

```bash
python3 "UX Bugs/Scripts/collect-ux-bugs.py" --snapshot "UX Bugs/Data/ux-bugs-data-{COLLECTION_DATE}.json"
```

The script is the single home of the calculation logic — never re-derive a metric in-context. It reads TTR windows from `jira-config.md` (`## TTR Windows` > `### UX Bugs`) and emits JSON with, per project, per quarter (current year + prior year):

- `total_created`, `p1`–`p4`, `other_priority`, `total_resolved`, `pct_remediated`, `pct_outside_ttr`, `outside_ttr_keys`, `ttr_scope_count`, `has_data` (true when created, resolved, or violations are nonzero)
- `status`: `complete` (quarter ended before collection date), `in_progress` (collection date falls inside the quarter), `future` (quarter starts after collection date)
- `current_state` per project: `open_total`, `ttr_scope_open` (customer-reported P1–P3), and the violation list

Metric definitions live in the script's docstring — one home, not two. The script is deterministic; a drift there surfaces as a value change.

If the script exits non-zero or emits `warnings` (e.g., an unrecognized priority value), surface them to the user before continuing.

**Key principle:** Recalculate ALL quarters every run. Historical data improves as bugs are resolved or discovered.

## Step 6: Write Quarterly Data Notes

Write one note per quarter per project to `UX Bugs/Tracking/`:

**File:** `UX Bugs/Tracking/{project_key_lowercase}-uxbugs-{YYYY}-q{N}.md`

Where `{project_key_lowercase}` is the lowercase version of the project key from `PROJECT_KEYS`.

UX Bugs data notes are expected to be **overwritten** each collection (quarterly metrics recalculate). No overwrite warning needed.

**Template** (substitute project key, display name, and file prefix as appropriate):

```yaml
---
type: metrics/ux-bugs
project: {PROJECT_KEY}
quarter: "Q1 2026"
quarter_short: 2026-q1
quarter_status: complete
total_created: 1
p1: 0
p2: 0
p3: 1
p4: 0
total_resolved: 2
pct_remediated: 2.00
pct_outside_ttr: 0.33
collection_date: {COLLECTION_DATE}
---

# {PROJECT_KEY} UX Bugs - Q1 2026

Collected via Atlassian MCP on {COLLECTION_DATE}.
```

Write a note for a quarter when BOTH hold:

1. `status` is `complete` or `in_progress`. Quarters with `status: future` are never written — a projected violation is not data.
2. `has_data` is true, OR a note for that quarter already exists in `UX Bugs/Tracking/`. An existing note whose metrics now recompute to zero gets corrected, never left stale.

## Step 7: Write TTR Violation Files and Current State Note

### TTR Violation Files

For each project in `PROJECT_KEYS`:

**Directory:** `UX Bugs/Tracking/TTR Violations/`

Use `Glob` to find all existing files matching `UX Bugs/Tracking/TTR Violations/{project_key_lowercase}-*.md`. Delete each using `mcp__obsidian__delete_note` (set `confirmPath` = `path`).

For each entry in the script's `current_state.violations` for this project (customer-reported P1–P3 with `ttr_deadline <= COLLECTION_DATE` — the same scope as the quarterly TTR metric, so the violation files and the percentages always agree):

**File:** `UX Bugs/Tracking/TTR Violations/{bug-key-lowercase}.md`

```yaml
---
type: metrics/ux-bugs-ttr-violation
project: {PROJECT_KEY}
bug_key: {BUG_KEY}
priority: {PRIORITY}
summary: "{SUMMARY}"
created: {CREATED_DATE}
ttr_deadline: {TTR_DEADLINE}
link: https://{JIRA_BASE_URL}/browse/{BUG_KEY}
---
```

Body: leave empty. These files are DERIVED — delete and recreate each run.

### Current State Notes

For each project in `PROJECT_KEYS`:

**File:** `UX Bugs/Tracking/{project_key_lowercase}-uxbugs-current-state.md`

This file is DERIVED — safe to overwrite each run. N = `current_state.open_total`, M = violation count, S = `current_state.ttr_scope_open`, PCT_INT = percentage of the TTR scope rounded to the nearest integer (never of all open bugs — mixing the two denominators is how 5 of 10 read as 24%).

**Frontmatter:**

```yaml
---
updated: {COLLECTION_DATE}
---
```

**Body — heading and summary line:**

```
# {PROJECT_KEY} UX Bugs — Current State

**As of {COLLECTION_DATE}:** {N} open bugs; {M} of {S} customer-reported P1–P3 outside TTR ({PCT_INT}% of TTR scope)

## Bugs Outside TTR Window
```

**Body — inline base block** (fenced code block with language `base`, immediately after the heading):

```base
filters:
  and:
    - 'type == "metrics/ux-bugs-ttr-violation"'
    - 'project == "{PROJECT_KEY}"'
views:
  - type: table
    name: {PROJECT_KEY} TTR Violations
    order:
      - bug_key
      - priority
      - summary
      - created
      - ttr_deadline
```

## Step 8: Display Summary

Output to user:

For each project in `PROJECT_KEYS`, output:

```
## UX Bugs Collection Complete — {COLLECTION_DATE}

### Quarterly Summary ({PROJECT_KEY})

| Quarter | Created | P1 | P2 | P3 | P4 | Resolved | % Remediated | % Outside TTR |
|---------|---------|----|----|----|----|----------|--------------|---------------|
[table rows — same quarters as Step 6: complete and in_progress only]

### {PROJECT_KEY}: {N} open bugs; {M} of {S} customer-reported P1–P3 outside TTR ({PCT}% of TTR scope)
```

Then after all projects:

```
### TTR Validation: {discrepancy count} issues found

Files updated:
- UX Bugs/Data/ux-bugs-data-{COLLECTION_DATE}.json
- UX Bugs/Tracking/{project_key_lowercase}-uxbugs-{YEAR}-q{N}.md (per project, per quarter)
- UX Bugs/Tracking/TTR Violations/ ({total} violation files)
- UX Bugs/Tracking/{project_key_lowercase}-uxbugs-current-state.md (per project)
```

## Step 9: Push to Google Sheets

Read the config:
```
Read: Infrastructure/sheets-api-config.md
```

If the file is missing, skip the push and say so in the Step 9 summary — a skipped push means the Sheet is stale, and silence is how that gets forgotten.

Extract `web_app_url` from the config. POST each quarter with data as a batch for each project.

Convert `COLLECTION_DATE` from YYYY-MM-DD to M/D/YYYY for the `Date` field (e.g. `2026-03-05` → `3/5/2026`).

```bash
python3 -c "
import urllib.request, json
payload = json.dumps({'metric_type':'ux_bugs','data':[{'Quarter':'{QUARTER}','Project':'{PROJECT}','Total_Created':{total_created},'P1':{p1},'P2':{p2},'P3':{p3},'P4':{p4},'Total_Resolved':{total_resolved},'%_Remediated':{pct_remediated},'%_Outside_TTR':{pct_outside_ttr},'Date':'{M/D/YYYY}'}]}).encode()
req = urllib.request.Request('{WEB_APP_URL}', data=payload, headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as r: print(r.read().decode())
"
```

Post exactly the quarters written in Step 6 — `status` complete or in_progress, never future. Each POST is a batch array of those quarters for that project.

Check each response `status` field. If `200`, report: `✓ Pushed to Google Sheets ({project}: inserted N, updated N)`. If not `200`, report the error but do not fail the skill.

## Step 10: Validate and Update TTR Due Dates

This step runs LAST — after all read-only work (notes, violation files, current-state, summary, Sheets push) is complete. The operator sees the full collection results before deciding on any Jira writes.

For each open bug across **all projects in `PROJECT_KEYS`** with `customer_reported=true` and priority P1/P2/P3:

1. Calculate expected due date: `created + TTR_WINDOWS[priority]` days
2. Compare to current `duedate` field
3. Collect all discrepancies from every project before prompting

### Report Discrepancies

```
TTR Due Date Validation:
  - {N} bugs checked (per project)
  - {M} discrepancies found:

    {PROJECT_KEY}-XXXXX (P3):
      Current: 2026-02-14
      Expected: 2026-06-13
      (Created 2025-12-15 + 180 days)

    {PROJECT_KEY}-XXXXX (P3):
      Current: 2026-03-01
      Expected: 2026-07-15
      (Created 2026-01-15 + 180 days)

Update due dates for these {M} bugs? (Y/N)
```

**Wait for user confirmation before making any Jira updates.**

### If User Approves Updates

For each discrepancy, update Jira:

```
mcp__atlassian__editJiraIssue(
    cloudId="{CLOUD_ID}",
    issueIdOrKey="{BUG_KEY}",
    fields={"duedate": "{EXPECTED_DUE_DATE}"}
)
```

Then add comment:

```
mcp__atlassian__addCommentToJiraIssue(
    cloudId="{CLOUD_ID}",
    issueIdOrKey="{BUG_KEY}",
    commentBody="Due date updated to align with UX Bug Priority Level policy. {PRIORITY} bugs have a {TTR_DAYS}-day TTR window from creation date."
)
```

After each successful update, append one line to `UX Bugs/Data/duedate-changes.jsonl` (create on first use; `python3 -c "import json; open('UX Bugs/Data/duedate-changes.jsonl','a').write(json.dumps({...})+'\n')"` — open in append mode so prior entries are never overwritten):

```json
{"date": "{COLLECTION_DATE}", "key": "{BUG_KEY}", "old_duedate": "{CURRENT}", "new_duedate": "{EXPECTED}"}
```

Log the line BEFORE the Jira call, so a crash mid-batch still records the intent. Do NOT modify the snapshot — it stays exactly as collected (Step 4 immutability).

If an `editJiraIssue` call fails, stop the batch there and report the applied changes (from the log) plus the remaining unapplied bugs. If the edit succeeds but the follow-up comment fails, the update counts as applied — log it with `"comment_failed": true` and continue.

## Error Handling

- **Atlassian MCP timeout:** Stop immediately, instruct user to exit/resume
- **Zero bugs returned:** Warn user ("Query returned 0 bugs — verify JQL and project"), but proceed with calculations
- **Missing resolutiondate:** Skip bug from resolved calculations, warn user
- **Partial data:** Write what succeeded, report what failed
