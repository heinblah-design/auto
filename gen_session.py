"""Generate a Telethon `SESSION_STRING` for stateless deployments.

Run this **once on your local machine**:

    python gen_session.py

It logs you in interactively (phone code + 2FA password if enabled) and
prints a long opaque string. Copy that string into your hosting platform as
the `SESSION_STRING` secret/env var — `main.py` will pick it up automatically
and skip file-based session storage. Useful for Fly.io, Railway, Render, or
any platform where the filesystem is ephemeral.

Treat the printed string like a password: anyone with it can act as your
account. Never commit it.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from telethon.sessions import StringSession
from telethon.sync import TelegramClient


def main() -> None:
    load_dotenv()

    api_id_raw = os.environ.get("API_ID")
    api_hash = os.environ.get("API_HASH")
    if not api_id_raw or not api_hash:
        raise SystemExit(
            "API_ID and API_HASH must be set in .env (see .env.example)."
        )

    api_id = int(api_id_raw)

    with TelegramClient(StringSession(), api_id, api_hash) as client:
        me = client.get_me()
        session_string: str = client.session.save()  # type: ignore[assignment]
        print()
        print("=" * 72)
        print(f"Logged in as: {me.first_name} (@{me.username}) id={me.id}")
        print()
        print("Copy the string below into your host as SESSION_STRING:")
        print()
        print(session_string)
        print()
        print("Treat it like a password. Never commit it.")
        print("=" * 72)


if __name__ == "__main__":
    main()
