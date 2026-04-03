# Pendo Configuration

Connection and product-specific IDs for Pendo MCP and REST API queries. Used by `/nps` and `/usage` skills.

Copy this file to `pendo-config.md` and fill in your values.

## Connection

subscription_id: YOUR_PENDO_SUBSCRIPTION_ID

> Find this in Pendo: Settings > Subscription > the numeric ID in your Pendo URL (e.g., `app.pendo.io/s/XXXXXXXXXX/...`).

## NPS Products

Add one section per product you run NPS surveys for. The `/nps` skill matches the `short` code from invocation arguments (e.g., `/nps 2026-02 mc`).

### Product A

- name: Product Display Name
- short: p1
- folder: Product A
- guide_id: YOUR_NPS_GUIDE_ID
- numeric_poll_id: YOUR_NUMERIC_POLL_ID
- text_poll_id: YOUR_TEXT_POLL_ID
- surface_filter: YOUR_SURFACE_AREA_VALUE
- pendo_url: https://app.pendo.io/s/YOUR_SUB_ID/net-promoter-system/guides/YOUR_GUIDE_ID?surveys=true&view=nps-poll-metrics

> **guide_id:** Pendo > Guides > your NPS guide > the ID in the URL.
> **poll IDs:** Pendo aggregation API response — each poll in a guide has a unique short ID.
> **surface_filter:** The value your Pendo feature surfaces under — used for JPD watch list filtering.

### Product B

- name: Second Product
- short: p2
- folder: Product B
- guide_id: YOUR_NPS_GUIDE_ID
- numeric_poll_id: YOUR_NUMERIC_POLL_ID
- text_poll_id: YOUR_TEXT_POLL_ID
- surface_filter: YOUR_SURFACE_AREA_VALUE
- pendo_url: https://app.pendo.io/s/YOUR_SUB_ID/net-promoter-system/guides/YOUR_GUIDE_ID?surveys=true&view=nps-poll-metrics

## Usage Apps

Add one section per product. The `/usage` skill iterates all products listed here.

### Product A

- name: Product Display Name
- short: p1
- app_id: YOUR_PENDO_APP_ID
- entity_type: visitor

> **app_id:** Pendo > Settings > Applications > the numeric or string ID.
> **entity_type:** `visitor` for standalone apps (query at visitor level), `page` for apps where you track specific pages (query at page level with page IDs below).

### Product B

- name: Second Product
- short: p2
- app_id: YOUR_PENDO_APP_ID
- entity_type: page

## Segments

Pendo segment IDs for teacher/student (or equivalent role) breakdown. Find these in Pendo > People > Segments.

- Role A Teachers: YOUR_TEACHER_SEGMENT_ID
- Role A Students: YOUR_STUDENT_SEGMENT_ID
- Role B Teachers: YOUR_TEACHER_SEGMENT_ID
- Role B Students: YOUR_STUDENT_SEGMENT_ID

> Segment naming is flexible — the skills reference these by position in this file. Add as many role/segment pairs as your products need.

## Page IDs

Page-level tracking IDs for products that use `entity_type: page`. Find these in Pendo > Behavior > Pages.

- Product B Page 1 ("descriptive name"): YOUR_PAGE_ID
- Product B Page 2 ("descriptive name"): YOUR_PAGE_ID

> Only needed for products with `entity_type: page`. Products using `entity_type: visitor` skip page-level queries.

## YoY Lookup Table

Historical MAU data for year-over-year calculations when Pendo tracking notes don't cover the prior year period. This is typically needed when you migrated from a different analytics source (e.g., Snowflake) to Pendo mid-stream.

If your Pendo data covers 12+ months, you can leave this section empty — the `/usage` skill falls back to Pendo tracking notes for YoY.

| Month   | Product A | Product B | Notes |
|---------|-----------|-----------|-------|
| YYYY-MM | 123,456   | 789,012   | Source x calibration_factor |

> **Calibration factors:** If your historical source counted differently than Pendo (e.g., different session definitions), apply a calibration factor so YoY comparisons are apples-to-apples. Document the factor and source in the Notes column.
