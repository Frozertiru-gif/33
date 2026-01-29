# tg_user_clicker

Minimal Telegram MTProto user client using Telethon.

## Setup

1. Copy `.env.example` to `.env` and fill in your credentials:
   - `TG_API_ID`
   - `TG_API_HASH`
   - `TG_PHONE`
   - `TG_2FA_PASSWORD` (optional)
   - `SESSION_NAME` (defaults to `user`)
   - `BOT_USERNAME` (optional for `press`, required if not passing `--chat`)
   - `BUTTON_NEXT_TEXT`
   - `BUTTON_SERIES_TEXT`
   - `BUTTON_QUALITY_TEXT`
   - `BUTTON_BACK_TEXT`
   - `SEARCH_RESULTS_TIMEOUT_SECONDS`
   - `AFTER_PICK_TIMEOUT_SECONDS`
   - `SEARCH_SEND_PREFIX`
   - `STATE_PATH`
   - `TITLES_PATH`
   - `SENT_DEDUP_LIMIT`

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Authorize and create the session file:

```bash
python -m app.cli login
```

Check the current session user:

```bash
python -m app.cli me
```

Press the "Вперёд" button from recent messages:

```bash
python -m app.cli press --contains "Вперёд"
```

Search for a title and pick the first result:

```bash
python -m app.cli search --chat @BOT --title "Название"
```

Inline search for a title and pick the first result:

```bash
python -m app.cli search --chat @fvid_heb_bot --title "время приключений" --inline
```

Process a list of titles with resume support:

```bash
python -m app.cli run-list --chat @BOT --titles-file ./titles.txt
```

Example `titles.txt`:

```text
# Lines starting with # are ignored
Название 1
Название 2

Название 3
```

Run a single title with resume state:

```bash
python -m app.cli run-one --chat @BOT --title "Название"
```

Run a series inline search and forward episodes:

```bash
python -m app.cli series --chat @fvid_heb_bot --title "декстер" --inline
```

Check resume status:

```bash
python -m app.cli status
```

Reset resume state (requires confirmation):

```bash
python -m app.cli reset --yes
```

Resume behavior:

- Progress is stored in `state.json` (configurable via `STATE_PATH`).
- On restart, `run-list` continues from `current_index` and skips media IDs already in `sent_ids`.
- The last media message ID is tracked per title to continue series runs without duplicates.

The session file is stored automatically and reused on subsequent runs, so you won't be prompted for the code again.
