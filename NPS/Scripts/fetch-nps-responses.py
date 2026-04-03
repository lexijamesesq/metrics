#!/usr/bin/env python3
"""
Fetch NPS responses from Pendo REST API

Usage:
    python3 fetch-nps-responses.py --month 2026-02 --product mc
    python3 fetch-nps-responses.py --month 2026-02 --product myproduct --guide-id XXX --numeric-poll-id YYY --text-poll-id ZZZ --op-item "op://Vault/Item/credential"

This script:
1. Fetches all NPS poll responses for a given month via Pendo aggregation API
2. Correlates numeric scores with text responses by visitor
3. Writes CSV in the same format as legacy Pendo CSV export

Output: {DATA_DIR}/nps-{TARGET_MONTH}.csv (or --output path)

Dependencies: Python stdlib only (no pip installs required)
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from calendar import monthrange
from datetime import datetime, timezone

# Built-in product configuration — override with CLI args for portability
# Fill in your Pendo guide/poll IDs, or pass --guide-id/--numeric-poll-id/--text-poll-id
PRODUCTS = {
    # "product_short": {
    #     "guide_id": "YOUR_GUIDE_ID",
    #     "numeric_poll_id": "YOUR_NUMERIC_POLL_ID",
    #     "text_poll_id": "YOUR_TEXT_POLL_ID",
    #     "data_dir": "Product Folder Name"
    # },
}

# Default 1Password item path — override with --op-item or PENDO_API_KEY env var
DEFAULT_OP_ITEM = "op://VaultName/PendoAPIKey/credential"  # Override with --op-item or PENDO_API_KEY env var

API_URL = "https://app.pendo.io/api/v1/aggregation"

CSV_COLUMNS = ['Visitor ID', 'Date', 'Rating', 'Response Group', 'Response',
               'NPS Themes', 'Channel']


def epoch_ms(dt):
    """Convert datetime to epoch milliseconds"""
    return int(dt.timestamp() * 1000)


def get_month_boundaries(month_str):
    """Return (start_ms, end_ms) epoch boundaries for a YYYY-MM month.

    Start is inclusive (first ms of month), end is exclusive (first ms of next month).
    """
    year, month = map(int, month_str.split('-'))
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return epoch_ms(start), epoch_ms(end)


def get_month_days(month_str):
    """Return number of days in a YYYY-MM month"""
    year, month = map(int, month_str.split('-'))
    return monthrange(year, month)[1]


def fetch_poll_responses(api_key, guide_id, poll_id, start_ms, month_days):
    """Fetch all responses for a specific poll within a time range.

    Uses the Pendo aggregation API with pollEvents source and timeSeries.
    Returns list of dicts with visitorId, accountId, pollResponse, browserTime.
    """
    pipeline = [
        {
            "source": {
                "pollEvents": {
                    "guideId": guide_id,
                    "pollId": poll_id
                },
                "timeSeries": {
                    "period": "dayRange",
                    "first": start_ms,
                    "count": month_days
                }
            }
        },
        {
            "select": {
                "visitorId": "visitorId",
                "accountId": "accountId",
                "pollResponse": "pollResponse",
                "browserTime": "browserTime"
            }
        }
    ]

    payload = {
        "response": {"mimeType": "application/json"},
        "request": {"pipeline": pipeline}
    }

    headers = {
        "x-pendo-integration-key": api_key,
        "Content-Type": "application/json"
    }

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
        method='POST'
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            # Response is {"startTime": ..., "results": [...]}
            if isinstance(data, dict) and 'results' in data:
                return data['results']
            # Fallback if response is already a list
            if isinstance(data, list):
                return data
            return data
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        raise Exception(
            f"HTTP {e.code}: {e.reason}\nResponse: {body[:500]}"
        )


def response_group(score):
    """Map NPS score (0-10) to response group label"""
    if score >= 9:
        return "Promoter"
    elif score >= 7:
        return "Passive"
    else:
        return "Detractor"


def format_date(epoch_ms_val):
    """Convert epoch ms to YYYY-MM-DD HH:MM:SS format matching legacy CSV"""
    dt = datetime.fromtimestamp(epoch_ms_val / 1000, tz=timezone.utc)
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def main():
    parser = argparse.ArgumentParser(
        description='Fetch NPS responses from Pendo REST API'
    )
    parser.add_argument(
        '--month', required=True,
        help='Target month in YYYY-MM format (e.g., 2026-02)'
    )
    parser.add_argument(
        '--product', required=True,
        help='Product short code (must match a key in PRODUCTS dict, or use --guide-id/--numeric-poll-id/--text-poll-id to override)'
    )
    parser.add_argument(
        '--output',
        help='Override output CSV path (default: Data/{product}/nps-{month}.csv)'
    )
    parser.add_argument(
        '--guide-id',
        help='Override Pendo guide ID (default: from PRODUCTS dict)'
    )
    parser.add_argument(
        '--numeric-poll-id',
        help='Override Pendo numeric poll ID (default: from PRODUCTS dict)'
    )
    parser.add_argument(
        '--text-poll-id',
        help='Override Pendo text poll ID (default: from PRODUCTS dict)'
    )
    parser.add_argument(
        '--data-dir',
        help='Override data directory name (default: from PRODUCTS dict)'
    )
    parser.add_argument(
        '--op-item',
        help='Override 1Password item path (default: from DEFAULT_OP_ITEM constant)'
    )
    args = parser.parse_args()

    # Validate month format
    try:
        year, month = map(int, args.month.split('-'))
        if not (1 <= month <= 12):
            raise ValueError
    except (ValueError, AttributeError):
        print(f"Error: Invalid month format '{args.month}'. Use YYYY-MM.")
        sys.exit(1)

    # Get API key — from environment or 1Password
    api_key = os.environ.get("PENDO_API_KEY")
    if not api_key:
        op_item = args.op_item or DEFAULT_OP_ITEM
        try:
            result = subprocess.run(
                ["op", "read", op_item],
                capture_output=True, text=True, check=True
            )
            api_key = result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print("Error: Could not retrieve API key.")
            print("Ensure 1Password CLI is installed and authenticated (`op signin`).")
            print(f"1Password item: {op_item}")
            print(f"Detail: {e}")
            sys.exit(1)

    # Resolve product config — CLI args override PRODUCTS dict
    if args.product in PRODUCTS:
        product = PRODUCTS[args.product].copy()
    else:
        product = {"guide_id": None, "numeric_poll_id": None, "text_poll_id": None, "data_dir": args.product}

    if args.guide_id:
        product["guide_id"] = args.guide_id
    if args.numeric_poll_id:
        product["numeric_poll_id"] = args.numeric_poll_id
    if args.text_poll_id:
        product["text_poll_id"] = args.text_poll_id
    if args.data_dir:
        product["data_dir"] = args.data_dir

    if not all([product.get("guide_id"), product.get("numeric_poll_id"), product.get("text_poll_id")]):
        print(f"Error: Product '{args.product}' not in built-in config and missing required --guide-id, --numeric-poll-id, --text-poll-id.")
        sys.exit(1)
    start_ms, _ = get_month_boundaries(args.month)
    month_days = get_month_days(args.month)

    print(f"Fetching {args.product.upper()} NPS data for {args.month}...")
    print(f"  Guide: {product['guide_id']}")
    print(f"  Time range: {args.month} ({month_days} days)")

    # Fetch numeric scores
    print("\n  Fetching numeric scores...")
    try:
        scores = fetch_poll_responses(
            api_key, product['guide_id'],
            product['numeric_poll_id'], start_ms, month_days
        )
    except Exception as e:
        print(f"Error fetching scores: {e}")
        if "403" in str(e) or "401" in str(e):
            print("Check that your API key is valid and has read access.")
        sys.exit(1)
    print(f"  Got {len(scores)} score responses")

    # Fetch text responses
    print("  Fetching text responses...")
    try:
        texts = fetch_poll_responses(
            api_key, product['guide_id'],
            product['text_poll_id'], start_ms, month_days
        )
    except Exception as e:
        print(f"Error fetching text responses: {e}")
        sys.exit(1)
    print(f"  Got {len(texts)} text responses")

    # Build text lookup by visitorId
    text_by_visitor = {}
    for row in texts:
        vid = row.get('visitorId', '')
        text_by_visitor[vid] = row.get('pollResponse', '')

    # Build combined rows from score responses
    combined = []
    for row in scores:
        vid = row.get('visitorId', '')
        score = row.get('pollResponse', '')
        time_ms = row.get('browserTime', 0)

        try:
            score_int = int(score)
        except (ValueError, TypeError):
            continue

        combined.append({
            'Visitor ID': vid,
            'Date': format_date(time_ms),
            'Rating': str(score_int),
            'Response Group': response_group(score_int),
            'Response': text_by_visitor.get(vid, ''),
            'NPS Themes': '',
            'Channel': 'In-app'
        })

    # Product-specific filtering example: if a survey is served in a broader platform
    # (e.g., a parent LMS), you may need to filter responses to those mentioning your
    # specific product. Adjust or remove this filter for your use case.
    if args.product == 'cq':
        total_fetched = len(combined)
        combined = [r for r in combined if 'quiz' in r['Response'].lower()]
        print(f"  CQ quiz filter: {len(combined)} of {total_fetched} responses contain 'quiz'")

    # Sort by date
    combined.sort(key=lambda r: r['Date'])

    # Determine output path
    if args.output:
        output_path = args.output
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(base_dir, 'Data', product['data_dir'])
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f'nps-{args.month}.csv')

    # Write CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(combined)

    print(f"\nWrote {len(combined)} responses to: {output_path}")

    # Print summary
    if not combined:
        print("\nNo responses found for this month.")
        return

    scores_list = [int(r['Rating']) for r in combined]
    total = len(scores_list)
    promoters = sum(1 for s in scores_list if s >= 9)
    passives = sum(1 for s in scores_list if 7 <= s <= 8)
    detractors = sum(1 for s in scores_list if s <= 6)
    nps = round((promoters / total - detractors / total) * 100)
    comments = sum(1 for r in combined if r['Response'].strip())

    print(f"\nSummary:")
    print(f"  Responses: {total}")
    print(f"  NPS Score: {nps}")
    print(f"  Promoters: {promoters} ({round(promoters/total*100, 1)}%)")
    print(f"  Passives: {passives} ({round(passives/total*100, 1)}%)")
    print(f"  Detractors: {detractors} ({round(detractors/total*100, 1)}%)")
    print(f"  Comments: {comments}")
    print(f"  Date range: {combined[0]['Date']} to {combined[-1]['Date']}")

    # Score distribution
    print(f"\n  Score distribution:")
    for s in range(0, 11):
        count = sum(1 for r in scores_list if r == s)
        if count > 0:
            bar = '#' * min(count, 50)
            print(f"    {s:2d}: {bar} ({count})")


if __name__ == '__main__':
    main()
