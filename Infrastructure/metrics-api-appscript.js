/**
 * Design Metrics API - Google Apps Script Web App
 *
 * Accepts JSON payloads via doPost() and writes to specific tabs
 * in the Design Metrics Google Sheet.
 *
 * Target Sheet: [your Google Sheet ID — set SHEET_ID constant below]
 *
 * Supported metric_type values: nps, usage, ux_bugs
 * Accepts single row or batch (array) payloads.
 *
 * Upsert behavior:
 *   - NPS/Usage: match on Product + Month
 *   - UX Bugs: match on Quarter + Project
 *
 * Month field: payload sends YYYY-MM (e.g. "2026-01"), written as M/D/YYYY (e.g. "1/1/2026").
 * Sheets parses this as a date; the column's custom MMMM yyyy format handles display.
 */

// ─── Configuration ──────────────────────────────────────────────────────────

const SHEET_ID = '[enter sheet id here]';

const CONFIG = {
  nps: {
    tabName: 'NPS_Data',
    columns: [
      'Product', 'Month', 'Score', 'Responses',
      'Promoter_Pct', 'Passive_Pct', 'Detractor_Pct',
      'MoM_Change_Pct', 'Interpretation',
      'Link_Analysis', 'Link_Pendo'
    ],
    keyFields: ['Product', 'Month']
  },
  usage: {
    tabName: 'Usage_Data',
    columns: [
      'Product', 'Month', 'Total_MAU', 'Teacher_MAU',
      'Student_MAU', 'Avg_DAU', 'Peak_DAU',
      'DAU_MAU_Ratio', 'MoM_Change_Pct', 'YoY_Change_Pct'
    ],
    keyFields: ['Product', 'Month']
  },
  ux_bugs: {
    tabName: 'UXBugs_Data',
    columns: [
      'Quarter', 'Project', 'Total_Created', 'P1', 'P2', 'P3', 'P4',
      'Total_Resolved', '%_Remediated', '%_Outside_TTR', 'Date'
    ],
    keyFields: ['Quarter', 'Project']
  }
};

// ─── Entry Point ────────────────────────────────────────────────────────────

/**
 * Handles incoming POST requests.
 *
 * Expected payload shape:
 * {
 *   "metric_type": "nps" | "usage" | "ux_bugs",
 *   "data": { ... } | [{ ... }, { ... }]
 * }
 */
function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents);
    const metricType = payload.metric_type;
    const data = payload.data;

    // Validate metric_type
    if (!metricType || !CONFIG[metricType]) {
      return jsonResponse(400, {
        error: 'Invalid or missing metric_type',
        valid_types: Object.keys(CONFIG)
      });
    }

    // Validate data
    if (!data) {
      return jsonResponse(400, { error: 'Missing "data" field in payload' });
    }

    // Normalize to array for uniform handling
    const rows = Array.isArray(data) ? data : [data];
    if (rows.length === 0) {
      return jsonResponse(400, { error: 'Empty data array' });
    }

    // Validate required key fields exist in each row
    const config = CONFIG[metricType];
    for (let i = 0; i < rows.length; i++) {
      for (const key of config.keyFields) {
        if (rows[i][key] === undefined || rows[i][key] === null || rows[i][key] === '') {
          return jsonResponse(400, {
            error: `Row ${i}: missing required key field "${key}"`,
            required_keys: config.keyFields
          });
        }
      }
    }

    // Acquire lock to prevent concurrent write collisions
    const lock = LockService.getScriptLock();
    if (!lock.tryLock(30000)) {
      return jsonResponse(503, { error: 'Server busy, try again in a few seconds' });
    }

    try {
      const result = upsertRows(metricType, rows);
      SpreadsheetApp.flush();
      return jsonResponse(200, result);
    } finally {
      lock.releaseLock();
    }

  } catch (err) {
    return jsonResponse(500, {
      error: 'Internal error',
      message: err.message
    });
  }
}

// ─── Core Upsert Logic ─────────────────────────────────────────────────────

/**
 * For each incoming row, find an existing row by key fields and update it,
 * or append a new row if no match is found.
 *
 * Returns a summary of inserted and updated counts.
 */
function upsertRows(metricType, rows) {
  const config = CONFIG[metricType];
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const sheet = ss.getSheetByName(config.tabName);

  if (!sheet) {
    throw new Error(`Tab "${config.tabName}" not found in spreadsheet`);
  }

  // Read existing data (row 1 = headers)
  const lastRow = sheet.getLastRow();
  const lastCol = config.columns.length;

  // Build index of key columns (0-based positions in our column config)
  const keyIndices = config.keyFields.map(k => config.columns.indexOf(k));

  // Read existing sheet data to find matches
  let existingData = [];
  if (lastRow > 1) {
    existingData = sheet.getRange(2, 1, lastRow - 1, lastCol).getValues();
  }

  let inserted = 0;
  let updated = 0;
  const details = [];

  for (const row of rows) {
    // Convert YYYY-MM fields to "Month YYYY" text before key comparison and write
    const processedRow = Object.assign({}, row);
    for (const col of config.columns) {
      const val = processedRow[col];
      if (typeof val === 'string' && /^\d{4}-\d{2}$/.test(val.trim())) {
        processedRow[col] = toMDYYYY(val.trim());
      }
    }

    // Build the key for this incoming row
    const incomingKey = config.keyFields.map(k => normalizeValue(processedRow[k])).join('||');

    // Search existing data for a match
    let matchRowIndex = -1;
    for (let i = 0; i < existingData.length; i++) {
      const existingKey = keyIndices.map(idx => normalizeValue(existingData[i][idx])).join('||');
      if (existingKey === incomingKey) {
        matchRowIndex = i;
        break;
      }
    }

    // Build the row values array in column order
    const rowValues = config.columns.map(col => {
      const val = processedRow[col];
      return val !== undefined ? val : '';
    });

    if (matchRowIndex >= 0) {
      // UPDATE existing row (matchRowIndex is 0-based in data, +2 for sheet row)
      const sheetRow = matchRowIndex + 2;
      sheet.getRange(sheetRow, 1, 1, lastCol).setValues([rowValues]);
      updated++;
      details.push({ action: 'updated', key: incomingKey, sheet_row: sheetRow });
    } else {
      // INSERT new row, copy full format from row above (includes borders + banding)
      const newRow = sheet.getLastRow() + 1;
      sheet.insertRowAfter(sheet.getLastRow());
      sheet.getRange(newRow - 1, 1, 1, lastCol).copyFormatToRange(sheet, 1, lastCol, newRow, newRow);
      sheet.getRange(newRow, 1, 1, lastCol).setValues([rowValues]);
      inserted++;
      // Also add to our in-memory data so subsequent rows in the same batch
      // can detect duplicates against this newly appended row
      existingData.push(rowValues);
      details.push({ action: 'inserted', key: incomingKey });
    }
  }

  return {
    metric_type: metricType,
    tab: config.tabName,
    processed: rows.length,
    inserted: inserted,
    updated: updated,
    details: details
  };
}

