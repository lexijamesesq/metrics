---
name: usage
description: This skill should be used when the user asks to "collect usage",
  "run usage metrics", "get DAU/MAU", or "pull Pendo data". Collects monthly
  Usage metrics (MAU, DAU, DAU/MAU ratio) for configured products via Pendo MCP.
argument-hint: [ YYYY-MM ]
context: fork
allowed-tools:
  - mcp__pendo__appUsage
  - mcp__pendo__appUsageTimeSeries
  - mcp__pendo__entityUsage
  - mcp__pendo__entityUsageTimeSeries
  - Read
  - Write
  - Glob
  - Bash(python3:*)
  - Bash(date:*)
  - Bash(curl:*)
---

# /usage — Collect Monthly DAU/MAU Metrics

Collects monthly Usage metrics (MAU, DAU, DAU/MAU ratio) for configured products via Pendo MCP. Writes individual data notes with YAML frontmatter.

## Intent

**Objective:** every configured product's month lands in the tracking notes and the `Usage_Data` tab with its provenance visible — a reader can always tell what basis produced a number.

**Health metrics — must not degrade:**
- YoY provenance stays visible: every `yoy_change_pct` carries `yoy_source` in its note, and Snowflake-normalized values outside the reliable window are marked directional. A naked ratio with an invisible basis is how +106% shipped unqualified in June 2026.
- The published contract is append-only: this skill never changes `Usage_Data` column names, order, or units.

## Invocation

```
/usage [YYYY-MM]
```

- Defaults to **previous month** if no argument given
- Example: `/usage 2026-02` collects February 2026 data

## Arguments

The month argument is substituted positionally before this skill runs:
- `$0` = month in `YYYY-MM` format (e.g., `2026-03`)
If `$0` is empty or invalid, calculate previous month from today's date.

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

Wait for confirmation. Do NOT proceed without it. (Overwriting is safe by design — notes regenerate and the Sheet upserts on Product+Month, so a re-run corrects rather than duplicates. The gate exists so a re-collection is always a deliberate act, not a side effect.)

## Step 3: Collect Visitor-Level App Data

For apps configured with `entity_type: visitor`, use **visitor-level queries with segments** for role breakdown.

**Reference:** `Usage/Process/mcp-collection-guide.md`

### 3a: Teacher MAU

```
mcp__pendo__appUsage(
    subId="{PENDO_SUB_ID}",
    appId="{MC_APP_ID}",
    dateRange={"type": "absolute", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    segmentPipeline="{MC_TEACHER_SEGMENT}",
    includeAnonymous=False,
    limit=1
)
```

Extract: `summary.totalNumVisitors` → `mc_teacher_mau`

### 3b: Student MAU

```
mcp__pendo__appUsage(
    subId="{PENDO_SUB_ID}",
    appId="{MC_APP_ID}",
    dateRange={"type": "absolute", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    segmentPipeline="{MC_STUDENT_SEGMENT}",
    includeAnonymous=False,
    limit=1
)
```

Extract: `summary.totalNumVisitors` → `mc_student_mau`

### 3c: Daily Active Users (for DAU calculations)

```
mcp__pendo__appUsageTimeSeries(
    subId="{PENDO_SUB_ID}",
    appId="{MC_APP_ID}",
    dateRange={"type": "absolute", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    period="daily",
    includeAnonymous=False
)
```

Extract each row's `totalNumVisitors` as that day's active-visitor count. Calculate:
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

> **Basis note (2026-07-27):** Pendo segments evaluate membership at query time,
> so monthly values are collection-time snapshots taken ~day 7 after month end —
> the standing cadence. Historical CQ-teacher months re-queried later will read
> low (verified gradient 2026-07-27: −5% to −10%); that is expected live-segment
> behavior, not a collection error. Never re-collect old CQ months — forward-only
> collection at day-7 cadence is what keeps the series' historical semantics
> intact. See Knowledge/pendo-mcp-capabilities.md.

### 4a: Teacher MAU (CQ Page + Canvas Teachers)

```
mcp__pendo__entityUsage(
    subId="{PENDO_SUB_ID}",
    entityType="page",
    entityId="{CQ_PAGE_ID}",
    dateRange={"type": "absolute", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    segmentPipeline="{CANVAS_TEACHER_SEGMENT}",
    includeAnonymous=False,
    limit=1
)
```

Extract: `summary.totalNumVisitors` → `cq_teacher_mau`

### 4b: Student MAU (CQ Page + Canvas Students)

```
mcp__pendo__entityUsage(
    subId="{PENDO_SUB_ID}",
    entityType="page",
    entityId="{CQ_PAGE_ID}",
    dateRange={"type": "absolute", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    segmentPipeline="{CANVAS_STUDENT_SEGMENT}",
    includeAnonymous=False,
    limit=1
)
```

