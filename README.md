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

### Option A — Fly.io (recommended for free/cheap)

Fly's hobby plan runs one always-on `shared-cpu-1x` machine. We use a string
session so no persistent volume is needed.

1. **Install flyctl** (one time):

   ```bash
   curl -L https://fly.io/install.sh | sh
   fly auth signup        # or: fly auth login
   ```

2. **Generate a session string locally** (replaces `python login.py` for Fly):

   ```bash
   python gen_session.py
   # paste the long string from the output into the fly secret below
   ```

3. **Create the app and set secrets**. From the repo root:

   ```bash
   fly launch --no-deploy --copy-config --name auto-userbot-<your-suffix>
   # Edit fly.toml `app = "..."` if flyctl didn't already do it for you.

   fly secrets set \
     API_ID=1234567 \
     API_HASH=your_api_hash_here \
     SESSION_STRING='1Ab...the_string_from_step_2...XyZ' \
     SOURCE_CHATS=@source_channel_1 \
     DEST_CHAT=@my_channel \
     MODE=copy
   ```

4. **Deploy**:

   ```bash
   fly deploy
   fly logs       # watch it boot — you should see "Userbot running"
   fly status     # confirm 1 machine started, state=started
   ```

5. **Update later** — push code to GitHub, then re-run `fly deploy`. To rotate
   the session, regenerate with `gen_session.py` and `fly secrets set
   SESSION_STRING=...`.

### Option B — Railway

1. Generate `SESSION_STRING` locally (`python gen_session.py`).
2. Push the repo to GitHub (already done).
3. <https://railway.app> → New Project → Deploy from GitHub repo →
   `heinblah-design/auto`.
4. Set the same env vars (`API_ID`, `API_HASH`, `SESSION_STRING`,
   `SOURCE_CHATS`, `DEST_CHAT`, `MODE`) under the service's **Variables** tab.
5. Railway auto-detects the `Dockerfile` and runs it. It bills against your
   $5/month free credit (~250h of a 256MB worker — enough for one always-on
   userbot).

### Option C — Hetzner / DigitalOcean / any VPS with systemd

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

### Option D — `tmux` / `screen`

```bash
tmux new -s userbot
source .venv/bin/activate
python main.py
# Ctrl+B then D to detach
```

### Option E — Docker (anywhere)

```bash
docker build -t auto-userbot .
docker run -d --name userbot --restart=unless-stopped \
  --env-file .env \
  -v $(pwd)/userbot.session:/app/userbot.session \
  auto-userbot
```

If you'd rather not mount the session file, set `SESSION_STRING` in `.env`
(generated by `python gen_session.py`) and drop the `-v` flag.

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
