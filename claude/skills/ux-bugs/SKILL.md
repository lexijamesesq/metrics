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

Calculate metrics for ALL quarters of `CURRENT_YEAR` (and prior year if data exists) for **each project in `PROJECT_KEYS`**. Use the logic from `UX Bugs/Scripts/collect-ux-bugs.py`.

### Quarter Date Ranges

```python
def get_quarter_dates(year, quarter):
    quarters = {
        "Q1": (f"{year}-01-01", f"{year}-03-31"),
        "Q2": (f"{year}-04-01", f"{year}-06-30"),
        "Q3": (f"{year}-07-01", f"{year}-09-30"),
        "Q4": (f"{year}-10-01", f"{year}-12-31"),
    }
    return quarters[quarter]
```

### TTR Windows

Use `TTR_WINDOWS` from config (loaded in Step 0):

```python
# Example: {"P1": 45, "P2": 60, "P3": 180, "P4": None}
TTR_WINDOWS = {loaded from config}
```

### For Each Quarter, Calculate:

1. **Total Created:** Count **customer-reported** bugs (open + resolved) with `created` date in quarter range
2. **P1-P4:** Count customer-reported bugs created in quarter by priority level
3. **Total Resolved:** Count **customer-reported** bugs with `resolved` date in quarter range
4. **% Remediated:** `total_resolved / total_created` (0 if no bugs created). Express as decimal (e.g., 0.33)
5. **% Outside TTR:**
   - Scope: **customer-reported P1/P2/P3 bugs only** — P4 excluded from both numerator and denominator (no TTR window)
   - Find all in-scope bugs "open during quarter" = created before/during quarter AND (not resolved OR resolved during/after quarter start)
   - For each: calculate TTR deadline = created + TTR_WINDOWS[priority]
   - Bug is "outside TTR" if TTR deadline <= quarter end AND bug was still open after deadline
   - `pct_outside_ttr = outside_ttr_count / total_open_during_quarter`
   - Express as decimal (e.g., 0.33)

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

Write notes only for quarters that have actual data (total_created > 0 OR total_resolved > 0 OR pct_outside_ttr > 0).

## Step 7: Validate and Update TTR Due Dates

For each open bug across **all projects in `PROJECT_KEYS`** with `customer_reported=true` and priority P1/P2/P3:

1. Calculate expected due date: `created + TTR_WINDOWS[priority]` days
2. Compare to current `duedate` field
3. Collect all discrepancies from both projects before prompting

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

After Jira updates, update the local JSON snapshot with corrected due dates.

## Step 8: Write TTR Violation Files and Current State Note

### TTR Violation Files

For each project in `PROJECT_KEYS`:

**Directory:** `UX Bugs/Tracking/TTR Violations/`

Use `Glob` to find all existing files matching `UX Bugs/Tracking/TTR Violations/{project_key_lowercase}-*.md`. Delete each using `mcp__obsidian__delete_note` (set `confirmPath` = `path`).

For each open bug in this project where `calculated_ttr_deadline <= COLLECTION_DATE`:

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

This file is DERIVED — safe to overwrite each run. N = open bug count, M = outside TTR count, PCT_INT = integer percentage.

**Frontmatter:**

```yaml
---
updated: {COLLECTION_DATE}
---
```

**Body — heading and summary line:**

```
# {PROJECT_KEY} UX Bugs — Current State

**As of {COLLECTION_DATE}:** {N} open bugs, {M} outside TTR ({PCT_INT}%)

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

## Step 9: Display Summary

Output to user:

For each project in `PROJECT_KEYS`, output:

```
## UX Bugs Collection Complete — {COLLECTION_DATE}

### Quarterly Summary ({PROJECT_KEY})

| Quarter | Created | P1 | P2 | P3 | P4 | Resolved | % Remediated | % Outside TTR |
|---------|---------|----|----|----|----|----------|--------------|---------------|
[table rows]

### {PROJECT_KEY}: {N} open bugs, {M} outside TTR ({PCT}%)
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

## Step 10: Push to Google Sheets

Read the config:
```
Read: Infrastructure/sheets-api-config.md
```

If file is missing, skip silently — summary table output is the fallback.

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

Post all quarters with data for each project in `PROJECT_KEYS`. Each POST is a batch array of all quarters for that project.

Check each response `status` field. If `200`, report: `✓ Pushed to Google Sheets ({project}: inserted N, updated N)`. If not `200`, report the error but do not fail the skill.

## Error Handling

- **Atlassian MCP timeout:** Stop immediately, instruct user to exit/resume
- **Zero bugs returned:** Warn user ("Query returned 0 bugs — verify JQL and project"), but proceed with calculations
- **Missing resolutiondate:** Skip bug from resolved calculations, warn user
- **Partial data:** Write what succeeded, report what failed