Extract: `summary.totalNumVisitors` → `cq_student_mau`

### 4c: Daily Active Users (Teacher + Student)

Run two daily queries (one per segment), then combine per day:

```
# Teacher daily (CQ Page + Canvas Teachers):
mcp__pendo__entityUsageTimeSeries(
    subId="{PENDO_SUB_ID}",
    entityType="page",
    entityId="{CQ_PAGE_ID}",
    dateRange={"type": "absolute", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    period="daily",
    segmentPipeline="{CANVAS_TEACHER_SEGMENT}",
    includeAnonymous=False
)

# Student daily (CQ Page + Canvas Students):
mcp__pendo__entityUsageTimeSeries(
    subId="{PENDO_SUB_ID}",
    entityType="page",
    entityId="{CQ_PAGE_ID}",
    dateRange={"type": "absolute", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    period="daily",
    segmentPipeline="{CANVAS_STUDENT_SEGMENT}",
    includeAnonymous=False
)
```

For each day, sum teacher + student `visitors` (each row's daily unique-visitor count). Then:
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
mcp__pendo__entityUsage(
    subId="{PENDO_SUB_ID}",
    entityType="page",
    entityId="{NQ_BUILD_PAGE_ID}",
    dateRange={"type": "absolute", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    segmentPipeline="{CANVAS_TEACHER_SEGMENT}",
    includeAnonymous=False,
    limit=1
)
```

Extract: `summary.totalNumVisitors` → `nq_teacher_mau`

### 5b: Student MAU (NQ Taking + Canvas Students)

```
mcp__pendo__entityUsage(
    subId="{PENDO_SUB_ID}",
    entityType="page",
    entityId="{NQ_TAKING_PAGE_ID}",
    dateRange={"type": "absolute", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    segmentPipeline="{CANVAS_STUDENT_SEGMENT}",
    includeAnonymous=False,
    limit=1
)
```

Extract: `summary.totalNumVisitors` → `nq_student_mau`

### 5c: Daily Active Users (Teacher + Student)

Run two daily queries (one per page+segment), then combine per day:

```
# Teacher daily (NQ Build + Canvas Teachers):
mcp__pendo__entityUsageTimeSeries(
    subId="{PENDO_SUB_ID}",
    entityType="page",
    entityId="{NQ_BUILD_PAGE_ID}",
    dateRange={"type": "absolute", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    period="daily",
    segmentPipeline="{CANVAS_TEACHER_SEGMENT}",
    includeAnonymous=False
)

# Student daily (NQ Taking + Canvas Students):
mcp__pendo__entityUsageTimeSeries(
    subId="{PENDO_SUB_ID}",
    entityType="page",
    entityId="{NQ_TAKING_PAGE_ID}",
    dateRange={"type": "absolute", "startDate": "{MONTH_START}", "endDate": "{MONTH_END}"},
    period="daily",
    segmentPipeline="{CANVAS_STUDENT_SEGMENT}",
    includeAnonymous=False
)
```

For each day, sum teacher + student `visitors` (each row's daily unique-visitor count). Then:
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

If previous month's data note doesn't exist, set `mom_change_pct: null` (the same missing-value convention as YoY — never `""`).

### 6b: Year-over-Year (all products; CQ starting with the 2026-08 run)

**CQ rule (operator ruling 2026-07-27):** CQ YoY resolves from prior-year Pendo notes only, beginning with the 2026-08 run — baseline is `cq-usage-2025-08.md`. The retained `cq-usage-2025-07.md` is NOT a trusted YoY baseline (rollout-period collection), and CQ has no Snowflake lookup fallback. For any run before 2026-08, CQ YoY is `null` with `yoy_source: null`.

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
yoy_source = "pendo" or "snowflake-normalized"  # whichever step resolved it
```

When `yoy_source` is `snowflake-normalized`, also set `yoy_reliability`: `reliable` if TARGET_MONTH's month is Oct–Jan (the calibration table's stated reliable window), else `directional-only`. When the source is `pendo`, omit `yoy_reliability` entirely.

If no prior year data available (not in Pendo notes AND not in lookup table), set `yoy_change_pct: null`, `total_mau_yoy: null`, and `yoy_source: null`.

**Basis flip, visible not silent:** starting with the 2026-08 run, MC and NQ resolve YoY from prior-year Pendo notes (2025-08 onward exists on disk) and the Snowflake lookup stops being used except for 2025-07. Nothing about the numbers announces that switch — `yoy_source` is what makes it visible in the data.

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
yoy_source: {YOY_SOURCE}
yoy_reliability: {YOY_RELIABILITY}   # only when yoy_source is snowflake-normalized
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

If the file is missing, skip the push — but say so in the summary. A skipped push means the Sheet is stale; silence is how that gets forgotten.

Extract `web_app_url` from the config, then POST **the products that collected successfully** as a batch. Build the `data` array in code — start empty and append one dict per product only when that product collected successfully this run (per Step 7/8's success list, `{SUCCESSFUL_PRODUCTS}` below). Never append a placeholder dict for a skipped or failed product:

```bash
python3 -c "
import urllib.request, json
data = []
# Append one dict per product that collected successfully this run — never a
# placeholder for a skipped or failed product.
if 'mc' in {SUCCESSFUL_PRODUCTS}:
    data.append({'Product':'{MC_PRODUCT_NAME}','Month':'{TARGET_MONTH}','Total_MAU':{mc_total_mau},'Teacher_MAU':{mc_teacher_mau},'Student_MAU':{mc_student_mau},'Avg_DAU':{mc_avg_dau},'Peak_DAU':{mc_peak_dau},'DAU_MAU_Ratio':{mc_dau_mau_ratio},'MoM_Change_Pct':{mc_mom_change_pct},'YoY_Change_Pct':{mc_yoy_change_pct}})
if 'cq' in {SUCCESSFUL_PRODUCTS}:
    data.append({'Product':'{CQ_PRODUCT_NAME}','Month':'{TARGET_MONTH}','Total_MAU':{cq_total_mau},'Teacher_MAU':{cq_teacher_mau},'Student_MAU':{cq_student_mau},'Avg_DAU':{cq_avg_dau},'Peak_DAU':{cq_peak_dau},'DAU_MAU_Ratio':{cq_dau_mau_ratio},'MoM_Change_Pct':{cq_mom_change_pct},'YoY_Change_Pct':{cq_yoy_change_pct}})
if 'nq' in {SUCCESSFUL_PRODUCTS}:
    data.append({'Product':'{NQ_PRODUCT_NAME}','Month':'{TARGET_MONTH}','Total_MAU':{nq_total_mau},'Teacher_MAU':{nq_teacher_mau},'Student_MAU':{nq_student_mau},'Avg_DAU':{nq_avg_dau},'Peak_DAU':{nq_peak_dau},'DAU_MAU_Ratio':{nq_dau_mau_ratio},'MoM_Change_Pct':{nq_mom_change_pct},'YoY_Change_Pct':{nq_yoy_change_pct}})
payload = json.dumps({'metric_type':'usage','data':data}).encode()
req = urllib.request.Request('{WEB_APP_URL}', data=payload, headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as r: print(r.read().decode())
"
```

- `{SUCCESSFUL_PRODUCTS}` is the literal Python list of product shorts collected without error this run, e.g. `['mc','nq']`
- `Month` is YYYY-MM format (e.g. `"2026-02"`) — the script converts it to M/D/YYYY for Sheets
- `MoM_Change_Pct` and `YoY_Change_Pct` are decimal ratios (e.g. `0.38`, not `38`)
- CQ `YoY_Change_Pct` is `null` for runs before 2026-08 (no trusted baseline earlier — see Step 6b's CQ rule); from the 2026-08 run it carries the computed value
- Use `None` (JSON null) for any MoM/YoY value where data was unavailable — the same convention as the notes, never `""`

Check the response `status` field. If `200`, report: `✓ Pushed to Google Sheets (inserted: N, updated: N)`. If not `200`, report the error but do not fail the skill — Sheets push is non-blocking.

On any skipped or failed push, the Step 8 summary must name the affected Product + Month rows and state that re-running the month is the recovery — both the tracking notes and the Sheet correct idempotently, so fixing the cause and re-running the month is always the fix.

## Configuration Reference

See `pendo-config.md` for all Pendo connection details, app IDs, segment IDs, and page IDs.

## Error Handling

- **Pendo MCP timeout:** Stop and tell user: "Pendo MCP timed out. Please exit and resume Claude Code to refresh the connection."
- **Missing previous month data:** Skip MoM calculation, set `mom_change_pct: null`
- **Partial collection failure:** Write data notes for the products that succeeded, push only those products (Step 9's array), and name the failed products in the Step 8 summary. Recovery is the same in every case: fix the cause and re-run the month — both the tracking notes and the Sheet correct idempotently.
- **Zero count for a product with nonzero history:** Stop before writing anything for that product and surface it — a paused survey or retired page looks exactly like a real zero (this bit the NPS pipeline in June 2026).
- **Unexpected response format:** Show raw response and ask user how to proceed
