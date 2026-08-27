# OpenLoop

**Catch commitments that die in chat and notes.**

People say *“I’ll send the deck Friday”* or *“Can you ping legal?”* — then the thread moves on and the loop never closes. No ticket. No owner. No follow-up.

OpenLoop turns messy text into **open loops**: who owes what, optionally by when, and a **still-open digest** you can paste into standup.

**Current version: 0.2.0**

---

## The pain

| What happens | What gets lost |
|--------------|----------------|
| Slack / meeting / email promises | Ownership |
| “Next week” / “EOD” | Concrete dates |
| Thread scrolls away | Any memory that it was still open |
| Same promise said twice | Duplicate tasks |

Todo apps only help if someone bothers to create the task. OpenLoop meets people where the commitment was *spoken*.

---

## What v0.2 does

1. **Ingest** chat / notes / email (or CSV)
2. **Extract** commitments (offline rules always; LLM when `OPENAI_API_KEY` is set)
3. **Normalize** owners (`@alex.k` → Alex) and deadlines (`tomorrow`, `EOD`, `asap`)
4. **Dedupe** similar loops via fingerprint
5. Local **SQLite** with safe column migrations
6. **Digest** — overdue, due soon, unassigned, stale, nudge-first, load by owner  
   Formats: terminal · Markdown · Slack · HTML · JSON
7. **Today board** for one owner
8. Close / steer loops: `done` · `assign` · `snooze` · `block` · `priority` · `note` · `due`

---

## Quick start

```bash
git clone https://github.com/VSBhargav5/OpenLoop.git
cd OpenLoop
pip install -e ".[dev]"
pytest -q

python -m openloop ingest examples/messy_chat.txt \
  -t "Team chat 25 Aug" --date 2026-08-25 --me Bhargav --rules

python -m openloop digest -f md -o still-open.md
python -m openloop today --owner Bhargav
python -m openloop done <id-prefix>
```

Copy `config.example.json` to `~/.openloop/config.json` to set `me` and owner aliases.

---

## CLI

```bash
python -m openloop ingest <file> -t TITLE [--date YYYY-MM-DD] [--me NAME] [--rules] [--replace]
python -m openloop list [--status open] [--owner X] [--overdue] [--due-soon N] [--unassigned] [--stale] [-p p0]
python -m openloop digest [-n 7] [-f rich|md|slack|html|json] [-o path]
python -m openloop today [--owner NAME]
python -m openloop mine [--owner NAME]
python -m openloop search QUERY
python -m openloop stats
python -m openloop done|cancel|reopen|block|unblock <id>
python -m openloop assign|priority|tag|note|due|snooze <id> …
python -m openloop export out.json|out.csv
python -m openloop import-csv loops.csv -t backlog
```

---

## Status

**v0.2.0** — dedupe, aliases, priority/tags/notes, blocked/stale, today board, HTML digest, CSV import/export, activity history

---

## Tech

Python 3.11+ · Pydantic · SQLite · Typer · Rich · python-dateutil · OpenAI-compatible APIs

## License

MIT
