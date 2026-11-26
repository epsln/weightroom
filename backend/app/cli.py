"""CLI helpers.

    uv run python -m app.cli import <history.json>   # load a saved history response
    uv run python -m app.cli sync                    # one-off sync using .env or in-app credentials
"""

from __future__ import annotations

import argparse
import asyncio
import json

from .auth import TokenManager
from .boostcamp import import_history, run_sync
from .config import Settings
from .crypto import load_cipher
from .db import connect, init_schema
from .profile import credentials, save_refresh_token


def main() -> None:
    parser = argparse.ArgumentParser(prog="weightroom")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_import = sub.add_parser("import", help="import a saved history JSON response")
    p_import.add_argument("path")
    sub.add_parser("sync", help="fetch history from Boostcamp now")
    args = parser.parse_args()

    settings = Settings.from_env()
    conn = connect(settings.database_path)
    init_schema(conn)

    if args.cmd == "import":
        with open(args.path, encoding="utf-8") as fh:
            seen = import_history(conn, json.load(fh))
        print(f"Imported {seen} sessions into {settings.database_path}")
    else:
        cipher = load_cipher(settings)
        refresh, api_key, _ = credentials(conn, settings, cipher)
        tokens = TokenManager(refresh, api_key, on_rotate=lambda t: save_refresh_token(conn, cipher, t))
        result = asyncio.run(run_sync(conn, tokens, settings.timezone_offset))
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
