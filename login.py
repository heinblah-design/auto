"""One-time interactive login.

Run this on your local machine the first time:
    python login.py

It will prompt for your phone number, the SMS/Telegram code, and (if enabled)
your 2FA password, then write a `.session` file. Copy that file alongside
`main.py` on your server — `main.py` will reuse it without re-prompting.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from telethon.sync import TelegramClient


def main() -> None:
    load_dotenv()

    api_id_raw = os.environ.get("API_ID")
    api_hash = os.environ.get("API_HASH")
    session_name = os.environ.get("SESSION_NAME", "userbot")

    if not api_id_raw or not api_hash:
        raise SystemExit(
            "API_ID and API_HASH must be set in .env (see .env.example)."
        )

    api_id = int(api_id_raw)

    with TelegramClient(session_name, api_id, api_hash) as client:
        me = client.get_me()
        print(f"Logged in as: {me.first_name} (@{me.username}) id={me.id}")
        print(f"Session saved to: {session_name}.session")


if __name__ == "__main__":
    main()
