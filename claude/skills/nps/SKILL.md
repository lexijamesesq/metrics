---
name: nps
description: This skill should be used when the user asks to "run NPS", "analyze NPS", "pull NPS data", or "generate NPS report". Runs the complete NPS monthly analysis workflow for one configured product via Pendo REST API and MCP.
argument-hint: [YYYY-MM] [mc|cq|all]
context: fork
allowed-tools:
  - mcp__atlassian__searchJiraIssuesUsingJql
  - mcp__pendo__surveyScores
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(python3:*)
  - Bash(date:*)
  - Bash(ls:*)
  - Bash(curl:*)
---

# /nps — Monthly NPS Analysis

Runs the complete NPS monthly analysis workflow for one configured product. Fetches NPS data via Pendo REST API, calculates metrics, queries recently-completed features as analysis context, performs qualitative analysis from direct CSV reading, and generates structured output.

## Intent

**Objective:** every published monthly analysis carries only verifiable user voice and a persisted validation verdict.

**Health metrics — must not degrade:**
- No quote reaches a published analysis unverified against the source CSV — cq-202601 shipped quotes no user wrote (found 2026-07-27).
- Validation results persist to the tracking note — the prior in-context check reported "all confirmed" over five drifted quotes (2026-07 audit).

## Invocation

```
/nps [YYYY-MM] [mc|cq|all]
```

**Bash execution format:** Run all bash commands as clean single-line commands. Do not prepend `#` comment lines — Claude Code's allowed-tools pattern matching operates on the full command string, and a `#` prefix will prevent the command from matching its allowed pattern and trigger an approval prompt.

Both arguments required:
- `YYYY-MM` — target month to analyze
- `mc`, `cq`, or `all` — product identifier (`all` runs both products in one invocation — see Arguments)

Examples:
- `/nps 2026-02 mc` — February 2026 analysis for product "mc"
- `/nps 2026-01 cq` — January 2026 analysis for product "cq"
- `/nps 2026-03 all` — March 2026 analysis for both mc and cq

## Arguments

Arguments are substituted positionally before this skill runs:
- `$0` = month (e.g., `2026-02`)
- `$1` = product (e.g., `mc`, `cq`, or `all`)

**The product is: `$1`**
**The month is: `$0`**

**`all` runs the complete pipeline for both products (mc, then cq) in one invocation.** Each product gets its own Steps 1–9 — its own CSV, analysis document, data note, validation run, and Sheets push. This is a config loop over the existing single-product flow, not new architecture: nothing below changes except that it runs twice, once per product.

The one shared step is Step 4's JPD watch list: the underlying `searchJiraIssuesUsingJql` query and quarter-scoping filter are fetched ONCE (not once per product) and that same quarter-filtered result is reused for both products — only the final surface-area filter (which produces each product's `JPD_WATCH_LIST`) runs per product. See Step 4.

The final summary reports per product when `$1` is `all` — two Step 8 validation blocks and two Step 9 Sheets push confirmations, each clearly labeled by product.

## Step 0: Load Configuration

### Pendo config

Read `pendo-config.md` from the project root. If the file is not found, stop and tell the user:

> "`pendo-config.md` not found in the project root. Copy `pendo-config.sample.md` to `pendo-config.md` and fill in your Pendo IDs to use this skill."

Extract the following values:

**From Connection:**
- `PENDO_SUB_ID` ← `subscription_id`

**From NPS Products — find the product whose `short` matches `$1`:**
- `PRODUCT_NAME` ← `name`
- `PRODUCT_SHORT` ← `short`
- `PRODUCT_FOLDER` ← `folder`
- `GUIDE_ID` ← `guide_id`
- `NUMERIC_POLL_ID` ← `numeric_poll_id`
- `TEXT_POLL_ID` ← `text_poll_id`
- `SURFACE_FILTER` ← `surface_filter`
- `PENDO_URL` ← `pendo_url`

**If `$1` is `all`:** run this entire skill (Steps 0–9) once per configured product short code (`mc`, then `cq`) — extract each product's values in turn at the top of its own iteration, then run its own Steps 1–9 before moving to the next product. The one exception is Step 4's JPD raw query and quarter-filter, which runs once and is shared — see Step 4 and the Arguments section.

