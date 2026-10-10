from __future__ import annotations

import argparse
import json
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from .config import get_settings
from .promotion import promote_ready_candidates
from .repository import Repository


def main() -> None:
    parser = argparse.ArgumentParser(prog="bike-api")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("migrate")
    promote = subparsers.add_parser("promote")
    promote.add_argument("--prefecture-codes", nargs="+", default=["40", "41", "42", "43", "44", "45", "46"])
    audit = subparsers.add_parser("audit-kyushu")
    audit.add_argument("--minimum-spots-per-prefecture", type=int, default=1)
    privacy = subparsers.add_parser("privacy-maintenance")
    privacy.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    settings = get_settings()

    if args.command == "migrate":
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(config, "head")
    elif args.command == "promote":
        result = promote_ready_candidates(
            create_engine(settings.database_url), args.prefecture_codes, settings.data_version
        )
        print(json.dumps(result.__dict__, ensure_ascii=False))
    elif args.command == "privacy-maintenance":
        repository = Repository(settings.database_url)
        result = (
            repository.privacy_maintenance_preview()
            if args.dry_run
            else repository.execute_deletions_and_retention()
        )
        print(json.dumps(result))
    elif args.command == "audit-kyushu":
        prefectures = {
            "40": "福岡県", "41": "佐賀県", "42": "長崎県", "43": "熊本県",
            "44": "大分県", "45": "宮崎県", "46": "鹿児島県",
        }
        engine = create_engine(settings.database_url)
        from sqlalchemy import text

        with engine.connect() as connection:
            counts = dict(
                connection.execute(
                    text(
                        """
                        SELECT r.prefecture_code, count(*)
                        FROM spots s JOIN administrative_regions r ON r.id=s.region_id
                        WHERE s.publication_status='published'
                          AND s.verified_at >= now() - interval '180 days'
                        GROUP BY r.prefecture_code
                        """
                    )
                ).all()
            )
        result = [
            {
                "prefecture_code": code,
                "prefecture_name": name,
                "published_fresh_spots": counts.get(code, 0),
                "release_ready": counts.get(code, 0) >= args.minimum_spots_per_prefecture,
            }
            for code, name in prefectures.items()
        ]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not all(item["release_ready"] for item in result):
            sys.exit(1)


if __name__ == "__main__":
    main()
