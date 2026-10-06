"""python -m mock_api.seed: load the Olist-based dataset into lumora_commerce."""

import argparse
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine

from mock_api.config import DatabaseSettings
from mock_api.seed.config import SeedConfig
from mock_api.seed.dataset import build_dataset
from mock_api.seed.errors import SeedError
from mock_api.seed.load import load_dataset, table_checksums
from mock_api.seed.olist import load_olist
from mock_api.seed.summary import summarize


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mock_api.seed", description=__doc__)
    parser.add_argument("--source", type=Path, help="directory with the Olist CSV files")
    parser.add_argument("--as-of", type=date.fromisoformat, help="newest order date, YYYY-MM-DD")
    parser.add_argument("--target-orders", type=int, help="number of orders to keep")
    args = parser.parse_args(argv)

    overrides = {
        "source_dir": args.source,
        "as_of": args.as_of,
        "target_orders": args.target_orders,
    }
    cfg = SeedConfig(**{k: v for k, v in overrides.items() if v is not None})
    url = DatabaseSettings().url()

    try:
        print(f"Reading Olist CSVs from {cfg.source_dir} ...", flush=True)
        dataset = build_dataset(load_olist(cfg.source_dir), cfg)
    except SeedError as e:
        print(f"seed failed: {e}", file=sys.stderr)
        return 1

    print(f"Loading into {url.render_as_string(hide_password=True)} ...", flush=True)
    engine = create_engine(url)
    try:
        load_dataset(engine, dataset)
        with engine.connect() as conn:
            checksums = table_checksums(conn)
    finally:
        engine.dispose()

    print()
    print(summarize(dataset, cfg, checksums))
    return 0


if __name__ == "__main__":
    sys.exit(main())
