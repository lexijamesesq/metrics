#!/usr/bin/env python3
"""
UX Bugs quarterly metrics calculator.

Deterministic calculation home for the /ux-bugs skill. The skill collects raw
bug data via Atlassian MCP and writes a snapshot JSON; this script computes
quarterly metrics from that snapshot. One home for the calculation truth —
the skill formats and writes, it does not re-derive arithmetic.

Usage:
  python3 collect-ux-bugs.py --snapshot "UX Bugs/Data/ux-bugs-data-2026-07-07.json"
  python3 collect-ux-bugs.py --snapshot <path> --config jira-config.md
  python3 collect-ux-bugs.py --snapshot <path> --ttr "P1=45,P2=60,P3=180"

Config resolution (public-safe: this file carries no installation values):
  --ttr overrides; otherwise TTR windows are parsed from the config file's
  "## TTR Windows" > "### UX Bugs" subsection. The functional-bug windows in
  the same file are never read — UX bugs use UX windows only.

Output: JSON to stdout.
  projects.<KEY>.quarters[]: quarter metrics + status flag
    status: "complete"    — quarter ended before collection date
            "in_progress" — collection date falls inside the quarter
            "future"      — quarter starts after collection date
    The script computes and reports every quarter; the CALLER decides what to
    write and push (convention: future quarters are never published).
  projects.<KEY>.current_state: open-bug counts and TTR violations as of the
    collection date, with both the all-open denominator and the TTR-scope
    (customer-reported P1-P3) denominator reported separately.

Metric definitions (this script is the single home — SKILL.md Step 5
invokes the script but does not restate these definitions):
  total_created   customer-reported bugs (open + resolved) created in quarter
  p1..p4          customer-reported created in quarter, by priority
  total_resolved  customer-reported bugs resolved in quarter
  pct_remediated  total_resolved / total_created (0 if none created; may
                  exceed 1.0 — resolved is a cross-cohort count by design)
  pct_outside_ttr scope: customer-reported P1-P3 open during the quarter.
                  A bug counts as outside TTR only for violations that have
                  actually occurred: deadline <= min(quarter end, collection
                  date) and the bug was still open after the deadline.
                  For completed quarters this is identical to the historical
                  rule; for in-progress quarters it stops counting deadlines
                  that have not yet passed.
"""

import argparse
import json
import re
import sys
from datetime import date, timedelta

TTR_PRIORITIES = ("P1", "P2", "P3")  # P4 has no UX TTR window


def parse_date(s):
    return date.fromisoformat(s.split("T")[0])


def parse_ttr_arg(s):
    out = {}
    try:
        for part in s.split(","):
            k, v = part.split("=")
            out[k.strip()] = int(v)
    except ValueError:
        sys.exit(f"error: --ttr expects 'P1=45,P2=60,P3=180' form, got {s!r}")
    return out


def parse_ttr_from_config(path):
    """Parse the '### UX Bugs' subsection under '## TTR Windows'."""
    text = open(path, encoding="utf-8").read()
    m = re.search(r"^## TTR Windows.*?^### UX Bugs[^\n]*\n(.*?)(?=^###|^## |\Z)",
                  text, re.M | re.S)
    if not m:
        raise ValueError(f"No '## TTR Windows' > '### UX Bugs' section in {path}")
    out = {}
    for pm in re.finditer(r"^-\s*(P\d)\s*:\s*(\d+)", m.group(1), re.M):
        out[pm.group(1)] = int(pm.group(2))
    if not out:
        raise ValueError(f"UX Bugs TTR subsection in {path} contains no 'P<n>: <days>' lines")
    return out


def quarter_bounds(year, q):
    starts = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}
    ends = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
    return (date(year, *starts[q]), date(year, *ends[q]))


def ttr_deadline(bug, windows):
    days = windows.get(bug["priority"])
    if days is None:
        return None
    return parse_date(bug["created"]) + timedelta(days=days)


