---
name: usage
description: This skill should be used when the user asks to "collect usage", "run usage metrics", "get DAU/MAU", or "pull Pendo data". Collects monthly Usage metrics (MAU, DAU, DAU/MAU ratio) for configured products via Pendo MCP.
argument-hint: [YYYY-MM]
context: fork
allowed-tools:
  - mcp__pendo__activityQuery
  - Read
  - Write
  - Glob
  - Bash(python3:*)
  - Bash(date:*)
  - Bash(curl:*)
---

# /usage — Collect Monthly DAU/MAU Metrics

Collects monthly Usage metrics (MAU, DAU, DAU/MAU ratio) for configured products via Pendo MCP. Writes individual data notes with YAML frontmatter.

## Invocation

```
/usage [YYYY-MM]
```

- Defaults to **previous month** if no argument given
- Example: `/usage 2026-02` collects February 2026 data

## Arguments

Parse `$ARGUMENTS` for a month in `YYYY-MM` format. If empty or invalid, calculate previous month from today's date.

## Step 0: Load Configuration

Read `pendo-config.md` from the project root. If the file is not found, stop and tell the user:

> "`pendo-config.md` not found in the project root. Copy `pendo-config.sample.md` to `pendo-config.md` and fill in your Pendo IDs to use this skill."

Extract the following values from the config sections:

**From Connection:**
- `PENDO_SUB_ID` ← `subscription_id`

**From Usage Apps:**
- `MC_APP_ID` ← first product `app_id` (visitor-level app)
- `CANVAS_APP_ID` ← second/third product `app_id` (page-level app, shared if applicable)

**From Segments:**
- `MC_TEACHER_SEGMENT` ← MC Teachers segment ID
- `MC_STUDENT_SEGMENT` ← MC Students segment ID
- `CANVAS_TEACHER_SEGMENT` ← Canvas Teachers segment ID
- `CANVAS_STUDENT_SEGMENT` ← Canvas Students segment ID

**From Page IDs:**
- `CQ_PAGE_ID` ← CQ page ID
- `NQ_BUILD_PAGE_ID` ← NQ Build page ID
- `NQ_TAKING_PAGE_ID` ← NQ Taking page ID

## Step 1: Determine Target Month

```python
# If $ARGUMENTS is empty, default to previous month
# Example: If today is 2026-03-05, target = "2026-02"
```

**Date validation:** If today is day 1 of the current month and the user is requesting the previous month, warn:
> "It's only [date]. Pendo data for [month] may still be processing. Recommend waiting until day 2-3. Proceed anyway?"

Wait for user confirmation before continuing.

Set these variables for the rest of the workflow:
- `TARGET_MONTH` = "YYYY-MM" (e.g., "2026-02")
- `MONTH_START` = "YYYY-MM-01"
- `MONTH_END` = last day of month (e.g., "2026-02-28")
- `MONTH_DATE` = "YYYY-MM-01" (for frontmatter and Sheets)

## Step 2: Check for Existing Data Notes

Check if data notes already exist for the target month:

```
Glob: Usage/Tracking/{mc,cq,nq}-usage-{TARGET_MONTH}.md
```

Path: `Usage/Tracking/`

If ANY files exist, warn the user:
> "Data notes already exist for [TARGET_MONTH]: [list files]. Overwrite? (Y/N)"

Wait for confirmation. Do NOT proceed without it.

## Step 3: Collect Visitor-Level App Data

For apps configured with `entity_type: visitor`, use **visitor-level queries with segments** for role breakdown.

**Reference:** `Usage/Process/mcp-collection-guide.md`

### 3a: Teacher MAU

```
mcp__pendo__activityQuery(
    subId="{PENDO_SUB_ID}",
    appId="{MC_APP_ID}",
    entityType="visitor",
    dateRange={"range": "custom", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    period="dayRange",
    segmentId="{MC_TEACHER_SEGMENT}",
    count=True
)
```

Extract: `results.count` → `mc_teacher_mau`

### 3b: Student MAU

```
mcp__pendo__activityQuery(
    subId="{PENDO_SUB_ID}",
    appId="{MC_APP_ID}",
    entityType="visitor",
    dateRange={"range": "custom", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    period="dayRange",
    segmentId="{MC_STUDENT_SEGMENT}",
    count=True
)
```

Extract: `results.count` → `mc_student_mau`

