#!/usr/bin/env python3
"""
UX Bugs Monthly Data Collection Script

This script:
1. Queries Atlassian Jira for open and resolved UX bugs
2. Calculates quarterly metrics using calculated TTR (created + priority-based window)
3. Generates spreadsheet-ready markdown output
4. Saves monthly data snapshot as JSON

Usage:
  python collect-ux-bugs.py --date 2025-12-26

The script uses Atlassian MCP tools which must be called from Claude Code, not run standalone.
This file serves as the reference implementation for the monthly collection process.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================

# Configuration — set these to match your jira-config.md values
CLOUD_ID = "YOUR_ATLASSIAN_CLOUD_ID"
JIRA_BASE_URL = "YOUR_ORG.atlassian.net"

TTR_WINDOWS = {
    "P1": 45,   # days
    "P2": 60,
    "P3": 180,
    "P4": None  # No TTR defined
}

PROJECTS = ["YOUR_PROJECT_KEY"]

# Output directory relative to this script's parent (UX Bugs/)
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "Data"

# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def get_quarter_dates(year, quarter):
    """Return (start_date, end_date) for a given quarter"""
    quarters = {
        "Q1": (f"{year}-01-01", f"{year}-03-31"),
        "Q2": (f"{year}-04-01", f"{year}-06-30"),
        "Q3": (f"{year}-07-01", f"{year}-09-30"),
        "Q4": (f"{year}-10-01", f"{year}-12-31"),
    }
    return quarters[quarter]


def is_date_in_range(date_str, start_str, end_str):
    """Check if date falls within range (inclusive)"""
    date = datetime.strptime(date_str, "%Y-%m-%d")
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    return start <= date <= end


def calculate_ttr_deadline(created_str, priority):
    """Calculate TTR deadline from created date + priority-based TTR window"""
    created = datetime.strptime(created_str, "%Y-%m-%d")
    ttr_window = TTR_WINDOWS.get(priority)

    if ttr_window is None:
        return None  # P4 has no TTR

    return created + timedelta(days=ttr_window)


def is_outside_ttr(bug, as_of_date_str):
    """Check if bug is outside TTR using CALCULATED deadline"""
    ttr_deadline = calculate_ttr_deadline(bug["created"], bug["priority"])

    if ttr_deadline is None:
        return False  # P4 has no TTR

    as_of_date = datetime.strptime(as_of_date_str, "%Y-%m-%d")
    return as_of_date > ttr_deadline


def bugs_open_on_date(open_bugs, resolved_bugs, snapshot_date_str):
    """
    Return list of bugs that were open on a specific date
    A bug was open on snapshot_date if:
    - Created on or before snapshot_date AND
    - (Never resolved OR resolved after snapshot_date)
    """
    snapshot_date = datetime.strptime(snapshot_date_str, "%Y-%m-%d")
    bugs_open = []

    # Currently open bugs
    for bug in open_bugs:
        created = datetime.strptime(bug["created"], "%Y-%m-%d")
        if created <= snapshot_date:
            bugs_open.append(bug)

    # Resolved bugs that were still open on snapshot date
    for bug in resolved_bugs:
        created = datetime.strptime(bug["created"], "%Y-%m-%d")
        resolved = datetime.strptime(bug["resolved"], "%Y-%m-%d")

        if created <= snapshot_date and resolved > snapshot_date:
            bugs_open.append(bug)

    return bugs_open


# ============================================================================
# DATA TRANSFORMATION
# ============================================================================

def transform_open_bug(jira_bug):
    """Transform Atlassian MCP bug response to clean structure"""
    fields = jira_bug["fields"]

    # Extract date from datetime string (YYYY-MM-DDTHH:MM:SS.sss-TZ)
    created_full = fields["created"]
    created_date = created_full.split("T")[0]

    # Customer-reported logic: YOUR_SALESFORCE_COUNT_FIELD (Salesforce Count) exists and > 0
    salesforce_count = fields.get("YOUR_SALESFORCE_COUNT_FIELD")
    customer_reported = salesforce_count is not None and salesforce_count > 0

    return {
        "key": jira_bug["key"],
        "summary": fields["summary"],
        "priority": fields["priority"]["name"],
        "created": created_date,
        "duedate": fields.get("duedate"),  # May be null
        "status": fields["status"]["name"],
        "customer_reported": customer_reported
    }


def transform_resolved_bug(jira_bug):
    """Transform resolved bug from Atlassian MCP"""
    fields = jira_bug["fields"]

    created_full = fields["created"]
    created_date = created_full.split("T")[0]

    resolved_full = fields.get("resolutiondate")
    resolved_date = resolved_full.split("T")[0] if resolved_full else None

    salesforce_count = fields.get("YOUR_SALESFORCE_COUNT_FIELD")
    customer_reported = salesforce_count is not None and salesforce_count > 0

    return {
        "key": jira_bug["key"],
        "summary": fields["summary"],
        "priority": fields["priority"]["name"],
        "created": created_date,
        "resolved": resolved_date,
        "project": fields["project"]["key"],
        "customer_reported": customer_reported
    }


# ============================================================================
# METRICS CALCULATION
# ============================================================================

def calculate_quarterly_metrics(open_bugs, resolved_bugs, year, as_of_date):
    """Calculate all quarterly metrics for all quarters"""
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    results = []

    for quarter in quarters:
        start_date, end_date = get_quarter_dates(year, quarter)

        # Total Created: bugs created in this quarter (open + resolved)
        open_created_this_q = [b for b in open_bugs if is_date_in_range(b["created"], start_date, end_date)]
        resolved_created_this_q = [b for b in resolved_bugs if is_date_in_range(b["created"], start_date, end_date)]
        total_created = len(open_created_this_q) + len(resolved_created_this_q)

        # Total Resolved: bugs resolved in this quarter
        total_resolved = len([b for b in resolved_bugs if is_date_in_range(b["resolved"], start_date, end_date)])

        # % Remediated: (resolved in Q) / (created in Q) as decimal
        pct_remediated = (total_resolved / total_created) if total_created > 0 else 0

        # Priority breakdown: customer-reported bugs CREATED in this quarter
        priority_counts = {"P1": 0, "P2": 0, "P3": 0, "P4": 0}

        for bug in open_created_this_q:
            if bug["customer_reported"]:
                priority_counts[bug["priority"]] += 1

        for bug in resolved_created_this_q:
            if bug["customer_reported"]:
                priority_counts[bug["priority"]] += 1

        # % Outside TTR: (Bugs outside TTR at any point during quarter) / (All bugs open during quarter)
        # Bugs open during quarter: created <= quarter end, not resolved before quarter start
        bugs_open_during_quarter = []

        # Currently open bugs created by quarter end
        for bug in open_bugs:
            created = datetime.strptime(bug["created"], "%Y-%m-%d")
            quarter_end = datetime.strptime(end_date, "%Y-%m-%d")
            if created <= quarter_end:
                bugs_open_during_quarter.append(bug)

        # Resolved bugs that were open at some point during quarter
        for bug in resolved_bugs:
            created = datetime.strptime(bug["created"], "%Y-%m-%d")
            resolved = datetime.strptime(bug["resolved"], "%Y-%m-%d")
            quarter_start = datetime.strptime(start_date, "%Y-%m-%d")
            quarter_end = datetime.strptime(end_date, "%Y-%m-%d")

            # Was open during quarter if: created before/during quarter AND resolved during/after quarter
            if created <= quarter_end and resolved >= quarter_start:
                bugs_open_during_quarter.append(bug)

        # Bugs outside TTR at any point during quarter
        # Bug counts if: TTR deadline <= quarter end AND bug was still open after deadline
        if bugs_open_during_quarter:
            outside_ttr_bugs = []
            quarter_end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            for bug in bugs_open_during_quarter:
                ttr_deadline = calculate_ttr_deadline(bug["created"], bug["priority"])

                if ttr_deadline and ttr_deadline <= quarter_end_dt:
                    # Check if bug was still open after TTR deadline
                    # If resolved, check if resolved AFTER deadline
                    if "resolved" in bug:
                        resolved_dt = datetime.strptime(bug["resolved"], "%Y-%m-%d")
                        if resolved_dt > ttr_deadline:
                            outside_ttr_bugs.append(bug)
                    else:
                        # Still open, so it's outside TTR
                        outside_ttr_bugs.append(bug)

            pct_outside_ttr = (len(outside_ttr_bugs) / len(bugs_open_during_quarter))
        else:
            pct_outside_ttr = 0

        results.append({
            "quarter": f"{quarter} {year}",
            "total_created": total_created,
            "p1": priority_counts["P1"],
            "p2": priority_counts["P2"],
            "p3": priority_counts["P3"],
            "p4": priority_counts["P4"],
            "total_resolved": total_resolved,
            "pct_remediated": pct_remediated,
            "pct_outside_ttr": pct_outside_ttr,
        })

    return results


# ============================================================================
# OUTPUT GENERATION
# ============================================================================

def generate_spreadsheet_output(project, metrics, open_bugs, as_of_date, output_path):
    """
    Update single markdown file with this project's section.

    File contains separate section per project. This function:
    - Reads existing file (if exists) to preserve other projects
    - Regenerates this project's complete section
    - Combines all project sections
    - Writes to spreadsheet-ready.md (no date in filename)
    """
    import re

    # Generate this project's section
    project_lines = []

    project_lines.append(f"## {project}")
    project_lines.append("")
    project_lines.append("### Summary Metrics Table")
    project_lines.append("")
    project_lines.append("**Copy/paste ready for Google Sheets _Data tab (percentages as decimals):**")
    project_lines.append("")
    project_lines.append("| Quarter | Total Created | P1 | P2 | P3 | P4 | Total Resolved | % Remediated | % Outside TTR |")
    project_lines.append("|---------|---------------|----|----|----|----|----------------|--------------|---------------|")

    for m in metrics:
        project_lines.append(
            f"| {m['quarter']} | {m['total_created']} | "
            f"{m['p1']} | {m['p2']} | {m['p3']} | {m['p4']} | "
            f"{m['total_resolved']} | {m['pct_remediated']:.2f} | {m['pct_outside_ttr']:.2f} |"
        )

    project_lines.append("")
    project_lines.append("### Bugs Outside TTR Window")
    project_lines.append("")

    # Find bugs currently outside TTR
    outside_ttr = [b for b in open_bugs if is_outside_ttr(b, as_of_date)]

    if outside_ttr:
        project_lines.append("| Bug ID | Priority | Summary | Created | TTR Deadline | Link |")
        project_lines.append("|--------|----------|---------|---------|--------------|------|")

        for bug in outside_ttr:
            link = f"https://{JIRA_BASE_URL}/browse/{bug['key']}"
            summary = bug['summary'][:60] + "..." if len(bug['summary']) > 60 else bug['summary']
            ttr_deadline = calculate_ttr_deadline(bug['created'], bug['priority'])
            deadline_str = ttr_deadline.strftime('%Y-%m-%d') if ttr_deadline else "N/A"
            project_lines.append(f"| {bug['key']} | {bug['priority']} | {summary} | {bug['created']} | {deadline_str} | {link} |")
    else:
        project_lines.append("No bugs outside TTR window.")

    project_lines.append("")
    project_lines.append("### Current State Summary")
    project_lines.append("")

    total_open = len(open_bugs)
    total_outside_ttr = len(outside_ttr)
    pct_outside = (total_outside_ttr / total_open * 100) if total_open > 0 else 0

    project_lines.append(f"**{project}:** {total_open} open bugs, {total_outside_ttr} outside TTR ({pct_outside:.0f}%)")

    project_section = "\n".join(project_lines)

    # Read existing file to preserve other projects' data
    existing_sections = {}
    if output_path.exists():
        with open(output_path, 'r') as f:
            content = f.read()

        # Parse existing project sections (## Project Name headers)
        pattern = r'## ([^\n]+)\n\n(.*?)(?=\n##|\n---|\Z)'
        for match in re.finditer(pattern, content, re.DOTALL):
            proj_name = match.group(1).strip()
            section_content = match.group(2).strip()
            if proj_name != project:
                existing_sections[proj_name] = section_content

    # Build complete file with all projects
    today = datetime.now().strftime('%Y-%m-%d')

    # Project order: matches PROJECTS configuration
    project_order = PROJECTS

    # Build sections for each project
    all_sections = []

    for proj_name in project_order:
        if proj_name == project:
            # Current project - use fresh section
            all_sections.append(project_section)
        elif proj_name in existing_sections:
            # Existing project - preserve its section
            section = f"## {proj_name}\n\n{existing_sections[proj_name]}"
            all_sections.append(section)

    content = f"""# UX Bugs Spreadsheet Data

