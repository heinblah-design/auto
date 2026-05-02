# auto — Telegram channel auto-copy / auto-forward

A small **userbot** (regular Telegram account, no bot token) that watches one
or more source channels/groups and automatically reposts every new message to
your own channel.

- **Copy mode** — re-uploads the post so it looks native (no "Forwarded from"
  header).
- **Forward mode** — uses Telegram's native forward (keeps attribution).
- Supports text, photos, videos, documents, voice/video notes, stickers, polls,
  and media albums.
- Optional keyword include / exclude filters.
- Reconnects automatically and respects FloodWait.

> **Heads up:** copying content from channels you don't own may violate
> Telegram's ToS, the channel owner's rights, or local copyright law. Use this
> on channels you control or have explicit permission to mirror.

---

## 1. Get API credentials

1. Open <https://my.telegram.org> and log in with the phone number of the
   account you want the userbot to use.
2. Go to **API development tools** and create a new app (any name/short
   name).
3. Copy the **App api_id** and **App api_hash**.

## 2. Set up locally

```bash
git clone https://github.com/heinblah-design/auto.git
cd auto

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env — set API_ID, API_HASH, SOURCE_CHATS, DEST_CHAT, MODE
```

Required `.env` values:

| Variable        | Example                          | Notes                                                |
| --------------- | -------------------------------- | ---------------------------------------------------- |
| `API_ID`        | `1234567`                        | From my.telegram.org                                 |
| `API_HASH`      | `0123abcd…`                      | From my.telegram.org                                 |
| `SOURCE_CHATS`  | `@news_ch,@another,-1001234567890` | Comma-separated; numeric ids work for private chats |
| `DEST_CHAT`     | `@my_channel`                    | Your channel; the user account must be admin        |
| `MODE`          | `copy` or `forward`              |                                                      |

The user account (the one whose phone number you use) must:
- be **a member** of every source chat, and
- be **an admin with post permission** on the destination channel.

## 3. First-time login (interactive)

```bash
python login.py
```

Telegram will send a code to your account; enter it (and your 2FA password if
enabled). This creates `userbot.session` — keep it secret, it grants full
access to your account.

## 4. Run

```bash
python main.py
```

You should see:

```
[INFO] userbot: Logged in as @yourname (id=…)
[INFO] userbot: Watching source: …
[INFO] userbot: Posting to: …
[INFO] userbot: Userbot running in copy mode. Press Ctrl+C to stop.
```

Post something in a source channel — within a second or two it should appear
in your destination channel.

## 5. Run 24/7

### Option A — VPS with systemd (recommended)

```ini
# /etc/systemd/system/tg-userbot.service
[Unit]
Description=Telegram auto-copy userbot
After=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/auto
EnvironmentFile=/home/ubuntu/auto/.env
ExecStart=/home/ubuntu/auto/.venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tg-userbot
journalctl -u tg-userbot -f
```

### Option B — `tmux` / `screen`

```bash
tmux new -s userbot
source .venv/bin/activate
python main.py
# Ctrl+B then D to detach
```

### Option C — Docker

```bash
docker build -t auto-userbot .
docker run -d --name userbot --restart=unless-stopped \
  --env-file .env \
  -v $(pwd)/userbot.session:/app/userbot.session \
  auto-userbot
```

(Run `python login.py` once on the host first to produce `userbot.session`.)

## Configuration reference

See [`.env.example`](.env.example) for every variable. Highlights:

- `KEYWORDS` — only repost messages whose text contains any of these.
- `BLOCK_KEYWORDS` — drop messages containing any of these.
- `PREFIX` / `SUFFIX` — add text to copied messages (copy mode only).

## Troubleshooting

- **`Could not resolve source`** — make sure the user account is a member of
  the source chat. For private channels you need to be invited; use the
  numeric `-100…` id (you can copy it from the message link in the desktop
  app).
- **`ChatWriteForbiddenError`** — the user account isn't an admin of
  `DEST_CHAT`, or doesn't have post permission.
- **`FloodWaitError`** — Telegram rate-limited you. The bot sleeps and retries
  automatically; if it happens often, reduce the number of source chats or
  add filters.
- **Session locked / `database is locked`** — only one process at a time may
  use a `.session` file. Stop the other instance first.
