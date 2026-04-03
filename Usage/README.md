# /usage -- Monthly DAU/MAU Collection

Collects Monthly Active Users (MAU), Daily Active Users (DAU), and DAU/MAU engagement ratio for configured products via Pendo MCP. Writes individual data notes with YAML frontmatter and optionally pushes to Google Sheets.

## Invocation

```
/usage 2026-02
```

Defaults to previous month if no argument given. Takes ~2-3 minutes for all products.

## What it produces

- **Data notes:** One file per product in `Usage/Tracking/{short}-usage-{YYYY-MM}.md` with YAML frontmatter (total MAU, teacher/student breakdown, avg/peak DAU, DAU/MAU ratio, MoM and YoY change)
- **Google Sheets push:** All products posted as a batch to the Usage_Data tab (non-blocking -- skipped if Sheets is not configured)
- **Summary table:** Displayed in the conversation after collection

## Configuration

This skill reads `pendo-config.md` at Step 0. Required fields:

| Field | Section | What to set |
|-------|---------|-------------|
| `subscription_id` | Connection | Your Pendo subscription ID |
| App entries | Usage Apps | One entry per product with `app_id` and `entity_type` (`visitor` or `page`) |
| Segment IDs | Segments | Teacher/student (or equivalent role) segment IDs per platform |
| Page IDs | Page IDs | Pendo page IDs for products using `entity_type: page` |
| YoY lookup table | YoY Lookup Table | Optional -- historical MAU data for year-over-year when Pendo notes don't cover the prior year |

## Query patterns

The skill demonstrates three Pendo MCP query patterns depending on how your products are instrumented:

1. **Visitor-level** (`entity_type: visitor`) -- queries at the visitor level with segment filters. Used when the entire app maps to one product.
2. **Page-level, single page** (`entity_type: page`, one page ID) -- queries a specific page with segment filters. Used when your product is a feature within a larger platform.
3. **Page-level, multi-page** (`entity_type: page`, multiple page IDs) -- queries separate pages for different roles (e.g., authoring vs. consumption). Each page is paired with a role segment.

Adapt the steps to match your products' Pendo instrumentation.

## Prerequisites

- Pendo MCP server configured in Claude Code
- `pendo-config.md` populated with your product IDs and segments