### 3c: Daily Active Users (for DAU calculations)

```
mcp__pendo__activityQuery(
    subId="{PENDO_SUB_ID}",
    appId="{MC_APP_ID}",
    entityType="visitor",
    dateRange={"range": "custom", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    period="daily",
    count=True
)
```

Extract daily counts array. Calculate:
- `mc_avg_dau` = sum(all daily counts) / number of days (round to integer)
- `mc_peak_dau` = max(all daily counts)

### 3d: Calculate Derived Metrics

```python
mc_total_mau = mc_teacher_mau + mc_student_mau
mc_dau_mau_ratio = round(mc_avg_dau / mc_total_mau, 2)
```

## Step 4: Collect Page-Level App Data (Single Page)

For apps configured with `entity_type: page` and a single tracked page, use **page-level queries** with role segments.

**Page:** configured page ID (`{CQ_PAGE_ID}`)

### 4a: Teacher MAU

```
mcp__pendo__activityQuery(
    subId="{PENDO_SUB_ID}",
    appId="{CANVAS_APP_ID}",
    entityType="page",
    itemIds=["{CQ_PAGE_ID}"],
    dateRange={"range": "custom", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    period="dayRange",
    segmentId="{CANVAS_TEACHER_SEGMENT}"
)
```

Extract: First row's `uniqueVisitorCount` → `cq_teacher_mau`

### 4b: Student MAU

```
mcp__pendo__activityQuery(
    subId="{PENDO_SUB_ID}",
    appId="{CANVAS_APP_ID}",
    entityType="page",
    itemIds=["{CQ_PAGE_ID}"],
    dateRange={"range": "custom", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    period="dayRange",
    segmentId="{CANVAS_STUDENT_SEGMENT}"
)
```

Extract: First row's `uniqueVisitorCount` → `cq_student_mau`

### 4c: Daily Active Users (Teacher + Student)

Run two daily queries (one per segment), then combine per day:

```
# Teacher daily:
mcp__pendo__activityQuery(
    subId="{PENDO_SUB_ID}",
    appId="{CANVAS_APP_ID}",
    entityType="page",
    itemIds=["{CQ_PAGE_ID}"],
    dateRange={"range": "custom", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    period="daily",
    segmentId="{CANVAS_TEACHER_SEGMENT}"
)

# Student daily:
mcp__pendo__activityQuery(
    subId="{PENDO_SUB_ID}",
    appId="{CANVAS_APP_ID}",
    entityType="page",
    itemIds=["{CQ_PAGE_ID}"],
    dateRange={"range": "custom", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    period="daily",
    segmentId="{CANVAS_STUDENT_SEGMENT}"
)
```

For each day, sum teacher + student `uniqueVisitorCount`. Then:
- `cq_avg_dau` = sum(all daily totals) / number of days (round to integer)
- `cq_peak_dau` = max(all daily totals)

### 4d: Derived

```python
cq_total_mau = cq_teacher_mau + cq_student_mau
cq_dau_mau_ratio = round(cq_avg_dau / cq_total_mau, 2)
```

## Step 5: Collect Page-Level App Data (Multi-Page)

For apps with **two separate tracked pages** (e.g., one for authoring, one for consumption), each mapped to a role segment.

**Pages:**
- "NQ | Build page" (`{NQ_BUILD_PAGE_ID}`) — Teachers
- "NQ | Taking quiz page" (`{NQ_TAKING_PAGE_ID}`) — Students

### 5a: Teacher MAU (NQ Build + Canvas Teachers)

```
mcp__pendo__activityQuery(
    subId="{PENDO_SUB_ID}",
    appId="{CANVAS_APP_ID}",
    entityType="page",
    itemIds=["{NQ_BUILD_PAGE_ID}"],
    dateRange={"range": "custom", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    period="dayRange",
    segmentId="{CANVAS_TEACHER_SEGMENT}"
)
```

Extract: First row's `uniqueVisitorCount` → `nq_teacher_mau`

### 5b: Student MAU (NQ Taking + Canvas Students)

```
mcp__pendo__activityQuery(
    subId="{PENDO_SUB_ID}",
    appId="{CANVAS_APP_ID}",
    entityType="page",
    itemIds=["{NQ_TAKING_PAGE_ID}"],
    dateRange={"range": "custom", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    period="dayRange",
    segmentId="{CANVAS_STUDENT_SEGMENT}"
)
```

