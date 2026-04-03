# Metrics API - Apps Script Deployment Guide

Deployment instructions for the Design Metrics API web app that writes NPS, Usage, and UX Bugs data to the Design Metrics Google Sheet.

**Script source:** `metrics-api-appscript.js` (same directory)
**Target sheet:** `[your Google Sheet ID]`

---

## Prerequisites

1. You have edit access to the target Google Sheet
2. You are signed into Google Workspace (your organization's account)
3. The Google Sheet has three tabs named exactly: `NPS_Data`, `Usage_Data`, `UXBugs_Data`
4. Each tab's first row contains the column headers matching the schemas below

### Tab Schemas (Row 1 Headers)

**NPS_Data:**
`Product | Month | Score | Responses | Promoter_Pct | Passive_Pct | Detractor_Pct | Trend | Features_Launched | Interpretation | Link_Analysis | Link_Pendo`

**Usage_Data:**
`Product | Month | Total_MAU | Teacher_MAU | Student_MAU | Avg_DAU | Peak_DAU | DAU_MAU_Ratio | MoM_Change_Pct`

**UXBugs_Data:**
`Quarter | Project | Total_Created | P1 | P2 | P3 | P4 | Total_Resolved | %_Remediated | %_Outside_TTR | Date`

---

## Step 1: Create the Apps Script Project

1. Open the target Google Sheet
2. Go to **Extensions > Apps Script**
3. This opens the Apps Script editor bound to that spreadsheet
4. Delete any existing code in `Code.gs`
5. Paste the entire contents of `metrics-api-appscript.js`
6. Click the floppy disk icon (or Ctrl/Cmd+S) to save
7. Name the project: **Metrics API**

### Alternative: Standalone Script

If you prefer a standalone script (not bound to the sheet):

1. Go to [script.google.com](https://script.google.com)
2. Click **New project**
3. Paste the code and save
4. The `SHEET_ID` constant in the code already points to the correct sheet

> **Recommendation:** Use the bound script approach (Extensions > Apps Script from within the sheet). It simplifies permissions since the script inherits access to its parent sheet.

---

## Step 2: Test Before Deploying

1. In the Apps Script editor, select `testDoPost` from the function dropdown (top toolbar)
2. Click **Run**
3. On first run, Google will prompt for authorization:
   - Click **Review permissions**
   - Select your Google account
   - Click **Allow** (grants spreadsheet access)
4. Check **Execution log** at the bottom for the JSON response
5. Verify a row appeared in the `NPS_Data` tab of the spreadsheet
6. Run `testBatchUsage` to verify batch writes to `Usage_Data`

---

## Step 3: Deploy as Web App

1. In the Apps Script editor, click **Deploy > New deployment**
2. Click the gear icon next to "Select type" and choose **Web app**
3. Configure:
   - **Description:** `Metrics API v1`
   - **Execute as:** `Me` (your account)
   - **Who has access:** `Anyone` (within the Workspace org) or `Anyone with Google Account`
4. Click **Deploy**
5. Copy the **Web app URL** -- this is your endpoint

> **About "Who has access":**
> - `Anyone` = no authentication needed, any HTTP client can call it
> - `Anyone with Google Account` = caller must authenticate with Google
>
> For Claude Code / Python script usage, `Anyone` is simpler. The URL itself acts as a capability token (it contains a random deployment ID that is not guessable).

### Save the URL

The URL will look like:
```
https://script.google.com/macros/s/AKfycb.../exec
```

Store this somewhere safe. You will need it for the Python push scripts.

---

## Step 4: Test the Deployed Endpoint

### Using curl

```bash
# Single NPS row
curl -L -H "Content-Type: application/json" \
  -d '{
    "metric_type": "nps",
    "data": {
      "Product": "Product A",
      "Month": "2026-01",
      "Score": -34,
      "Responses": 108,
      "Promoter_Pct": 13.0,
      "Passive_Pct": 40.7,
      "Detractor_Pct": 46.3,
      "Trend": "Flat",
      "Features_Launched": 0,
      "Interpretation": "Test row",
      "Link_Analysis": "",
      "Link_Pendo": ""
    }
  }' \
  "YOUR_WEB_APP_URL"

# Batch Usage rows
curl -L -H "Content-Type: application/json" \
  -d '{
    "metric_type": "usage",
    "data": [
      {
        "Product": "Product A",
        "Month": "2026-01",
        "Total_MAU": 145000,
        "Teacher_MAU": 28000,
        "Student_MAU": 117000,
        "Avg_DAU": 42000,
        "Peak_DAU": 58000,
        "DAU_MAU_Ratio": 0.29,
        "MoM_Change_Pct": 2.1
      },
      {
        "Product": "Product B",
        "Month": "2026-01",
        "Total_MAU": 890000,
        "Teacher_MAU": 95000,
        "Student_MAU": 795000,
        "Avg_DAU": 310000,
        "Peak_DAU": 420000,
        "DAU_MAU_Ratio": 0.35,
        "MoM_Change_Pct": -1.3
      }
    ]
  }' \
  "YOUR_WEB_APP_URL"
```

> **Important:** The `-L` flag is required. Apps Script returns a 302 redirect before the actual response.

### Using Python

```python
import requests
import json

URL = "YOUR_WEB_APP_URL"

payload = {
    "metric_type": "ux_bugs",
    "data": {
        "Quarter": "Q1 2026",
        "Project": "PROJ",
        "Total_Created": 12,
        "P1": 1,
        "P2": 3,
        "P3": 6,
        "P4": 2,
        "Total_Resolved": 8,
        "%_Remediated": 66.7,
        "%_Outside_TTR": 12.5,
        "Date": "2026-02-23"
    }
}

response = requests.post(URL, json=payload)
print(json.dumps(response.json(), indent=2))
```

---

## Updating the Deployment

When you edit the script code:

1. Click **Deploy > Manage deployments**
2. Click the pencil icon on your deployment
3. Change **Version** to **New version**
4. Click **Deploy**

> You must create a new version for changes to take effect. The URL stays the same.

---

## Payload Reference

### Single Row

```json
{
  "metric_type": "nps",
  "data": {
    "Product": "Product A",
    "Month": "2026-01",
    "Score": -34,
    ...
  }
}
```

### Batch (Array)

```json
{
  "metric_type": "usage",
  "data": [
    { "Product": "Product A", "Month": "2026-01", ... },
    { "Product": "Product B", "Month": "2026-01", ... },
    { "Product": "Product C", "Month": "2026-01", ... }
  ]
}
```

### Response Format

All responses include a `status` field (200, 400, 500, 503) and a `timestamp`.

**Success (200):**
```json
{
  "status": 200,
  "metric_type": "nps",
  "tab": "NPS_Data",
  "processed": 1,
  "inserted": 0,
  "updated": 1,
  "details": [
    { "action": "updated", "key": "product a||2026-01", "sheet_row": 5 }
  ],
  "timestamp": "2026-02-23T15:30:00.000Z"
}
```

**Validation Error (400):**
```json
{
  "status": 400,
  "error": "Row 0: missing required key field \"Product\"",
  "required_keys": ["Product", "Month"],
  "timestamp": "2026-02-23T15:30:00.000Z"
}
```

**Server Busy (503):**
```json
{
  "status": 503,
  "error": "Server busy, try again in a few seconds",
  "timestamp": "2026-02-23T15:30:00.000Z"
}
```

---

## Upsert Behavior

The API uses "upsert" logic -- update if exists, insert if new:

| Metric Type | Key Fields | Match Logic |
|------------|------------|-------------|
| `nps` | Product + Month | Case-insensitive match on both |
| `usage` | Product + Month | Case-insensitive match on both |
| `ux_bugs` | Quarter + Project | Case-insensitive match on both |

If you POST data for "Product A" + "2026-01" and that combination already exists in the tab, the existing row is overwritten with the new values. If it does not exist, a new row is appended.

---

## Quotas and Limits

| Limit | Value | Notes |
|-------|-------|-------|
| Execution time | 6 minutes | Per invocation; well within range for batch writes |
| Writes per minute | ~60 | Google Sheets API limit; batches count as multiple |
| Payload size | ~50 MB | POST body limit; effectively unlimited for this use case |
| Concurrent executions | 30 | Per user; LockService serializes writes to prevent collisions |

For this project's volume (3 metrics, monthly cadence, ~5-10 rows per push), these limits are irrelevant.

---

## Troubleshooting

**"Tab not found" error:**
- Verify tab names match exactly: `NPS_Data`, `Usage_Data`, `UXBugs_Data`
- Tab names are case-sensitive

**Empty response or HTML returned:**
- Add `-L` flag to curl (follow redirects)
- Verify the deployment URL is correct (not the editor URL)

**Authorization errors:**
- Re-run `testDoPost` from the editor to re-authorize
- Check that "Execute as: Me" is set in deployment

**Changes not reflected:**
- After editing code, you must create a new version under Manage deployments
- The URL does not change, but the version must be bumped

**Lock timeout (503):**
- Retry after a few seconds
- This only happens under concurrent requests, which is unlikely at monthly cadence
