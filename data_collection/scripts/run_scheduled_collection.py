from __future__ import annotations

import argparse
import json

from collection_worker.config import load_settings
from collection_worker.db import create_db_engine
from collection_worker.pipeline import collect_all
from sqlalchemy import text


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a collection profile under a PostgreSQL advisory lock")
    parser.add_argument("--profile", default="kyushu-p0")
    parser.add_argument("--region-group", default="kyushu")
    parser.add_argument("--mode", choices=["initial", "refresh"], default="refresh")
    parser.add_argument("--config")
    args = parser.parse_args()
    settings = load_settings(args.config)
    engine = create_db_engine(settings)
    lock_name = f"bike-easyfinder:{args.profile}:{args.region_group}"
    with engine.connect() as connection:
        acquired = connection.execute(
            text("SELECT pg_try_advisory_lock(hashtextextended(:name,0))"), {"name": lock_name}
        ).scalar_one()
        if not acquired:
            print(json.dumps({"status": "skipped", "reason": "already_running", "lock": lock_name}))
            return
        try:
            result = collect_all(engine, settings, args.profile, args.region_group, args.mode)
            print(json.dumps(result, ensure_ascii=False, default=str))
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(hashtextextended(:name,0))"), {"name": lock_name})


if __name__ == "__main__":
    main()