def quarter_metrics(open_bugs, resolved_bugs, year, q, collection_date, windows, warnings):
    q_start, q_end = quarter_bounds(year, q)
    if q_start > collection_date:
        status = "future"
    elif q_end < collection_date:
        status = "complete"
    else:
        status = "in_progress"

    cust_open = [b for b in open_bugs if b.get("customer_reported")]
    cust_resolved = [b for b in resolved_bugs if b.get("customer_reported")]

    created_in_q = [b for b in cust_open + cust_resolved
                    if q_start <= parse_date(b["created"]) <= q_end]
    resolved_in_q = [b for b in cust_resolved
                     if b.get("resolved") and q_start <= parse_date(b["resolved"]) <= q_end]

    prio = {"P1": 0, "P2": 0, "P3": 0, "P4": 0}
    other = 0
    for b in created_in_q:
        if b["priority"] in prio:
            prio[b["priority"]] += 1
        else:
            other += 1
            warnings.append(f"{b['key']}: unrecognized priority {b['priority']!r} "
                            f"counted as 'other', excluded from P1-P4 and TTR scope")

    total_created = len(created_in_q)
    total_resolved = len(resolved_in_q)
    pct_remediated = round(total_resolved / total_created, 2) if total_created else 0

    # TTR scope: customer-reported P1-P3 open at some point during the quarter.
    scope = []
    for b in cust_open:
        if b["priority"] in TTR_PRIORITIES and parse_date(b["created"]) <= q_end:
            scope.append(b)
    for b in cust_resolved:
        if (b["priority"] in TTR_PRIORITIES and b.get("resolved")
                and parse_date(b["created"]) <= q_end
                and parse_date(b["resolved"]) >= q_start):
            scope.append(b)

    violation_cutoff = min(q_end, collection_date)
    outside = []
    for b in scope:
        dl = ttr_deadline(b, windows)
        if dl is None or dl > violation_cutoff:
            continue  # no window, or deadline not yet passed by cutoff
        if "resolved" in b and b.get("resolved"):
            if parse_date(b["resolved"]) > dl:
                outside.append(b["key"])
        else:
            outside.append(b["key"])

    pct_outside_ttr = round(len(outside) / len(scope), 2) if scope else 0

    return {
        "quarter": f"Q{q} {year}",
        "quarter_short": f"{year}-q{q}",
        "status": status,
        "total_created": total_created,
        "p1": prio["P1"], "p2": prio["P2"], "p3": prio["P3"], "p4": prio["P4"],
        "other_priority": other,
        "total_resolved": total_resolved,
        "pct_remediated": pct_remediated,
        "pct_outside_ttr": pct_outside_ttr,
        "outside_ttr_keys": sorted(outside),
        "ttr_scope_count": len(scope),
        "has_data": bool(total_created or total_resolved or outside),
    }


def current_state(open_bugs, collection_date, windows):
    cust_scope = [b for b in open_bugs
                  if b.get("customer_reported") and b["priority"] in TTR_PRIORITIES]
    violations = []
    for b in cust_scope:
        dl = ttr_deadline(b, windows)
        if dl and dl <= collection_date:
            violations.append({
                "key": b["key"], "priority": b["priority"],
                "summary": b["summary"], "created": b["created"],
                "ttr_deadline": dl.isoformat(),
            })
    violations.sort(key=lambda v: v["ttr_deadline"])
    return {
        "open_total": len(open_bugs),
        "ttr_scope_open": len(cust_scope),
        "violations": violations,
        "pct_of_all_open": round(len(violations) / len(open_bugs), 2) if open_bugs else 0,
        "pct_of_ttr_scope": round(len(violations) / len(cust_scope), 2) if cust_scope else 0,
    }


def main():
    ap = argparse.ArgumentParser(description="Compute quarterly UX bug metrics from a snapshot JSON")
    ap.add_argument("--snapshot", required=True, help="Path to ux-bugs-data-YYYY-MM-DD.json")
    ap.add_argument("--config", default="jira-config.md",
                    help="Config file with '## TTR Windows' > '### UX Bugs' (default: jira-config.md)")
    ap.add_argument("--ttr", help="Override TTR windows, e.g. 'P1=45,P2=60,P3=180'")
    ap.add_argument("--collection-date", help="Override collection date (default: snapshot as_of_date)")
    ap.add_argument("--years", help="Comma-separated years (default: collection year and prior)")
    args = ap.parse_args()

    snapshot = json.load(open(args.snapshot, encoding="utf-8"))
    collection = parse_date(args.collection_date or snapshot["as_of_date"])

    if args.ttr:
        windows = parse_ttr_arg(args.ttr)
    else:
        try:
            windows = parse_ttr_from_config(args.config)
        except (OSError, ValueError) as e:
            sys.exit(f"error: no --ttr given and config unusable: {e}")

    years = ([int(y) for y in args.years.split(",")] if args.years
             else [collection.year - 1, collection.year])

    warnings = []
    projects = {}
    for key, data in snapshot.items():
        if not isinstance(data, dict) or "open_bugs" not in data:
            continue
        quarters = [quarter_metrics(data["open_bugs"], data["resolved_bugs"],
                                    y, q, collection, windows, warnings)
                    for y in years for q in (1, 2, 3, 4)]
        projects[key] = {
            "quarters": quarters,
            "current_state": current_state(data["open_bugs"], collection, windows),
        }

    json.dump({
        "as_of_date": snapshot.get("as_of_date"),
        "collection_date": collection.isoformat(),
        "ttr_windows": windows,
        "years": years,
        "projects": projects,
        "warnings": sorted(set(warnings)),
    }, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