Extract: First row's `uniqueVisitorCount` → `nq_student_mau`

### 5c: Daily Active Users (Teacher + Student)

Run two daily queries (one per page+segment), then combine per day:

```
# Teacher daily (NQ Build + Canvas Teachers):
mcp__pendo__activityQuery(
    subId="{PENDO_SUB_ID}",
    appId="{CANVAS_APP_ID}",
    entityType="page",
    itemIds=["{NQ_BUILD_PAGE_ID}"],
    dateRange={"range": "custom", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    period="daily",
    segmentId="{CANVAS_TEACHER_SEGMENT}"
)

# Student daily (NQ Taking + Canvas Students):
mcp__pendo__activityQuery(
    subId="{PENDO_SUB_ID}",
    appId="{CANVAS_APP_ID}",
    entityType="page",
    itemIds=["{NQ_TAKING_PAGE_ID}"],
    dateRange={"range": "custom", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    period="daily",
    segmentId="{CANVAS_STUDENT_SEGMENT}"
)
```

For each day, sum teacher + student `uniqueVisitorCount`. Then:
- `nq_avg_dau` = sum(all daily totals) / number of days (round to integer)
- `nq_peak_dau` = max(all daily totals)

### 5d: Derived

```python
nq_total_mau = nq_teacher_mau + nq_student_mau
nq_dau_mau_ratio = round(nq_avg_dau / nq_total_mau, 2)
```

## Step 6: Calculate Month-over-Month and Year-over-Year Change

### 6a: Month-over-Month

For each product, read the **previous month's** data note to get prior MAU:

```
Read: Usage/Tracking/{short}-usage-{PREV_MONTH}.md
```

Extract `total_mau` from frontmatter. Calculate:

```python
mom_change_pct = round((current_total_mau - prev_total_mau) / prev_total_mau, 2)
```

If previous month's data note doesn't exist, leave `mom_change_pct` as empty string `""`.

### 6b: Year-over-Year (MC and NQ only — CQ always `null`)

Determine `PRIOR_YEAR_MONTH` = TARGET_MONTH minus 12 months (e.g., "2026-02" → "2025-02").

**Step 1 — Try Pendo tracking note first:**

```
Read: Usage/Tracking/{short}-usage-{PRIOR_YEAR_MONTH}.md
```

If found, extract `total_mau` → use as `prior_year_mau`. Mark source as `pendo`.

**Step 2 — Fall back to Snowflake-normalized lookup:**

If tracking note not found, check the YoY Lookup Table in `pendo-config.md` for the `PRIOR_YEAR_MONTH`. If found, use that value. Mark source as `snowflake-normalized`.

**Step 3 — Calculate or skip:**

```python
yoy_change_pct = round((current_total_mau - prior_year_mau) / prior_year_mau, 2)
total_mau_yoy = prior_year_mau  # the actual prior year value, for YoY line chart
```

If no prior year data available (not in Pendo notes AND not in lookup table), set `yoy_change_pct: null` and `total_mau_yoy: null`.

**Note on July:** Jul 2025 Pendo tracking files were deleted (excluded from ongoing tracking). The lookup table includes 2025-07 values so `/usage 2026-07` can still compute YoY. Jul 2024 is not in the table — a data gap existed for one product that month.

**Step 4 — Note source in summary** if `snowflake-normalized` was used (see Step 8).

## Step 7: Write Individual Data Notes

Write one note per product to `Usage/Tracking/`:

**File:** `Usage/Tracking/{short}-usage-{TARGET_MONTH}.md`

**Template:**

```yaml
---
type: metrics/usage
product: {PRODUCT_NAME}
product_short: {SHORT}
month: "{TARGET_MONTH}"
month_date: {MONTH_DATE}
total_mau: {TOTAL_MAU}
teacher_mau: {TEACHER_MAU}
student_mau: {STUDENT_MAU}
avg_dau: {AVG_DAU}
peak_dau: {PEAK_DAU}
dau_mau_ratio: {DAU_MAU_RATIO}
mom_change_pct: {MOM_CHANGE_PCT}
yoy_change_pct: {YOY_CHANGE_PCT}
total_mau_yoy: {TOTAL_MAU_YOY}
collected: {TODAY_DATE}
---

# {PRODUCT_NAME} Usage - {TARGET_MONTH}

Collected via Pendo MCP on {TODAY_DATE}.
```

