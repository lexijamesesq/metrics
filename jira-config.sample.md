# Jira Configuration

Atlassian connection details, project keys, and custom field IDs. Used by `/ux-bugs` and `/nps` (JPD watch list) skills.

Copy this file to `jira-config.md` and fill in your values.

## Connection

- cloud_id: YOUR_ATLASSIAN_CLOUD_ID
- base_url: YOUR_ORG.atlassian.net

> **cloud_id:** Run `mcp__atlassian__getAccessibleAtlassianResources()` — the `id` field in the response for your Jira instance.

## UX Bug Projects

Projects tracked for UX bug metrics. The `/ux-bugs` skill queries each project listed here. Add one line per Jira project key.

- YOUR_PROJECT_KEY_1
- YOUR_PROJECT_KEY_2

> These are the Jira project keys (e.g., `PROJ`) for projects that use a "Requirement Type" field to tag UX bugs.

## Custom Fields

### UX Bugs

- salesforce_count: customfield_XXXXX
- requirement_type_field: Requirement Type[Dropdown]
- requirement_type_value: UX

> **salesforce_count:** The custom field that tracks Salesforce case associations. Used to identify customer-reported bugs. Find this in Jira Admin > Issues > Custom Fields, or inspect a bug's API response.
> **requirement_type_field/value:** The field name and value used to filter UX bugs in JQL. Adjust to match your Jira configuration.

### JPD (Jira Product Discovery)

Used by `/nps` for the feature watch list — recently completed features that may appear in NPS feedback.

- project_key: YOUR_JPD_PROJECT_KEY
- surface_area: customfield_XXXXX
- target_quarter: customfield_XXXXX

> **project_key:** The Jira Product Discovery project where feature ideas are tracked.
> **surface_area:** JPD field that maps features to product areas (used to filter the watch list to the current NPS product).
> **target_quarter:** JPD field containing the target delivery quarter (e.g., "Q1 26").

## TTR Windows

Priority-based Time to Remediation windows (in days). Adjust these to match your organization's SLA commitments.

- P1: 45
- P2: 60
- P3: 180
- P4: null

> P4 has no TTR window — these bugs are tracked but not SLA-bound. Set `null` for any priority level without an SLA.
