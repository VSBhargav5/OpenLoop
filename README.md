# OpenLoop

**Catch commitments that die in chat and notes.**

People say *“I’ll send the deck Friday”* or *“Can you ping legal?”* — then the thread moves on and the loop never closes. No ticket. No owner. No follow-up.

OpenLoop turns messy text into **open loops**: who owes what, optionally by when, and a **still-open digest** you can paste into standup.

**Current version: 0.1.0**

---

## The pain

| What happens | What gets lost |
|--------------|----------------|
| Slack / meeting / email promises | Ownership |
| “Next week” / “EOD” | Concrete dates |
| Thread scrolls away | Any memory that it was still open |

Todo apps only help if someone bothers to create the task. OpenLoop meets people where the commitment was *spoken*.

---

## What v0.1 does

1. **Ingest** a text dump (chat export, notes, email)
2. **Extract** commitments (offline rules always; LLM when `OPENAI_API_KEY` is set)
3. **Normalize** relative deadlines (`tomorrow`, `by Friday`, `EOD`)
4. Store in local **SQLite**
5. **Digest** — overdue, due soon, unassigned, no-deadline, load by owner  
   Formats: terminal · Markdown · Slack
6. Close loops: `done` · `assign` · `snooze`

---

## Quick start

```bash
git clone https://github.com/VSBhargav5/OpenLoop.git
cd OpenLoop
pip install -e ".[dev]"
pytest -q

# Offline (no API key required)
python -m openloop ingest examples/messy_chat.txt \
  -t "Team chat 25 Aug" --date 2026-08-25 --me Bhargav --rules

python -m openloop list
python -m openloop digest -f md -o still-open.md
python -m openloop done <id-prefix>
```

Optional LLM path (better recall on messy prose):

```bash
export OPENAI_API_KEY=sk-...
python -m openloop ingest examples/messy_chat.txt -t "Team chat" --me Bhargav
```

---

## CLI

```bash
python -m openloop ingest <file> -t TITLE [--date YYYY-MM-DD] [--me NAME] [--rules] [--replace]
python -m openloop list [--status open] [--owner X] [--overdue] [--due-soon N] [--unassigned]
python -m openloop digest [-n 7] [-f rich|md|slack] [-o path]
python -m openloop done <id>
python -m openloop assign <id> <owner>
python -m openloop snooze <id> [days]
python -m openloop show <id>
```

---

## Status

**v0.1.0** — ingest, rule + LLM extract, SQLite, still-open digest, done/assign/snooze

Next ideas: dedupe similar loops, Slack export adapter, personal “today” board, confidence thresholds.

---

## Tech

Python 3.11+ · Pydantic · SQLite · Typer · Rich · python-dateutil · OpenAI-compatible APIs

## License

MIT
