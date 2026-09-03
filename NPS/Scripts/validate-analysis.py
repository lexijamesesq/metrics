#!/usr/bin/env python3
"""
Mechanical validator for NPS monthly analysis documents.

Reports findings; does not gate. The caller (the /nps skill, or the operator)
decides what passes. Exit code is always 0 unless the inputs themselves are
unreadable — a finding is data, not a failure.

Every check is grounded in a failure observed in this project's own outputs:
  quote fidelity     five of 42 quoted spans drifted from source CSV (two
                     substantive rewrites) while the in-context check
                     reported "all confirmed" (2026-07 audit)
  banned section     "Features launched this month" shipped in both 202601
                     analyses before the rule banning it
  same-value delta   "promoter percentage dropped from 9% to 9%" shipped
                     in cq-202601
  structure/counts   the six-section format and five-bullet pain list are
                     the published contract with the Google Docs mirror

Deliberately NOT checked: tracking-note arithmetic (score recompute, pct
sums, response counts). No such failure has ever been observed — audit
spot-checks passed. Revisit trigger: the first observed numeric drift
between script output and a tracking note reinstates that block (it
existed once; see git history).

Quote-match policy (explicit, so the check can't cry wolf):
  1. exact substring of a CSV Response          -> pass
  2. match after quote/apostrophe/dash/ellipsis
     normalization on both sides                -> pass (cosmetic), reported
  3. match ignoring case                        -> DRIFT-case (warn)
  4. match ignoring all whitespace differences  -> DRIFT-whitespace (warn)
  5. match after stripping internal punctuation
     (hyphens, commas, periods, apostrophes,
     quote marks) from both sides, whitespace
     ignored too                                -> DRIFT-punctuation (warn)
  6. no match at any rung                        -> DRIFT-content (error;
                                                  possible edit or fabrication)
  Rung 5 exists because documented American-style quote-mark punctuation and
  hyphenation variance is real drift but not fabrication: "real-time" vs
  "real time", a dropped Oxford comma, 'single' vs "double" quotes around a
  nested word. None of that changes what the respondent said. The error tier
  (rung 6 falling through) is reserved for fragments that match at NO rung —
  word-level edits or invented quotes, the failure mode that motivated this
  script: cq-202601 contained quotes ("worse than Classic", "better than
  alternatives") appearing nowhere in the source CSV.
  Quoted spans are split on ellipses and on " / " (both are splice markers:
  ellipses join excerpts, " / " renders a newline inside a CSV response).
  Trailing punctuation is stripped from each fragment before matching —
  American style places the sentence's comma or period inside the closing
  quote, and that punctuation belongs to the analysis, not the user.
  Fragments shorter than 12 characters after stripping are skipped as
  unmatchable noise and reported as 'skipped'.

AI-phrasing check (warn, check name 'ai-phrasing'): scans the whole document
body for two classes of stock phrasing seeded from project-local sources only
(Incubator artifact-critic kill-word list + lexi-persona review rubric):
  kill words   leverage, synergies, holistic, robust, utilize, meaningful,
               unprecedented, game-changing, transformed, drive outcomes,
               facilitate alignment, the practical upshot
  hedging      could potentially, might consider, it may be worth exploring,
               one might
One finding per distinct phrase with an occurrence count. Word-boundary
matching with inflection handling where marked (leverage, synergies, utilize).
Do NOT add terms from org-level style guides or "universal AI tells" — only
terms grounded in a project the operator owns. Structural AI-writing signals
(smoothness, near-list prose, connective tics, restated points) are judgment
checks that belong in the fresh-context critic, not in a regex.

Usage:
  python3 validate-analysis.py --analysis "NPS/Analysis/MasteryConnect/mc-nps-analysis-202604.md" \
      --csv "NPS/Data/MasteryConnect/nps-2026-04.csv" \
      [--persist-to "NPS/Tracking/mc-nps-2026-04.md"]

Output: JSON to stdout: {analysis, csv, findings: [{severity, check, detail}],
summary: {error, warn, info, quotes_checked, quotes_passed}}.

With --persist-to <tracking-note>, writes validation_run / validation_verdict /
validation_errors / validation_warnings into the note's frontmatter, so the
run is closable from the record instead of from ephemeral chat output.
validation_run is a date — a timestamp must never read as a verdict, so
pass/fail lives in its own key: validation_verdict is 'fail' iff the error
count is > 0, else 'pass'. Any prior run's keys (including the legacy
'validated' key) are replaced, not appended, so re-running is idempotent.
If the persist write itself fails, that failure is appended as a finding
and the stdout summary counts are recomputed to include it — a persist
failure must be visible in the same run's output, not silently swallowed
by counts that were tallied before the failure existed.

KNOWN LIMITATION (by design — do not claim this tool covers it): a quote
that is a genuine contiguous substring of a longer response passes as exact
even if the omitted context materially changes the meaning (misleading
truncation). Substring containment cannot judge materiality; that is the
separate-context critic's responsibility, not a mechanical check.
"""

