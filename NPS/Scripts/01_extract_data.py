#!/usr/bin/env python3
# DEPRECATED: This script is retained as a fallback for CSV-based extraction.
# Primary workflow uses fetch-nps-responses.py (REST API) as of Feb 2026.
# To use this fallback: download CSV from Pendo manually, save to staging folder.
"""
Extract and validate NPS CSV from staging folder

Usage:
    python 01_extract_data.py --month 2025-11 --product mc
    python 01_extract_data.py --month 2025-11 --product cq

This script:
1. Detects CSV in Data/Staging/{product}/ folder
2. Validates date range (first/last of month)
3. Extracts to Data/{product}/nps-2025-[month].csv
4. Auto-deletes staging file
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from data_processing import (
    read_pendo_csv,
    validate_csv_completeness,
    extract_month_csv
)


def find_staging_csv(staging_dir: Path) -> Optional[Path]:
    """Find CSV file in staging directory"""
    csv_files = list(staging_dir.glob('*.csv'))

    if len(csv_files) == 0:
        return None
    elif len(csv_files) == 1:
        return csv_files[0]
    else:
        print(f"⚠️  Warning: Found {len(csv_files)} CSV files in staging folder:")
        for f in csv_files:
            print(f"   - {f.name}")
        print(f"\nUsing: {csv_files[0].name}")
        return csv_files[0]


def main():
    parser = argparse.ArgumentParser(description='Extract and validate NPS CSV')
    parser.add_argument('--month', required=True, help='Target month in YYYY-MM format (e.g., 2025-11)')
    parser.add_argument('--product', required=True, help='Product short code (e.g., mc, cq)')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')
    args = parser.parse_args()

    target_month = args.month
    product = args.product
    # Map product codes to folder names — add your products here
    PRODUCT_FOLDERS = {}  # e.g., {"p1": "Product One", "p2": "Product Two"}
    product_folder = PRODUCT_FOLDERS.get(product, product)

    # Validate month format
    try:
        year, month = map(int, target_month.split('-'))
        if not (1 <= month <= 12):
            raise ValueError("Month must be between 01 and 12")
    except (ValueError, AttributeError) as e:
        print(f"❌ Error: Invalid month format '{target_month}'. Use YYYY-MM (e.g., 2025-11)")
        sys.exit(1)

    # Setup paths
    base_dir = Path(__file__).parent.parent
    staging_dir = base_dir / 'Data' / 'Staging' / product_folder
    output_dir = base_dir / 'Data' / product_folder
    output_file = output_dir / f'nps-{target_month}.csv'

    # Check staging directory exists
    if not staging_dir.exists():
        print(f"❌ Error: Staging directory not found: {staging_dir}")
        sys.exit(1)

    # Find CSV in staging
    print(f"📂 Looking for CSV in: {staging_dir}")
    staging_csv = find_staging_csv(staging_dir)

    if staging_csv is None:
        print(f"❌ Error: No CSV files found in staging directory")
        sys.exit(1)

    print(f"✓ Found: {staging_csv.name}")

    # Read and validate CSV
    print(f"\n📊 Reading CSV...")
    try:
        rows, columns = read_pendo_csv(staging_csv)
        print(f"✓ Loaded {len(rows)} rows, {len(columns)} columns")
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        sys.exit(1)

    # Validate completeness
    print(f"\n🔍 Validating data for {target_month}...")
    is_complete, message = validate_csv_completeness(rows, target_month)

    if is_complete:
        print(f"✓ {message}")
    else:
        print(f"⚠️  Warning: {message}")
        print(f"\nContinuing with extraction, but data may be incomplete.")
        if not args.yes:
            response = input("Continue? (y/n): ")
            if response.lower() != 'y':
                print("Aborted.")
                sys.exit(0)

    # Extract to output file
    print(f"\n💾 Extracting to: {output_file}")

    try:
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Check if output file already exists
        if output_file.exists():
            print(f"⚠️  Warning: Output file already exists")
            if not args.yes:
                response = input("Overwrite? (y/n): ")
                if response.lower() != 'y':
                    print("Aborted.")
                    sys.exit(0)

        extract_month_csv(staging_csv, target_month, output_file)
        print(f"✓ Extracted {target_month} data")

        # Verify extracted file
        extracted_rows, _ = read_pendo_csv(output_file)
        print(f"✓ Verified: {len(extracted_rows)} rows in output file")

    except Exception as e:
        print(f"❌ Error during extraction: {e}")
        sys.exit(1)

    # Delete staging file
    print(f"\n🗑️  Deleting staging file...")
    try:
        staging_csv.unlink()
        print(f"✓ Deleted: {staging_csv.name}")
    except Exception as e:
        print(f"⚠️  Warning: Could not delete staging file: {e}")
        print(f"   Please manually delete: {staging_csv}")

    # Success summary
    print(f"\n" + "="*60)
    print(f"✅ SUCCESS")
    print(f"="*60)
    print(f"Month: {target_month}")
    print(f"Output: {output_file}")
    print(f"Rows: {len(extracted_rows)}")

    if not is_complete:
        print(f"\n⚠️  Note: Data validation showed potential incompleteness")
        print(f"   Review extraction carefully")

    print(f"\nNext step: Run 02_update_tracking.py --month {target_month} --product {product}")


if __name__ == '__main__':
    main()