**If `$1` does not match any product's `short` value, is missing, and is not `all`:** list available product short codes (plus `all`) from the config and stop.

### Jira config

Read `jira-config.md` from the project root. If the file is not found, stop and tell the user:

> "`jira-config.md` not found in the project root. Copy `jira-config.sample.md` to `jira-config.md` and fill in your values to use this skill."

Extract the following values:

**From Connection:**
- `CLOUD_ID` ← `cloud_id`

**From Custom Fields > JPD:**
- `JPD_PROJECT_KEY` ← `project_key`
- `JPD_SURFACE_AREA_FIELD` ← `surface_area`
- `JPD_TARGET_QUARTER_FIELD` ← `target_quarter`

### CLAUDE.md config

Read the `## Configuration` section of `CLAUDE.md` from the project root. Extract:

- `ONEPASSWORD_ITEM` ← `onepassword.pendo_api_key` (1Password item path, e.g., `op://VaultName/ItemName/credential`)
- `SHEETS_URL` ← `spreadsheet_url` (Google Sheets URL for analysis document links)

If the Configuration section is missing or either value is not found, warn the user and continue — these are used in Step 1 (1Password) and Step 6/9 (Sheets URL) respectively.

### Set derived variables

```
TARGET_MONTH   = "$0"
PRODUCT        = "{PRODUCT_SHORT}"
NPS_BASE       = "NPS"
DATA_DIR       = "{NPS_BASE}/Data/{PRODUCT_FOLDER}"
ANALYSIS_DIR   = "{NPS_BASE}/Analysis/{PRODUCT_FOLDER}"
SCRIPTS_DIR    = "{NPS_BASE}/Scripts"
DATA_NOTES_DIR = "NPS/Tracking"
```

State the resolved values, then proceed immediately to Step 1:
> "Running NPS analysis for **[PRODUCT_NAME]** (`[PRODUCT_SHORT]`), **[TARGET_MONTH]**."

## Configuration Reference

See `pendo-config.md` for Pendo connection details, guide IDs, and poll IDs.

See `jira-config.md` for Atlassian connection details and JPD field IDs.

See CLAUDE.md Configuration section for 1Password item path and Google Sheets URL.

---

## Step 1: Fetch NPS Data via REST API

```bash
python3 {SCRIPTS_DIR}/fetch-nps-responses.py --month {TARGET_MONTH} --product {PRODUCT_SHORT} --guide-id {GUIDE_ID} --numeric-poll-id {NUMERIC_POLL_ID} --text-poll-id {TEXT_POLL_ID} --data-dir {PRODUCT_FOLDER} --op-item {ONEPASSWORD_ITEM}
```

The script fetches the API key from 1Password using the `--op-item` path (or `PENDO_API_KEY` env var if set). If 1Password auth fails, the script exits with an error — stop execution and ask the user to run `op signin`.

This script:
- Fetches all NPS poll responses for TARGET_MONTH via Pendo aggregation API
- Correlates numeric scores with text comments by visitor
- Writes CSV to: `{DATA_DIR}/nps-{TARGET_MONTH}.csv`
- Prints summary (count, NPS score, score distribution)

Verify the output CSV exists and has a reasonable response count.

**Date validation:** If today is day 1 of the month following TARGET_MONTH, warn:
> "It's only [date]. Pendo NPS data for [TARGET_MONTH] may still be processing (timezone/international users). Recommend waiting until day 2-3. Proceed anyway?"

Wait for user confirmation.

**If REST API fails** (HTTP error, auth error):
> "Pendo REST API returned [error]. Check that the API key is valid. If the key is correct and the error persists, fall back to manual CSV download:
> - Download from Pendo dashboard: {PENDO_URL}
> - Save to `{DATA_DIR}/nps-{TARGET_MONTH}.csv`
> - Re-run /nps (Step 1 will be skipped if CSV exists)"

Stop execution.