import argparse
import csv
import json
import re
import sys
import unicodedata

EXPECTED_SECTIONS = ["Summary", "Top Pain Points", "3 Things That Matter",
                     "What's Working", "The Signal", "Document Links"]
BANNED_SECTION_PAT = re.compile(r"features?\s+launched", re.I)
MIN_FRAGMENT = 12

# Internal punctuation stripped for the DRIFT-punctuation rung: hyphens,
# commas, periods, apostrophes, straight/curly quote marks (already folded
# to straight by normalize()), colons, semicolons, and terminal punctuation.
# Whitespace is stripped too so hyphenated and spaced word-boundary variants
# ("real-time" / "real time") land on the same string.
_PUNCT_CHARS = "-,.'\";:!?()"
_PUNCT_RE = re.compile("[" + re.escape(_PUNCT_CHARS) + "]")

# AI-phrasing check: kill words and hedging patterns from two project-local
# sources — Incubator's artifact-critic (strategy-doc voice conformance) and
# lexi-persona's review rubric (corporate/AI phrasing). Do not add terms from
# org-level style guides or "universal AI tells" — only terms grounded in a
# project the operator owns. Multi-word patterns use \s+ so line-wrapped
# markdown doesn't defeat detection.
AI_KILL_WORDS = [
    ("leverage", re.compile(r"\bleverag(?:e|es|ed|ing)\b", re.I)),
    ("synergies", re.compile(r"\bsynerg(?:y|ies)\b", re.I)),
    ("holistic", re.compile(r"\bholistic\b", re.I)),
    ("robust", re.compile(r"\brobust\b", re.I)),
    ("utilize", re.compile(r"\butiliz(?:e|es|ed|ing)\b", re.I)),
    ("meaningful", re.compile(r"\bmeaningful\b", re.I)),
    ("unprecedented", re.compile(r"\bunprecedented\b", re.I)),
    ("game-changing", re.compile(r"\bgame[- ]changing\b", re.I)),
    ("transformed", re.compile(r"\btransformed\b", re.I)),
    ("drive outcomes", re.compile(r"\bdrive\s+outcomes\b", re.I)),
    ("facilitate alignment", re.compile(r"\bfacilitate\s+alignment\b", re.I)),
    ("the practical upshot", re.compile(r"\bthe\s+practical\s+upshot\b", re.I)),
]
AI_HEDGING = [
    ("could potentially", re.compile(r"\bcould\s+potentially\b", re.I)),
    ("might consider", re.compile(r"\bmight\s+consider\b", re.I)),
    ("it may be worth exploring", re.compile(r"\bit\s+may\s+be\s+worth\s+exploring\b", re.I)),
    ("one might", re.compile(r"\bone\s+might\b", re.I)),
]
AI_PHRASES = AI_KILL_WORDS + AI_HEDGING


