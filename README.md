# Clavabit — staged modular refactor

This is **stage 1** of the refactor. It deliberately moves only configuration
and SQLite initialization out of the legacy bot, leaving handlers and business
logic intact to minimize behavioral changes.

## Structure

- `main.py` — stable process entry point (`from bot import main`).
- `bot.py` — existing bot logic, preserved with minimal import changes.
- `config.py` — project paths and settings.
- `database/db.py` — SQLite connection, initial tables, and additive column migrations.
- `handlers/`, `services/` — reserved for the next migration stages.
- `assets/`, `miniapp/` — reserved; no Mini App behavior is added yet.

## Run

Install the same dependencies as the existing deployment, then run `python main.py`.
Set `BOT_TOKEN` (or `TOKEN`) in the environment, or use the existing local
`token.txt` mechanism. Do not commit tokens or database files.

## Database safety

The database filename remains `activity.db`. The path remains `DATA_DIR` when
set, otherwise the project root (`BASE`). No table is renamed or dropped.
Back up the existing `activity.db` before deploying this refactor.

## Important

This stage is a safe extraction, not the full modularization. The next stages
will move one subsystem at a time (economy, career, relationships, moderation,
mini-games), with regression checks after each move.
