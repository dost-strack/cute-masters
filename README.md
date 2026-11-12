# Cute Masters — Telegram Giveaway Bot

A Python Telegram bot for creating simple giveaways, collecting participants and randomly selecting winners.

## Features in this starter version

- Guided giveaway creation: prize/description, 1–100 winners, duration (1–720 hours).
- Inline **Participate** button and duplicate-entry protection.
- Live participant count button.
- Automatic giveaway closing and random winner selection.
- Personal list of giveaways with `/my`.
- SQLite storage; Docker Compose deployment.

> This is the first working MVP, not yet a full feature-for-feature replacement for Best Random Bot. Channel subscription checks, CAPTCHA/anti-bot, sponsor channels, media albums, boosts, scheduled publishing and detailed analytics are planned next.

## Run locally

1. Create a Telegram bot with [@BotFather](https://t.me/BotFather).
2. Copy `.env.example` to `.env` and set `BOT_TOKEN`.
3. Install Python 3.11+ and dependencies:

   ```bash
   python -m venv .venv
   # Windows: .venv\\Scripts\\activate
   # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   python main.py
   ```

## Run with Docker

```bash
cp .env.example .env
# Edit .env and set BOT_TOKEN
docker compose up -d --build
docker compose logs -f
```

The SQLite database is persisted in `./data`.

## Commands

- `/start` — start the bot
- `/create` — create a giveaway
- `/my` — list your giveaways
- `/help` — instructions

## Security

Never commit your real bot token or the `.env` file. Rotate the token with @BotFather if it is exposed.