Write all 3 files (mc, cq, nq).

## Step 8: Display Summary

Output a summary table to the user:

```
## Usage Collection Complete — {TARGET_MONTH}

| Product         | Total MAU  | Teacher MAU | Student MAU | Avg DAU | Peak DAU | DAU/MAU | MoM   | YoY   |
|-----------------|------------|-------------|-------------|---------|----------|---------|-------|-------|
| Product A       | 1,234,567  | 100,000     | 1,134,567   | 150,000 | 400,000  | 0.12   | -0.05 | 0.10  |
| Product B       | 5,678,901  | 500,000     | 5,178,901   | ...     | ...      | ...     | ...   | —     |
| Product C       | 2,345,678  | 200,000     | 2,145,678   | ...     | ...      | ...     | ...   | 0.15  |

Files written:
- Usage/Tracking/mc-usage-{TARGET_MONTH}.md
- Usage/Tracking/cq-usage-{TARGET_MONTH}.md
- Usage/Tracking/nq-usage-{TARGET_MONTH}.md
```

If any YoY values used the Snowflake-normalized lookup, add a footnote:

```
† Prior year from Snowflake-normalized data (calibration factors per product). Calibration period: Aug 2024–Jun 2025.
  Aug–Sep values are directional only; Oct–Jan is the reliable YoY window.
```

## Step 9: Push to Google Sheets

Read the config:
```
Read: Infrastructure/sheets-api-config.md
```

If file is missing, skip silently — summary table output is the fallback.

Extract `web_app_url` from the config, then POST all three products as a batch:

```bash
python3 -c "
import urllib.request, json
payload = json.dumps({'metric_type':'usage','data':[{'Product':'{MC_PRODUCT_NAME}','Month':'{TARGET_MONTH}','Total_MAU':{mc_total_mau},'Teacher_MAU':{mc_teacher_mau},'Student_MAU':{mc_student_mau},'Avg_DAU':{mc_avg_dau},'Peak_DAU':{mc_peak_dau},'DAU_MAU_Ratio':{mc_dau_mau_ratio},'MoM_Change_Pct':{mc_mom_change_pct},'YoY_Change_Pct':{mc_yoy_change_pct}},{'Product':'{CQ_PRODUCT_NAME}','Month':'{TARGET_MONTH}','Total_MAU':{cq_total_mau},'Teacher_MAU':{cq_teacher_mau},'Student_MAU':{cq_student_mau},'Avg_DAU':{cq_avg_dau},'Peak_DAU':{cq_peak_dau},'DAU_MAU_Ratio':{cq_dau_mau_ratio},'MoM_Change_Pct':{cq_mom_change_pct},'YoY_Change_Pct':None},{'Product':'{NQ_PRODUCT_NAME}','Month':'{TARGET_MONTH}','Total_MAU':{nq_total_mau},'Teacher_MAU':{nq_teacher_mau},'Student_MAU':{nq_student_mau},'Avg_DAU':{nq_avg_dau},'Peak_DAU':{nq_peak_dau},'DAU_MAU_Ratio':{nq_dau_mau_ratio},'MoM_Change_Pct':{nq_mom_change_pct},'YoY_Change_Pct':{nq_yoy_change_pct}}]}).encode()
req = urllib.request.Request('{WEB_APP_URL}', data=payload, headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as r: print(r.read().decode())
"
```

- `Month` is YYYY-MM format (e.g. `"2026-02"`) — the script converts it to M/D/YYYY for Sheets
- `MoM_Change_Pct` and `YoY_Change_Pct` are decimal ratios (e.g. `0.38`, not `38`)
- CQ `YoY_Change_Pct` is always `null`
- Use `""` for any MoM/YoY values where data was unavailable

Check the response `status` field. If `200`, report: `✓ Pushed to Google Sheets (inserted: N, updated: N)`. If not `200`, report the error but do not fail the skill — Sheets push is non-blocking.

## Configuration Reference

See `pendo-config.md` for all Pendo connection details, app IDs, segment IDs, and page IDs.

## Error Handling

- **Pendo MCP timeout:** Stop and tell user: "Pendo MCP timed out. Please exit and resume Claude Code to refresh the connection."
- **Missing previous month data:** Skip MoM calculation, leave field empty
- **Partial collection failure:** Write data notes for products that succeeded, report which failed
- **Unexpected response format:** Show raw response and ask user how to proceed
