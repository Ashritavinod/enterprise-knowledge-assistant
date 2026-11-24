"""Load (or reload) the sample customer reviews dataset into PostgreSQL.

The API loads it automatically on first start. Use this script to rebuild it:

    python scripts/seed_reviews.py --reset

`--reset` deletes all products, reviews and sales (including AI sentiment
labels) and loads the dataset again.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.db.database import init_db, session_scope  # noqa: E402
from backend.services import review_dataset  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reset", action="store_true", help="delete and reload the dataset")
    args = parser.parse_args()
    init_db()
    with session_scope() as db:
        loaded = review_dataset.seed(db, reset=args.reset)
    print("Dataset loaded." if loaded else "Dataset already present; use --reset to reload it.")


if __name__ == "__main__":
    main()
