import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.sync_service import clean_legacy_sample_data

logger = logging.getLogger("scripts.clear_database")


def main():
    print("Cleaning sample Excel imports while strictly preserving permanent electronic inventory...")
    result = clean_legacy_sample_data()
    print(f"Removed {result.get('sample_products_removed')} sample products.")
    print(f"Removed {result.get('orphan_procurements_removed')} procurement records.")
    print(f"Removed {result.get('orphan_expenses_removed')} expense records.")
    print(f"Permanent inventory items preserved: {result.get('permanent_products_count')}")
    print("Database cleanup completed successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
