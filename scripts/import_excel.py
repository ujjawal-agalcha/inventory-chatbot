import sys
import os
import argparse
import logging
from pathlib import Path

# Add workspace to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.excel_service import auto_detect_and_import

logger = logging.getLogger("scripts.import_excel")


def main():
    parser = argparse.ArgumentParser(description="Import an Excel workbook into MongoDB Inventory.")
    parser.add_argument("file_path", type=str, help="Path to the .xlsx or .xls file")
    parser.add_argument("--uploaded-by", type=str, default="cli_admin", help="Username importing the file")
    args = parser.parse_args()

    file_path = Path(args.file_path)
    if not file_path.exists():
        print(f"Error: File '{file_path}' does not exist.")
        sys.exit(1)

    print(f"Reading '{file_path.name}'...")
    file_bytes = file_path.read_bytes()

    print("Ingesting and processing workbook...")
    result = auto_detect_and_import(file_bytes, file_path.name, uploaded_by=args.uploaded_by)

    print("\n--- Ingestion Result ---")
    print(f"File Type: {result.get('file_type')}")
    print(f"Batch ID: {result.get('import_batch_id')}")
    print(f"Total Rows: {result.get('total_rows')}")
    print(f"Valid Records: {result.get('valid_records')}")
    print(f"New Master Products: {result.get('new_records')}")
    print(f"Updated Products: {result.get('updated_records')}")
    print(f"Duplicate Rows Prevented: {result.get('duplicate_records')}")
    if result.get("errors"):
        print(f"Errors: {result.get('errors')}")
    print("\nImport completed successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
