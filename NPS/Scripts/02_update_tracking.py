#!/usr/bin/env python3
"""
Calculate NPS metrics from extracted CSV

Usage:
    python 02_update_tracking.py --month 2025-11 --product mc
    python 02_update_tracking.py --month 2025-11 --product cq

This script:
1. Reads extracted NPS CSV
2. Calculates NPS metrics (score, promoter/passive/detractor breakdown)
3. Prints results for use in Claude Code Steps 4-7

Note: Tracking is handled via structured data notes in NPS/Tracking/.
      Pain point analysis is handled by Claude Code in Steps 5-6.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from data_processing import (
    read_pendo_csv,
    calculate_nps_score
)


def format_month_display(month: str) -> str:
    """Convert YYYY-MM to 'Month YYYY' format"""
    date = datetime.strptime(month, '%Y-%m')
    return date.strftime('%B %Y')


def main():
    parser = argparse.ArgumentParser(description='Calculate metrics and update tracking CSVs')
    parser.add_argument('--month', required=True, help='Target month in YYYY-MM format (e.g., 2025-11)')
    parser.add_argument('--product', required=True, help='Product short code (e.g., mc, cq)')
    parser.add_argument('--data-dir', help='Product data directory name (default: derived from product code)')
    args = parser.parse_args()

    target_month = args.month
    product = args.product
    # Map product codes to folder names — add your products here or pass --data-dir
    PRODUCT_FOLDERS = {}  # e.g., {"p1": "Product One", "p2": "Product Two"}
    product_folder = args.data_dir or PRODUCT_FOLDERS.get(product, product)
    month_display = format_month_display(target_month)

    # Setup paths
    base_dir = Path(__file__).parent.parent
    nps_csv = base_dir / 'Data' / product_folder / f'nps-{target_month}.csv'
    score_tracking_csv = base_dir / 'Data' / product_folder / f'{product}-nps-score-tracking.csv'

    # Validate input file exists
    if not nps_csv.exists():
        print(f"❌ Error: NPS CSV not found: {nps_csv}")
        print(f"\nRun 01_extract_data.py first:")
        print(f"   python 01_extract_data.py --month {target_month} --product {product}")
        sys.exit(1)

    # Read NPS data
    print(f"\n📊 Reading NPS data for {month_display}...")
    try:
        rows, columns = read_pendo_csv(nps_csv)
        print(f"✓ Loaded {len(rows)} responses")
    except Exception as e:
        print(f"❌ Error reading NPS CSV: {e}")
        sys.exit(1)

    # Extract ratings and count comments
    ratings = []
    comment_count = 0

    for row in rows:
        # Rating column might be 'Rating', 'Score', or similar
        rating_value = row.get('Rating') or row.get('Score') or row.get('NPS Score')
        if rating_value:
            try:
                ratings.append(int(rating_value))
            except ValueError:
                pass

        # Count comments (non-empty Response field)
        response_value = row.get('Response', '').strip()
        if response_value:
            comment_count += 1

    if not ratings:
        print(f"⚠️  Warning: No ratings found in CSV")
        print(f"   Expected column: 'Rating', 'Score', or 'NPS Score'")
        sys.exit(1)

    # Calculate NPS metrics
    print(f"\n📈 Calculating NPS metrics...")
    nps_score, breakdown = calculate_nps_score(ratings)

    print(f"\nNPS Score: {nps_score}")
    print(f"  Total Responses: {breakdown['total_responses']}")
    print(f"  Promoters (9-10): {breakdown['promoters']} ({breakdown['promoter_pct']})")
    print(f"  Passives (7-8): {breakdown['passives']} ({breakdown['passive_pct']})")
    print(f"  Detractors (0-6): {breakdown['detractors']} ({breakdown['detractor_pct']})")
    print(f"  Comments: {comment_count} ({round((comment_count / breakdown['total_responses']) * 100, 1)}%)")

    # Success summary
    print(f"\n" + "="*60)
    print(f"✅ SUCCESS")
    print(f"="*60)
    print(f"Month: {month_display}")
    print(f"NPS Score: {nps_score}")
    print(f"Responses: {breakdown['total_responses']}")

    print(f"\nNext steps:")
    print(f"  1. Validate feature watch lists (Step 4a)")
    print(f"  2. Generate analysis with Claude Code (Step 6)")


if __name__ == '__main__':
    main()
