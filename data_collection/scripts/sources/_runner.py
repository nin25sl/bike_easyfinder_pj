from __future__ import annotations

import sys

from collection_worker.cli import app


def run(source_key: str) -> None:
    app(prog_name=f"collect-{source_key}", args=["collect", "--sources", source_key, *sys.argv[1:]])