## Step 2: Cross-Validate with MCP Survey Score

Call `mcp__pendo__surveyScores` for aggregate NPS validation. It returns `score` and `numResponses` per survey directly — no more hand-computing NPS in-context from a raw response distribution. (`guideMetrics`, this step's original tool, was retired from the Pendo MCP surface — verified 2026-07-27. `surveyResponses` served as the interim replacement but required reconstructing the score from `distribution` counts; `surveyScores` was verified as the direct-score drop-in on 2026-07-27 — see `Knowledge/pendo-mcp-capabilities.md`.)

```
mcp__pendo__surveyScores(
    subId="{PENDO_SUB_ID}",
    surveyId="{GUIDE_ID}",
    dateRange={"type": "absolute", "startDate": "{TARGET_MONTH}-01", "endDate": "{LAST_DAY_OF_MONTH}"}
)
```

`surveyId` set to the NPS guide ID narrows the result to that one survey — read `rows[0]` directly, no arithmetic:
- `mcp_score` ← `rows[0].score`
- `mcp_responses` ← `rows[0].numResponses`

**Cross-validation:** Compare REST results (Step 1 summary) with the MCP result:
- **MC:** response count should match closely; a small gap (a few responses) concentrated at month-end can occur when Pendo's raw event stream (queried by the REST fetch) lags the survey-scoring backend (queried by `surveyScores`). This is not a timezone/window bug — verified 2026-07-27: March matched exactly row-for-row via the same code path, and April's 3 extras were all late-month-end events. If the gap exceeds ~3 responses or ~3%, STOP — report both counts to the user and wait for their decision (re-run Step 1, or proceed) before continuing to Step 3; never silently absorb it. Score within 1 point (rounding)
- **CQ:** the REST pipeline filters to quiz-mentioning responses, so counts will NOT match the guide-wide aggregate — compare against the pre-filter total the fetch script prints (`CQ quiz filter: X of Y` — validate Y), and skip the score comparison (the published CQ score is computed over the filtered subset by design)

If mismatch > 1 point, warn user but continue.

**If MCP is unavailable or fails (tool not in environment, connection error, timeout, auth failure):** Stop immediately. Do not silently skip. Surface the failure to the user with this exact format:

> ⚠️ **Pendo MCP unavailable — cross-validation cannot run.**
>
> REST API returned: NPS [score], [count] responses for [TARGET_MONTH].
> MCP error: [specific error or "tool not available in this environment"].
>
> Cross-validation is normally run to catch REST API discrepancies. Without it, the REST API data is the only source.
>
> **Proceed without cross-validation?** (yes/no)

Wait for explicit user confirmation before continuing to Step 3. If the user declines, stop the run — no analysis document, no data note, no Sheets push.

This is non-blocking *only* with user consent. Never bury MCP unavailability as a footnote at the end of a run.

## Step 3: Calculate NPS Metrics (Python)

Run the tracking update script:

```bash
python3 {SCRIPTS_DIR}/02_update_tracking.py --month {TARGET_MONTH} --product {PRODUCT_SHORT} --data-dir {PRODUCT_FOLDER}
```

This script:
- Reads extracted NPS CSV
- Calculates NPS score, promoter/passive/detractor percentages
- Counts comments

Capture the console output for the calculated values:
- `NPS_SCORE`, `TOTAL_RESPONSES`
- `PROMOTER_PCT`, `PASSIVE_PCT`, `DETRACTOR_PCT`
- `COMMENT_COUNT`

## Step 4: Build JPD Watch List

**IMPORTANT — JPD limitation:** {JPD_PROJECT_KEY} is a Jira Product Discovery project. JPD custom fields cannot be filtered in JQL — they always return 0 results. Query by status only and filter in-memory.

```
mcp__atlassian__searchJiraIssuesUsingJql(
    cloudId="{CLOUD_ID}",
    jql='project = {JPD_PROJECT_KEY} AND status in ("3 - GTM", "Done") ORDER BY updated DESC',
    fields=["summary", "{JPD_SURFACE_AREA_FIELD}", "{JPD_TARGET_QUARTER_FIELD}", "status"],
    maxResults=100
)
```

**Quarter scoping:**
- Determine current quarter from TARGET_MONTH (e.g., Feb 2026 → Q1 26)
- Include prior 1 quarter (e.g., Q4 25)
- Filter in-memory: keep only features where `{JPD_TARGET_QUARTER_FIELD}.value` matches one of these 2 quarters
- Then filter by surface area: `"{SURFACE_FILTER}"` for the current product

**Custom field reference:**
- `{JPD_SURFACE_AREA_FIELD}`: Product Surface Area (array — value matching `"{SURFACE_FILTER}"`)
- `{JPD_TARGET_QUARTER_FIELD}`: Target Quarter (object — `.value` is `"Q1 26"` etc.)

Result: `JPD_WATCH_LIST` — list of `{key, summary, quarter, status}`

**Multi-product runs (`$1` = `all`):** run the `searchJiraIssuesUsingJql` query and the quarter-scoping filter above ONCE, not once per product. Reuse that single quarter-filtered result as the input to the surface-area filter for each product in turn — mc's `JPD_WATCH_LIST` and cq's `JPD_WATCH_LIST` are two different filtered views of the same shared raw fetch, not two separate Atlassian queries.

**Note:** JPD_WATCH_LIST represents features that recently completed development. These are not confirmed launch dates — JPD is a planning tool, not a release tracking tool. Use as reference context only: scan for these features being mentioned in NPS comments.

**If Atlassian MCP times out:**
> "Atlassian MCP timed out. Please exit and resume Claude Code to refresh the connection."

Stop and wait for user.

## Step 5: Build Evidence Base (CSV)

Read the extracted CSV at `{DATA_DIR}/nps-{TARGET_MONTH}.csv`. Read ALL comments before categorizing anything.

**This step produces a locked evidence base. Step 6 may only use quotes that appear in this output.**

### 5a: Identify themes and collect evidence

1. Read all comments in full before assigning any themes
2. Identify recurring themes organically from user language — NO hardcoded categories
3. Assign each comment a primary theme — for multi-issue comments, assign by the issue that takes the most space in the response (not the lead sentence or the strongest language). For CQ specifically, the CSV is pre-filtered to quiz-mentioning responses, so a comment that spends most of its words on a non-quiz platform issue still entered the dataset because of its quiz content — assign to the quiz-relevant issue, not the largest non-quiz portion
4. Collect verbatim quotes per theme — exact CSV text only, no paraphrasing, condensing, or grammar correction. Preserve the respondent's errors ("agonzing", "might needs") as-is; byte-verbatim fidelity overrides prior-month style conventions. The validator checks quotes against the CSV — a cleaned quote fails.

**Percentage calculation:** Count by primary theme per comment. Percentages of comments-with-text, descending order.

### 5b: Output structured evidence base

Produce this output in full before beginning Step 6:

```
EVIDENCE BASE: {TARGET_MONTH} {PRODUCT_NAME}

Theme counts (descending):
1. [Theme]: N comments (XX%)
2. [Theme]: N comments (XX%)
...

[Theme 1] — N comments
- "[verbatim quote from CSV]"
- "[verbatim quote from CSV]"
[Include all quotes worth potentially referencing — the analysis draws from this pool]

[Theme 2] — N comments
- "[verbatim quote from CSV]"
...

Promoter themes — N comments
- "[verbatim quote from CSV]"
...

JPD Watch List mentions:
- [Feature name]: mentioned / not mentioned
  [If mentioned: verbatim quote]

Total responses with text: N

LOCKED — Step 6 draws only from quotes above.
```

### 5c: Constraint for Step 6

Every quoted string in the analysis document must appear in the Evidence Base above. No quote may be introduced in Step 6 that was not recorded in Step 5b.

Pattern-level claims (observations about the distribution or character of multiple quotes) are permitted, but must accurately describe the evidence — do not characterize user sentiment, intent, or implication beyond what the quotes themselves show. If users didn't name something (trust, architecture, business impact), the analysis should not assert it. Present the evidence; let the reader draw the inference.

## Step 6: Generate Full Analysis Document

**CRITICAL: Before generating, read the 2 most recent analyses for the same product to ensure format consistency:**

```
Glob: {ANALYSIS_DIR}/{PRODUCT_SHORT}-nps-analysis-*.md
```

Sort by filename (YYYYMM), read the 2 most recent.

### Analysis Document Structure

Generate the complete analysis following this format:

**Filename:** `{ANALYSIS_DIR}/{PRODUCT_SHORT}-nps-analysis-{YYYYMM}.md`

(YYYYMM = TARGET_MONTH without hyphen, e.g., "202602")

---

#### Section 1: Summary

```markdown
## Summary

[First paragraph: Score context, response volume, comparison to previous month]

**Feedback breaks down as:**
* Category Name *(XX%)*
* Category Name *(XX%)*
[Derived from ORGANIC_TOPICS — themes identified organically from CSV comments, counted by primary theme per comment. Descending order, NO "Other" category. Target 8–12 categories; consolidate below that range, question your cuts above it]

[Commentary paragraph — ONLY include if one of these conditions is true:
1. A theme appears for the first time as a distinct cluster (flag it and explain why it's significant)
2. A theme that was dominant in prior months has meaningfully shifted in weight (state what moved and what that shift suggests about user behavior)
3. Two or more themes connect to reveal something about the user base that neither reveals alone

If none of these conditions apply, omit this paragraph entirely. Do NOT restate the percentages in prose. Do NOT build causal theories (seasonal patterns, school calendar, etc.) unless directly supported by a quote or verifiable pattern in the data. One focused sentence is better than a paragraph of plausible-sounding analysis.]
```

#### Section 2: Top Pain Points

```markdown
## Top Pain Points

- [Direct pain point statement - no quotes, no frequencies, no category labels]
- [...]
- [...]
- [...]
- [...]
```

Exactly 5 bullets. Simple statements only. **Intent:** the executive skim layer — what a VP reads in 10 seconds without opening any section. Cover the full surface of what users said, not just what gets deep analysis below. Themes that didn't make the top-three analytical cut still belong here if they represent real user pain. Overlap with 3 Things That Matter is natural when a theme is both broadly felt and analytically interesting — different altitude, different value.

#### Section 3: 3 Things That Matter

```markdown
## 3 Things That Matter

**[Organic theme header — a specific, analytical framing of the pattern, not a category label]**: [~100-150 words per section. Use 3-4 quotes maximum to demonstrate pattern. NO rating annotations like "(Rating: 9)".]

**[Organic theme header]**: [...]

**[Organic theme header]**: [...]
```

Headers are the top 3 themes from Step 5, framed analytically — describe what the pattern reveals, not just what category it falls into. Target total: 300-450 words across all three sections. **Intent:** the analytical depth layer — three themes chosen because they reveal something beyond their surface (a pattern, a shift, a contradiction), not simply because they're the largest. Selection criterion is "most analytically interesting," not "biggest." Overlap with Top Pain Points is fine — same topic, different job.

Ellipsis splices (`...`) join excerpts from the SAME response only — never composite quotes across respondents. If two respondents say similar things, quote them separately.

If JPD_WATCH_LIST features appear in comment scans (Step 5), reference them naturally here — e.g., "Users are asking about X, which recently completed development."

#### Section 4: What's Working

```markdown
## What's Working

**[Bold header describing positive pattern]**: [Promoter quote analysis. What users value when workflows function correctly.]
```

Claims about the promoter cohort must reflect the pattern across promoter quotes, not extrapolate from one. If only one promoter names a tradeoff, attribute it to that respondent — don't generalize it to the group.

#### Section 5: The Signal

```markdown
## The Signal

[One to two paragraphs of natural prose. No bold headers.]
```

**Purpose:** The Signal is the only section that operates across the dataset — not just this month. It asks: given this month in context of the full trend, what trajectory question is now open? What would answering it look like?

"3 Things That Matter" presents the evidence from this month. The Signal raises the hypothesis the next run will test. A reader who only reads The Signal should leave knowing what to watch for — not what happened.

**Default to one paragraph.** If two genuinely distinct trajectory questions are open, two paragraphs are acceptable — but attempt to unify them first. If both trace to the same underlying issue, one synthesized signal is stronger.

**No bold headers.** Prose only. Bold headers make The Signal read as a continuation of "3 Things That Matter" — exactly what it is not.

**Inclusion bar:** Only include a paragraph if it meets one of these criteria:
1. A theme appeared for the first time as a distinct cluster (2+ independent data points describing the same specific gap)
2. A recurring theme is showing directional change — growing or narrowing — that has implications for future months
3. A JPD Watch List feature warrants forward-looking commentary (appeared in comments, or has a specific user audience likely to surface with lag)

**Exclude:**
- Retrospective observations (confirming previous predictions) — those belong in the analysis body, not The Signal
- Single data points — one comment does not establish a pattern worth monitoring
- Restatements of themes already analyzed in "3 Things That Matter" — if it's already in the body, it doesn't belong here

**Each paragraph structure:**
1. State a trajectory question that advances beyond the prior month's. If last month's question was answered or partially answered, the retrospective belongs in the Summary or 3 Things That Matter — not here. Start forward.
2. Ground the question in this month's data — one or two factual anchors. Do not recap prior Signals or re-explain themes already covered in the analysis body.
3. State the confirmation condition: "If [specific observable thing] appears in [next month's] data, [conclusion] is confirmed." Required — a Signal without a testable hypothesis is a monitoring instruction, not a signal.

If JPD_WATCH_LIST features appeared in comment scans (Step 5), surface forward-looking commentary here. Frame as: "X recently completed development — early signals suggest..." rather than attributing a specific launch date.

#### Section 6: Document Links

```markdown
## Document Links

- **Spreadsheet:** [Design Metrics Google Sheet, NPS tab]({SHEETS_URL})
- **Source Data:** [Pendo NPS Survey - {MONTH YYYY}]({PENDO_URL})
```

## Step 7: Write Data Note

Write the NPS data note to the structured data store:

**File:** `{DATA_NOTES_DIR}/{PRODUCT_SHORT}-nps-{TARGET_MONTH}.md`

Always overwrite if file exists — the skill produces fresh data each run.

**Template:**

```yaml
---
type: metrics/nps
product: {PRODUCT_NAME}
product_short: {PRODUCT_SHORT}
month: "{TARGET_MONTH}"
month_date: {TARGET_MONTH}-01
score: {NPS_SCORE}
responses: {TOTAL_RESPONSES}
promoter_pct: {PROMOTER_PCT}   # decimal max 2 places, e.g. 0.24
passive_pct: {PASSIVE_PCT}     # decimal max 2 places, e.g. 0.25
detractor_pct: {DETRACTOR_PCT} # decimal max 2 places, e.g. 0.52
mom_change_pct: {TREND}
interpretation: "{WHY_CHANGED}"
# WHY_CHANGED: One sentence identifying the USER SEGMENT experiencing the problem + the SPECIFIC FRICTION they hit.
# Format: [who is affected] + [what specific problem they encounter]
# Target: ~100 characters. Hard max: 130 characters. If over 130, cut — do not add semicolons or em-dashes to append more detail.
# Answer "who hits what" — not "what did the score do" and not just "what themes appeared"
# Good: "ELA and social studies teachers hit question bank gaps that math teachers don't; academic integrity surfaces as new demand"
# Good: "Teachers managing multiple classes blocked by editing workflow that invalidates student data mid-assessment"
# Good: "Specialist teachers with 20-35 sections hit multi-section architecture built for 5-6 class loads"
# Bad: "Score improved 6 points; navigation friction persists; academic integrity surfaced as new category"
# Bad: "Navigation and content gaps dominate; new academic integrity cluster emerged this month"
link_analysis: "[[{PRODUCT_SHORT}-nps-analysis-{YYYYMM}]]"
link_pendo: "{PENDO_URL}"
link_csv: "NPS/Data/{PRODUCT_FOLDER}/nps-{TARGET_MONTH}.csv"
collected: {TODAY_DATE}
---

# {PRODUCT_NAME} NPS - {TARGET_MONTH}

Collected via /nps skill on {TODAY_DATE}.
```

**Validator-written keys (not written by this step):** `validation_run`, `validation_verdict`, `validation_errors`, `validation_warnings` are added to this note's frontmatter by Step 8's `validate-analysis.py --persist-to` call, not by Step 7. They appear only on notes produced by a run that reaches Step 8's validation. Never back-stamp these keys onto historical notes that predate the validator — a note's absence of these keys means it was never run through this validator, not that it failed one (operator boundary).

## Step 8: Validation Checks

Run automated validation:

1. **Metrics accuracy:**
   - NPS score = (Promoter % - Detractor %) × 100 (verify)
   - Response count matches extracted CSV row count
   - Percentages sum to ~100%
   - **Cross-validation:** If Step 2 MCP score was obtained, verify REST API score matches within 1 point

2. **Format compliance:**
   - 5 pain point bullets (no more, no fewer)
   - "Feedback breaks down as" categories are organically derived from CSV comments (not borrowed from any external taxonomy)
   - No rating annotations in quotes
   - `mom_change_pct` is integer (not "+3" or "↑ 3")
   - No "Features launched this month" subsection anywhere in the document
   - **Why Changed? answers "what drove sentiment" not "what did the score do"** — must describe the themes/pain points that dominated, not the score or its movement. Flag if it contains: score numbers, "improvement", "decline", "increased", "decreased", "from [month]", "cohort", response count references, "unchanged", or any framing that describes the score rather than the user experience

3. **Mechanical validation (script, not judgment):**

```bash
python3 "NPS/Scripts/validate-analysis.py" \
    --analysis "{ANALYSIS_DIR}/{PRODUCT_SHORT}-nps-analysis-{YYYYMM}.md" \
    --csv "{DATA_DIR}/nps-{TARGET_MONTH}.csv" \
    --persist-to "{DATA_NOTES_DIR}/{PRODUCT_SHORT}-nps-{TARGET_MONTH}.md"
```

The script checks quote fidelity against the CSV (byte-verbatim with an explicit splice/punctuation policy), section structure, pain-bullet count, banned sections, and same-value delta prose, then writes its verdict into the tracking note frontmatter so the run is closable from the record. Do NOT verify quotes by re-reading them in-context — that exact check reported "all confirmed" over five drifted quotes before this script existed.

**Gate:** if `validation_verdict` is `fail` (i.e., the script's error count is > 0), STOP. Do not proceed to Step 9 and do not report the run complete — fix the document, then re-run the validator until `validation_verdict` reads `pass`. Step 9 and run completion are blocked for as long as any error finding exists. `warn`/`info` findings are reported but never block — the operator reads them in the summary below.

4. **Fresh-context critic (separate context, never this one):**

Judgment checks must not run in the context that wrote the analysis — in-context self-review is the exact shape that reported "all confirmed" over five drifted quotes (2026-07 audit). Dispatch a subagent whose brief contains ONLY: the finished analysis document, the Step 5 Evidence Base, and the criteria below. No drafting history, no this-session reasoning.

Critic criteria (voice-agnostic — default Claude voice is fine per operator, 2026-07-27):

Content integrity:
- Any claim asserting user intent, emotional state, or implication not directly expressed in the quoted evidence
- Any quote technically verbatim but truncated so its meaning changes — the mechanical script cannot judge materiality (its documented limitation)
- Any quote that silently drops mid-sentence content without an ellipsis marker (observed pattern: cq-202604 dropped two parentheticals)

Structural quality (from Studio's judge rubric and LLM-technique research — smoothness and structure are stronger AI-detection signals than vocabulary):
- Near-list prose: does the writing "almost start listing things" where it should stay prose? (Studio C9)
- Connective tics: transitions carried by mechanical seams ("Which means,", "This highlights", "It's worth noting") rather than earned prose (Studio C10)
- Point restated across perspectives: is the same claim made more than once in different words? (Studio C6)
- Vague generality presented as a claim ("significant issues" — which ones?), labels where claims belong, a buried lead in the Summary

Economy:
- The 20%-cut test: name cuttable spans

Grading rule: criticisms carry full weight. Confirmations carry reduced weight — the critic inherits project context and its agreement may be echo, not independent derivation.

The critic REPORTS findings — it proposes no rewrites. Restrict its tools to Read only (no Edit, Write, or Bash). Apply what's valid, note what's rejected and why, one critic round plus one scoped re-check of applied fixes, cap 2. Critic findings never block mechanically (the script's error gate owns blocking); they are judgment input to the author before the document ships.

Report validation results:

```
Validation:
✓ NPS score: -34 (verified: 19% - 53% = -34)
✓ MCP cross-validation: -34 (within 1 point)
✓ Response count: 108 matches CSV
✓ Percentages sum: 100.2% (rounding acceptable)
✓ Format: 5 pain points, CSV-derived categories, no rating annotations, mom_change_pct is integer
✓ Why Changed?: user experience summary (no score meta-commentary)
✓ validate-analysis.py: errors=0 warn=N info=N, quotes N/N — verdict persisted to tracking note
```

## Step 9: Push to Google Sheets

Read the config:
```
Read: Infrastructure/sheets-api-config.md
```

If the file is missing, skip the push and say so in the summary — the Step 8 summary table is the operator's fallback for manual entry.

Extract `web_app_url` from the config, then POST:

```bash
python3 -c "
import urllib.request, json
payload = json.dumps({'metric_type':'nps','data':{'Product':'{PRODUCT_NAME}','Month':'{TARGET_MONTH}','Score':{NPS_SCORE},'Responses':{TOTAL_RESPONSES},'Promoter_Pct':{PROMOTER_PCT},'Passive_Pct':{PASSIVE_PCT},'Detractor_Pct':{DETRACTOR_PCT},'MoM_Change_Pct':{MOM_CHANGE_PCT},'Interpretation':'{WHY_CHANGED}','Link_Pendo':'{PENDO_URL}'}}).encode()
req = urllib.request.Request('{WEB_APP_URL}', data=payload, headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as r: print(r.read().decode())
"
```

- `Month` is YYYY-MM format (e.g. `"2026-02"`) — the script converts it to M/D/YYYY for Sheets
- `MoM_Change_Pct` is integer NPS points (e.g. `6`, not `0.06`)
- `Link_Analysis` is omitted from the payload entirely — never send `''`. Once the Apps Script's merge-on-update change is deployed (see `Infrastructure/metrics-api-appscript.js` and `Infrastructure/metrics-api-deployment.md`), an UPDATE branch preserves the existing cell value for any key absent from the payload, so a hand-added Google Doc link in that column survives future re-runs. Until the operator redeploys, an absent key still blanks the cell on update — do not re-push historical months before the redeploy.

Check the response `status` field. If `200`, report: `✓ Pushed to Google Sheets ({action}: {key})`. If not `200`, report the error but do not fail the skill — Sheets push is non-blocking.

## Error Handling

- **1Password failure:** Stop with setup instructions (op CLI, signin, item path)
- **REST API failure:** Show HTTP error, suggest checking API key. Provide manual CSV fallback instructions.
- **MCP `surveyScores` failure or unavailability:** Stop and surface to user (see Step 2). Never skip silently. Proceed only with explicit user consent.
- **Python script failure:** Show error output, suggest manual verification
- **Atlassian MCP timeout:** Stop and instruct user to exit/resume

## Legacy Fallback

If REST API is unavailable (key revoked, API changes), the manual CSV workflow still works:

1. Download NPS CSV from Pendo dashboard (URL available via `{PENDO_URL}`)
2. Run `python3 {SCRIPTS_DIR}/01_extract_data.py --month {TARGET_MONTH} --product {PRODUCT_SHORT} --data-dir {PRODUCT_FOLDER} --yes`
3. Continue from Step 3 onward (02_update_tracking.py reads the same CSV format)

The `01_extract_data.py` script is retained as a fallback. See deprecation note in that file.
