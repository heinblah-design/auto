"""Telegram auto-copy / auto-forward userbot.

Listens for new messages in `SOURCE_CHATS` and reposts them to `DEST_CHAT`,
either as a native forward (`MODE=forward`) or as a clean copy without the
"Forwarded from" header (`MODE=copy`). Handles single messages, albums
(grouped media), and edits.

Uses a regular Telegram **user** account via MTProto — no bot token required.
Run `python login.py` once to generate the session, then `python main.py`.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Awaitable, Callable, Iterable

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.custom.message import Message

# Cap so a server-side ban (e.g. 24h FloodWait) can't tie up the event loop.
MAX_FLOOD_WAIT_SECONDS = 600
MAX_FLOOD_RETRIES = 5

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("userbot")


def _parse_chats(raw: str) -> list[str | int]:
    chats: list[str | int] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        # Numeric ids (channels are typically -100…)
        if item.lstrip("-").isdigit():
            chats.append(int(item))
        else:
            chats.append(item.lstrip("@").removeprefix("https://t.me/").removeprefix("t.me/"))
    return chats


def _parse_keywords(raw: str) -> list[str]:
    return [k.strip().lower() for k in raw.split(",") if k.strip()]


def _matches(text: str | None, allow: list[str], block: list[str]) -> bool:
    haystack = (text or "").lower()
    if block and any(b in haystack for b in block):
        return False
    if allow and not any(a in haystack for a in allow):
        return False
    return True


async def _retry_on_flood(
    op: Callable[[], Awaitable[None]],
    label: str,
) -> bool:
    """Run `op()`, retrying after FloodWait. Returns True on success.

    Telethon delivers each event exactly once, so a handler that catches
    FloodWaitError and returns silently drops the message. We retry instead.
    """
    for attempt in range(1, MAX_FLOOD_RETRIES + 1):
        try:
            await op()
            return True
        except FloodWaitError as fw:
            if fw.seconds > MAX_FLOOD_WAIT_SECONDS:
                log.error(
                    "%s: FloodWait %ds exceeds cap %ds — dropping",
                    label, fw.seconds, MAX_FLOOD_WAIT_SECONDS,
                )
                return False
            log.warning(
                "%s: FloodWait %ds (attempt %d/%d) — sleeping",
                label, fw.seconds, attempt, MAX_FLOOD_RETRIES,
            )
            await asyncio.sleep(fw.seconds + 1)
    log.error("%s: gave up after %d FloodWait retries", label, MAX_FLOOD_RETRIES)
    return False


async def _send_copy(
    client: TelegramClient,
    dest: str | int,
    messages: Iterable[Message],
    prefix: str,
    suffix: str,
) -> None:
    """Re-send messages to `dest` without forward attribution.

    For media albums Telethon expects a list passed in one `send_file` call so
    the destination preserves the grouped layout.
    """
    msgs = list(messages)
    if not msgs:
        return

    first = msgs[0]
    caption = first.message or ""
    if prefix or suffix:
        caption = f"{prefix}{caption}{suffix}".strip()

    if any(m.media for m in msgs):
        files = [m for m in msgs]  # Telethon accepts Message objects as files
        await client.send_file(
            dest,
            file=files if len(files) > 1 else files[0],
            caption=caption if caption else None,
            formatting_entities=first.entities if not (prefix or suffix) else None,
            link_preview=False,
        )
    else:
        await client.send_message(
            dest,
            caption,
            formatting_entities=first.entities if not (prefix or suffix) else None,
            link_preview=False,
        )


async def run() -> None:
    load_dotenv()

    api_id_raw = os.environ.get("API_ID")
    api_hash = os.environ.get("API_HASH")
    session_name = os.environ.get("SESSION_NAME", "userbot")
    sources_raw = os.environ.get("SOURCE_CHATS", "")
    dest_raw = os.environ.get("DEST_CHAT", "")
    mode = os.environ.get("MODE", "copy").strip().lower()
    allow = _parse_keywords(os.environ.get("KEYWORDS", ""))
    block = _parse_keywords(os.environ.get("BLOCK_KEYWORDS", ""))
    prefix = os.environ.get("PREFIX", "")
    suffix = os.environ.get("SUFFIX", "")

    if not api_id_raw or not api_hash:
        raise SystemExit("API_ID and API_HASH must be set (see .env.example).")
    if not sources_raw or not dest_raw:
        raise SystemExit("SOURCE_CHATS and DEST_CHAT must be set.")
    if mode not in {"copy", "forward"}:
        raise SystemExit("MODE must be 'copy' or 'forward'.")

    api_id = int(api_id_raw)
    sources = _parse_chats(sources_raw)
    dest_parsed = _parse_chats(dest_raw)
    if not dest_parsed:
        raise SystemExit(
            "DEST_CHAT could not be parsed; check the value in .env."
        )
    dest: str | int = dest_parsed[0]

    client = TelegramClient(session_name, api_id, api_hash)
    await client.start()  # type: ignore[func-returns-value]

    me = await client.get_me()
    log.info("Logged in as %s (id=%s)", getattr(me, "username", None) or me.first_name, me.id)

    # Resolve entities once so handler dispatch is fast and ids are validated.
    resolved_sources = []
    for src in sources:
        try:
            entity = await client.get_entity(src)
            resolved_sources.append(entity)
            log.info("Watching source: %s (id=%s)", getattr(entity, "title", src), entity.id)
        except Exception as e:  # noqa: BLE001
            log.error("Could not resolve source %r: %s", src, e)
    if not resolved_sources:
        raise SystemExit("No source chats could be resolved. Check SOURCE_CHATS.")

    try:
        dest_entity = await client.get_entity(dest)
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"Could not resolve DEST_CHAT={dest!r}: {e}") from e
    log.info("Posting to: %s (id=%s)", getattr(dest_entity, "title", dest), dest_entity.id)

    @client.on(events.Album(chats=resolved_sources))
    async def on_album(event: events.Album.Event) -> None:
        text = event.messages[0].message or ""
        if not _matches(text, allow, block):
            return
        label = f"album from chat {event.chat_id}"

        async def _do() -> None:
            if mode == "forward":
                await client.forward_messages(dest_entity, list(event.messages))
            else:
                await _send_copy(client, dest_entity, event.messages, prefix, suffix)

        try:
            if await _retry_on_flood(_do, label):
                log.info("Reposted album of %d messages from %s", len(event.messages), event.chat_id)
        except Exception:  # noqa: BLE001
            log.exception("Failed to repost album")

    @client.on(events.NewMessage(chats=resolved_sources))
    async def on_message(event: events.NewMessage.Event) -> None:
        msg: Message = event.message
        # Albums also fire NewMessage for each item; the Album handler covers them.
        if msg.grouped_id is not None:
            return
        if not _matches(msg.message, allow, block):
            return
        label = f"message {msg.id} from chat {event.chat_id}"

        async def _do() -> None:
            if mode == "forward":
                await client.forward_messages(dest_entity, msg)
            else:
                await _send_copy(client, dest_entity, [msg], prefix, suffix)

        try:
            if await _retry_on_flood(_do, label):
                log.info("Reposted %s", label)
        except Exception:  # noqa: BLE001
            log.exception("Failed to repost message")

    log.info("Userbot running in %s mode. Press Ctrl+C to stop.", mode)
    await client.run_until_disconnected()  # type: ignore[func-returns-value]


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