def normalize(s):
    s = unicodedata.normalize("NFKC", s)
    for a, b in [("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"'),
                 ("–", "-"), ("—", "-"), ("…", "..."), (" ", " ")]:
        s = s.replace(a, b)
    return s


def squash(s):
    return re.sub(r"\s+", " ", s).strip()


def depunct(s):
    """Strip internal punctuation and whitespace for the punctuation-
    insensitive match rung. Word content (letters/digits) is untouched, so
    a genuine word-level edit ("needs" vs "need", "student" vs "students")
    still fails to match here."""
    s = _PUNCT_RE.sub("", s)
    return re.sub(r"\s+", "", s).lower()


def find_sections(text):
    """Return list of (title, start, end) for ## sections."""
    heads = [(m.group(1).strip(), m.start()) for m in re.finditer(r"^##\s+(.+)$", text, re.M)]
    out = []
    for i, (title, start) in enumerate(heads):
        end = heads[i + 1][1] if i + 1 < len(heads) else len(text)
        out.append((title, start, end))
    return out


def extract_quotes(text):
    """Quoted spans (curly or straight double quotes), with offsets."""
    spans = []
    for m in re.finditer(r'[“"]([^“”"]{4,}?)[”"]', text, re.S):
        spans.append((m.group(1), m.start()))
    return spans


def check_quote(quote, responses_norm, responses_raw):
    """Apply the match policy to one quoted span. Returns (verdict, detail)."""
    fragments = [f.strip() for f in re.split(r"…|\.\.\.|\s/\s", quote)]
    fragments = [re.sub(r"[,.;:!?]+$", "", f).strip() for f in fragments]
    fragments = [f for f in fragments if f]
    results = []
    for frag in fragments:
        if len(frag) < MIN_FRAGMENT:
            results.append(("skipped", frag))
            continue
        if any(frag in r for r in responses_raw):
            results.append(("exact", frag))
            continue
        nf = squash(normalize(frag))
        if any(nf in r for r in responses_norm):
            results.append(("cosmetic", frag))
            continue
        if any(nf.lower() in r.lower() for r in responses_norm):
            results.append(("DRIFT-case", frag))
            continue
        if any(re.sub(r"\s+", "", nf).lower() in re.sub(r"\s+", "", r).lower()
               for r in responses_norm):
            results.append(("DRIFT-whitespace", frag))
            continue
        if any(depunct(nf) in depunct(r) for r in responses_norm):
            results.append(("DRIFT-punctuation", frag))
            continue
        results.append(("DRIFT-content", frag))
    worst_order = ["DRIFT-content", "DRIFT-punctuation", "DRIFT-whitespace",
                   "DRIFT-case", "cosmetic", "exact", "skipped"]
    worst = min((r[0] for r in results), key=worst_order.index, default="skipped")
    return worst, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--persist-to",
                    help="Tracking note whose frontmatter receives "
                         "validation_run/validation_verdict/validation_errors/"
                         "validation_warnings keys")
    args = ap.parse_args()

    try:
        text = open(args.analysis, encoding="utf-8").read()
        rows = list(csv.DictReader(open(args.csv, encoding="utf-8-sig")))
    except OSError as e:
        sys.exit(f"error: {e}")

    resp_col = "Response" if rows and "Response" in rows[0] else (list(rows[0]) if rows else ["Response"])[0]
    responses_raw = [r.get(resp_col) or "" for r in rows]
    responses_norm = [squash(normalize(r)) for r in responses_raw]

    findings = []

    def add(sev, check, detail):
        findings.append({"severity": sev, "check": check, "detail": detail})

    # --- structure ---
    sections = find_sections(text)
    titles = [t for t, _, _ in sections]
    for s in EXPECTED_SECTIONS:
        if s not in titles:
            add("error", "section-missing", f"required section '## {s}' not found")
    order_actual = [t for t in titles if t in EXPECTED_SECTIONS]
    order_expected = [s for s in EXPECTED_SECTIONS if s in order_actual]
    if order_actual != order_expected:
        add("error", "section-order", f"sections out of order: {order_actual}")
    for t in titles:
        if t not in EXPECTED_SECTIONS:
            add("warn", "section-unexpected", f"unexpected section '## {t}'")
    for m in re.finditer(r"^(?:#{2,4}\s*|\*\*)\s*features?\s+launched[^\n]*", text, re.M | re.I):
        add("error", "banned-section", f"banned 'Features launched' block present: {m.group(0)[:80]!r}")

    def section_text(name):
        for t, s, e in sections:
            if t == name:
                return text[s:e]
        return ""

    # --- pain points: exactly 5 bullets, no quotes, no percentages ---
    pp = section_text("Top Pain Points")
    if pp:
        bullets = re.findall(r"^\s*[-*]\s+(.+)$", pp, re.M)
        if len(bullets) != 5:
            add("error", "pain-point-count", f"{len(bullets)} bullets (spec: exactly 5)")
        for b in bullets:
            if re.search(r'[“"]', b):
                add("warn", "pain-point-quote", f"bullet contains a quote: {b[:60]}")
            if re.search(r"\d+\s*%", b):
                add("warn", "pain-point-frequency", f"bullet contains a percentage: {b[:60]}")

    # --- 3 Things That Matter: exactly 3 bold headers ---
    ttm = section_text("3 Things That Matter")
    if ttm:
        # Colon lands inside or outside the bold (**X**: and **X:** both occur)
        holders = re.findall(r"^\*\*[^*]+\*\*\s*:|^\*\*[^*]+:\*\*", ttm, re.M)
        if len(holders) != 3:
            add("error", "three-things-count", f"{len(holders)} bold theme headers (spec: 3)")

    # --- The Signal: <=2 paragraphs, no bold headers ---
    sig = section_text("The Signal")
    if sig:
        body = re.sub(r"^##\s+.+$", "", sig, count=1, flags=re.M).strip()
        paras = [p for p in re.split(r"\n\s*\n", body) if p.strip()]
        if len(paras) > 2:
            add("warn", "signal-paragraphs", f"{len(paras)} paragraphs (spec: 1, max 2)")
        if re.search(r"\*\*[^*]+\*\*", body):
            add("error", "signal-bold-header", "bold text in The Signal (spec: prose only)")

    # --- same-value delta prose ---
    for m in re.finditer(
            r"from\s+(-?\d+(?:\.\d+)?)\s*(%|points?)?\s+(?:to|down to|up to)\s+(-?\d+(?:\.\d+)?)\s*(%|points?)?",
            text, re.I):
        if m.group(1) == m.group(3):
            add("error", "same-value-delta", f"delta prose with identical values: {m.group(0)!r}")

    # --- quote fidelity ---
    checked = passed = 0
    for section_name in ("3 Things That Matter", "What's Working", "The Signal", "Summary"):
        stext = section_text(section_name)
        for quote, _ in extract_quotes(stext):
            checked += 1
            verdict, results = check_quote(quote, responses_norm, responses_raw)
            if verdict in ("exact", "skipped"):
                passed += 1
            elif verdict == "cosmetic":
                passed += 1
                add("info", "quote-cosmetic",
                    f"[{section_name}] normalized-only match: {quote[:70]!r}")
            else:
                frag_details = [f"{v}: {f[:60]!r}" for v, f in results if v.startswith("DRIFT")]
                add("error" if verdict == "DRIFT-content" else "warn",
                    f"quote-{verdict.lower()}",
                    f"[{section_name}] {'; '.join(frag_details)}")

    # --- AI-phrasing: whole document body, one finding per distinct phrase ---
    body_norm = normalize(text)
    for label, pat in AI_PHRASES:
        hits = pat.findall(body_norm)
        if hits:
            add("warn", "ai-phrasing", f"{label!r} found {len(hits)}x")

    def tally():
        s = {"error": 0, "warn": 0, "info": 0}
        for f in findings:
            s[f["severity"]] += 1
        return s

    sev = tally()

    if args.persist_to:
        from datetime import date as _date
        verdict_str = "fail" if sev["error"] > 0 else "pass"
        persisted = False
        try:
            note_text = open(args.persist_to, encoding="utf-8").read()
            parts = note_text.split("---", 2)
            if len(parts) < 3:
                add("warn", "persist-failed", f"{args.persist_to}: no frontmatter block")
            else:
                fm_body = parts[1]
                for key in ("validated", "validation_run", "validation_verdict",
                            "validation_errors", "validation_warnings"):
                    fm_body = re.sub(rf"^{key}:.*\n", "", fm_body, flags=re.M)
                fm_body = fm_body.rstrip("\n") + (
                    f"\nvalidation_run: {_date.today().isoformat()}"
                    f"\nvalidation_verdict: {verdict_str}"
                    f"\nvalidation_errors: {sev['error']}"
                    f"\nvalidation_warnings: {sev['warn']}\n")
                open(args.persist_to, "w", encoding="utf-8").write(
                    "---" + fm_body + "---" + parts[2])
                persisted = True
        except OSError as e:
            add("warn", "persist-failed", str(e))

        if not persisted:
            # The finding just appended must show up in the counts this run
            # reports -- a persist failure that isn't visible in the summary
            # is a failure that shipped quietly.
            sev = tally()
    json.dump({
        "analysis": args.analysis,
        "csv": args.csv,
        "csv_rows": len(rows),
        "findings": findings,
        "summary": {**sev, "quotes_checked": checked, "quotes_passed": passed},
    }, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
