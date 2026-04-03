#!/usr/bin/env python3
"""
Data Processing Library for NPS Analysis

Provides shared functions for:
- CSV manipulation and validation
- NPS metric calculations

Note: Pain point analysis is handled by Claude Code in Steps 5-6 (native LLM generation)
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


def calculate_nps_score(ratings: List[int]) -> Tuple[int, Dict]:
    """
    Calculate NPS score and breakdown

    Args:
        ratings: List of ratings (0-10)

    Returns:
        (nps_score, breakdown_dict)

    breakdown_dict contains:
        - total_responses
        - promoters (9-10)
        - promoter_pct
        - passives (7-8)
        - passive_pct
        - detractors (0-6)
        - detractor_pct
        - nps_score
    """
    total = len(ratings)
    if total == 0:
        return 0, {}

    promoters = sum(1 for r in ratings if r >= 9)
    passives = sum(1 for r in ratings if 7 <= r <= 8)
    detractors = sum(1 for r in ratings if r <= 6)

    promoter_pct = (promoters / total) * 100
    detractor_pct = (detractors / total) * 100
    passive_pct = (passives / total) * 100

    nps_score = round(promoter_pct - detractor_pct)

    return nps_score, {
        "total_responses": total,
        "promoters": promoters,
        "promoter_pct": round(promoter_pct / 100, 2),
        "passives": passives,
        "passive_pct": round(passive_pct / 100, 2),
        "detractors": detractors,
        "detractor_pct": round(detractor_pct / 100, 2),
        "nps_score": nps_score
    }




def read_pendo_csv(csv_path: Path) -> Tuple[List[Dict], List[str]]:
    """
    Read Pendo NPS CSV and extract data

    Args:
        csv_path: Path to CSV file

    Returns:
        (rows_list, column_names)
    """
    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        for row in reader:
            rows.append(row)

    return rows, columns


def validate_csv_completeness(rows: List[Dict], target_month: str) -> Tuple[bool, str]:
    """
    Validate that CSV contains complete month's data

    Args:
        rows: CSV rows
        target_month: Month in YYYY-MM format

    Returns:
        (is_complete, message)
    """
    if not rows:
        return False, "CSV is empty"

    # Parse target month
    year, month = map(int, target_month.split('-'))

    # Get first and last dates from CSV
    dates = []
    for row in rows:
        date_str = row.get('Date', '')
        if date_str:
            try:
                # Pendo format: "2025-11-01T00:00:00.000Z" or "2025-11-01 12:34:56" or "2025-11-01"
                # Extract date part (before T or space)
                if 'T' in date_str:
                    date_part = date_str.split('T')[0]
                else:
                    date_part = date_str.split(' ')[0]
                date_obj = datetime.strptime(date_part, '%Y-%m-%d')
                dates.append(date_obj)
            except ValueError:
                continue

    if not dates:
        return False, "No valid dates found in CSV"

    first_date = min(dates)
    last_date = max(dates)

    # Check if spans full month
    # First date should be in first 5 days of month
    # Last date should be in last 5 days of month
    if first_date.year == year and first_date.month == month and first_date.day <= 5:
        # Check last date
        if last_date.year == year and last_date.month == month and last_date.day >= 25:
            return True, f"Complete month: {first_date.date()} to {last_date.date()}"

    return False, f"Incomplete month: {first_date.date()} to {last_date.date()} (expected full {target_month})"


def extract_month_csv(source_csv: Path, target_month: str, output_csv: Path) -> None:
    """
    Extract specific month's data from source CSV

    Args:
        source_csv: Source CSV path
        target_month: Month in YYYY-MM format
        output_csv: Output CSV path
    """
    rows, columns = read_pendo_csv(source_csv)

    # Filter rows for target month
    year, month = map(int, target_month.split('-'))
    filtered_rows = []

    for row in rows:
        date_str = row.get('Date', '')
        if date_str:
            try:
                # Extract date part (before T or space)
                if 'T' in date_str:
                    date_part = date_str.split('T')[0]
                else:
                    date_part = date_str.split(' ')[0]
                date_obj = datetime.strptime(date_part, '%Y-%m-%d')
                if date_obj.year == year and date_obj.month == month:
                    filtered_rows.append(row)
            except ValueError:
                continue

    # Write filtered data
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(filtered_rows)


def get_collection_period(rows: List[Dict]) -> Tuple[str, str]:
    """
    Get first and last date from CSV rows

    Returns:
        (first_date_str, last_date_str) in YYYY-MM-DD format
    """
    dates = []
    for row in rows:
        date_str = row.get('Date', '')
        if date_str:
            try:
                # Extract date part (before T or space)
                if 'T' in date_str:
                    date_part = date_str.split('T')[0]
                else:
                    date_part = date_str.split(' ')[0]
                date_obj = datetime.strptime(date_part, '%Y-%m-%d')
                dates.append(date_obj)
            except ValueError:
                continue

    if dates:
        first = min(dates).strftime('%Y-%m-%d')
        last = max(dates).strftime('%Y-%m-%d')
        return first, last

    return "", ""