// ─── Helpers ────────────────────────────────────────────────────────────────

/**
 * Convert YYYY-MM string to M/D/YYYY text (e.g. "2026-01" → "1/1/2026").
 * Sheets parses this as a date and applies the column's custom format (MMMM yyyy).
 */
function toMDYYYY(yyyyMM) {
  const parts = yyyyMM.split('-');
  return parseInt(parts[1]) + '/1/' + parts[0];
}

/**
 * Normalize values for key comparison.
 * Existing date cells return as Date objects; incoming Month arrives as M/D/YYYY string.
 * Both normalize to YYYY-MM for comparison.
 */
function normalizeValue(val) {
  if (val instanceof Date) {
    return Utilities.formatDate(val, 'UTC', 'yyyy-MM');
  }
  if (typeof val === 'string') {
    // Normalize M/D/YYYY to YYYY-MM for comparison against existing date cells
    const mdyyyy = val.trim().match(/^(\d{1,2})\/1\/(\d{4})$/);
    if (mdyyyy) {
      return mdyyyy[2] + '-' + mdyyyy[1].padStart(2, '0');
    }
    return val.trim().toLowerCase();
  }
  return String(val).trim().toLowerCase();
}

/**
 * Build a JSON response with the given status code and body.
 * Note: Apps Script web apps always return HTTP 200 at the transport level.
 * The status field in the JSON body communicates logical success/failure.
 */
function jsonResponse(statusCode, body) {
  const output = {
    status: statusCode,
    ...body,
    timestamp: new Date().toISOString()
  };
  return ContentService
    .createTextOutput(JSON.stringify(output))
    .setMimeType(ContentService.MimeType.JSON);
}

// ─── Utility: Test Functions ─────────────────────────────────────────────────

/**
 * Run this from the Apps Script editor to test without deploying.
 * Simulates a doPost call with sample NPS data.
 */
function testDoPost() {
  const mockEvent = {
    postData: {
      contents: JSON.stringify({
        metric_type: 'nps',
        data: {
          Product: 'Product A',
          Month: '1900-01',
          Score: -34,
          Responses: 108,
          Promoter_Pct: 0.19,
          Passive_Pct: 0.29,
          Detractor_Pct: 0.53,
          MoM_Change_Pct: 0,
          Interpretation: 'Test row — safe to delete',
          Link_Analysis: 'https://example.com/analysis',
          Link_Pendo: 'https://example.com/pendo'
        }
      })
    }
  };

  const result = doPost(mockEvent);
  Logger.log(result.getContent());
}

/**
 * Run this to test UX Bugs data.
 */
function testUXBugs() {
  const mockEvent = {
    postData: {
      contents: JSON.stringify({
        metric_type: 'ux_bugs',
        data: {
          Quarter: 'Q1 1900',
          Project: 'PROJ',
          Total_Created: 5,
          P1: 0,
          P2: 1,
          P3: 4,
          P4: 0,
          Total_Resolved: 3,
          '%_Remediated': 0.6,
          '%_Outside_TTR': 0,
          Date: '3/5/2026'
        }
      })
    }
  };

  const result = doPost(mockEvent);
  Logger.log(result.getContent());
}

/**
 * Run this to test batch Usage data.
 */
function testBatchUsage() {
  const mockEvent = {
    postData: {
      contents: JSON.stringify({
        metric_type: 'usage',
        data: [
          {
            Product: 'Product A',
            Month: '1900-01',
            Total_MAU: 145000,
            Teacher_MAU: 28000,
            Student_MAU: 117000,
            Avg_DAU: 42000,
            Peak_DAU: 58000,
            DAU_MAU_Ratio: 0.29,
            MoM_Change_Pct: 0.021,
            YoY_Change_Pct: 0.15
          },
          {
            Product: 'Product B',
            Month: '1900-01',
            Total_MAU: 890000,
            Teacher_MAU: 95000,
            Student_MAU: 795000,
            Avg_DAU: 310000,
            Peak_DAU: 420000,
            DAU_MAU_Ratio: 0.35,
            MoM_Change_Pct: -0.013,
            YoY_Change_Pct: 0.25
          }
        ]
      })
    }
  };

  const result = doPost(mockEvent);
  Logger.log(result.getContent());
}
