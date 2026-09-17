"""Replace the candidate profile from JSON files in data/candidate/."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import get_settings
from app.db import Database
from app.services.candidate import replace_from_seed
from app.services.candidate_seed import DEFAULT_DATA_DIR, load_seed_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Replace the stored candidate profile from seed JSON."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing profile.json and evidence.json",
    )
    args = parser.parse_args(argv)

    bundle = load_seed_bundle(args.data_dir)
    database = Database(get_settings())
    session = database.session_factory()
    try:
        profile = replace_from_seed(session, bundle)
        session.commit()
    except Exception as exc:
        session.rollback()
        print(f"seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()
        database.dispose()

    print(
        f"seeded profile key={profile.key} id={profile.id} "
        f"evidence={len(bundle.evidence)} from {args.data_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