**Generated:** {today}
**Data as of:** {as_of_date}

## Copy/Paste to UXBugs_Data Tab

{chr(10).join(all_sections)}

---

## Notes

- All quarterly metrics calculated from {as_of_date} Jira data pull
- Customer-reported bugs only for priority breakdown (P1-P4 columns)
- % Outside TTR uses **calculated TTR** (created date + priority-based window):
  - P1: 45 days, P2: 60 days, P3: 180 days, P4: None
- Resolved dates retrieved using `resolutiondate` field from Atlassian API
"""

    with open(output_path, 'w') as f:
        f.write(content)

    return content


# ============================================================================
# MAIN COLLECTION PROCESS
# ============================================================================

def main():
    """
    Main collection process - to be called from Claude Code using Atlassian MCP

    This function outline shows what needs to happen, but the actual MCP calls
    must be made from Claude Code, not from this script.
    """
    print("="*80)
    print("UX BUGS MONTHLY DATA COLLECTION")
    print("="*80)
    print("")
    print("This script defines the collection process but requires Atlassian MCP calls")
    print("from Claude Code. See monthly-data-collection-process.md for full instructions.")
    print("")
    print("Collection steps:")
    print("1. Query Atlassian MCP for open bugs (per configured project)")
    print("2. Query Atlassian MCP for resolved bugs (per configured project)")
    print("3. Transform data using transform_open_bug() and transform_resolved_bug()")
    print("4. Calculate metrics using calculate_quarterly_metrics()")
    print("5. Generate output using generate_spreadsheet_output()")
    print("6. Save data snapshot as JSON")
    print("")
    print("See test-collection-v2.py for working example with test data.")


if __name__ == "__main__":
    main()
