from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import uuid4

from .aging import age_days, aging_score, is_stale
from .fingerprint import fingerprint
from .models import ExtractResult, LoopPriority, LoopStatus
from .utc import now_iso

DEFAULT_DB = Path.home() / ".openloop" / "loops.db"

_LOOP_COLUMNS = (
    "id, source_id, text, owner, due_date, due_text, status, priority, tags, "
    "notes, blocked_reason, fingerprint, evidence, confidence, created_at, updated_at"
)


class LoopStore:
    def __init__(self, db_path: Path | str = DEFAULT_DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    path TEXT,
                    ingested_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS loops (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    owner TEXT,
                    due_date TEXT,
                    due_text TEXT,
                    status TEXT NOT NULL,
                    evidence TEXT,
                    confidence REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (source_id) REFERENCES sources(id)
                );
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    loop_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    note TEXT,
                    at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_loops_status ON loops(status);
                CREATE INDEX IF NOT EXISTS idx_loops_owner ON loops(owner);
                CREATE INDEX IF NOT EXISTS idx_loops_due ON loops(due_date);
                CREATE INDEX IF NOT EXISTS idx_activity_loop ON activity_log(loop_id);
                """
            )
            self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        existing = {r[1] for r in conn.execute("PRAGMA table_info(loops)").fetchall()}
        extras = {
            "priority": "TEXT NOT NULL DEFAULT 'p2'",
            "tags": "TEXT NOT NULL DEFAULT ''",
            "notes": "TEXT",
            "blocked_reason": "TEXT",
            "fingerprint": "TEXT",
        }
        for col, spec in extras.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE loops ADD COLUMN {col} {spec}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_loops_fp ON loops(fingerprint)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_loops_priority ON loops(priority)")

    def log_activity(self, loop_id: str, kind: str, *, old_value=None, new_value=None, note=None) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO activity_log (loop_id, kind, old_value, new_value, note, at) VALUES (?, ?, ?, ?, ?, ?)",
                (loop_id, kind, old_value, new_value, note, now_iso()),
            )

    def history(self, loop_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM activity_log WHERE loop_id = ? ORDER BY id ASC", (loop_id,)).fetchall()
        return [dict(r) for r in rows]

    def existing_fingerprints(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT fingerprint FROM loops WHERE fingerprint IS NOT NULL AND status NOT IN ('cancelled', 'archived')"
            ).fetchall()
        return {r[0] for r in rows if r[0]}

    def save_ingest(self, title: str, result: ExtractResult, *, path=None, source_id=None, replace_title=False, dedupe=True):
        sid = source_id or str(uuid4())
        now = now_iso()
        known = self.existing_fingerprints() if dedupe else set()
        inserted = skipped = 0
        with self._connect() as conn:
            if replace_title:
                row = conn.execute("SELECT id FROM sources WHERE title = ? ORDER BY ingested_at DESC LIMIT 1", (title,)).fetchone()
                if row:
                    sid = row["id"]
                    conn.execute("DELETE FROM loops WHERE source_id = ?", (sid,))
                    conn.execute("UPDATE sources SET path = COALESCE(?, path), ingested_at = ? WHERE id = ?", (path, now, sid))
                    known = set()
                else:
                    conn.execute("INSERT INTO sources (id, title, path, ingested_at) VALUES (?, ?, ?, ?)", (sid, title, path, now))
            else:
                conn.execute("INSERT INTO sources (id, title, path, ingested_at) VALUES (?, ?, ?, ?)", (sid, title, path, now))
            for loop in result.loops:
                fp = loop.fingerprint or fingerprint(loop.text, loop.owner)
                if dedupe and fp in known:
                    skipped += 1
                    continue
                known.add(fp)
                pri = loop.priority.value if hasattr(loop.priority, "value") else (loop.priority or "p2")
                conn.execute(
                    f"INSERT INTO loops ({_LOOP_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        loop.id, sid, loop.text, loop.owner,
                        loop.due_date.isoformat() if loop.due_date else None, loop.due_text,
                        loop.status.value, pri, loop.tags or "", loop.notes, loop.blocked_reason, fp,
                        loop.evidence, loop.confidence, loop.created_at.isoformat(), loop.updated_at.isoformat(),
                    ),
                )
                inserted += 1
        result.skipped_dupes = skipped
        return sid, inserted

    def list_loops(self, *, status=None, owner=None, overdue=False, due_within_days=None, unassigned=False, priority=None, tag=None, stale_days=None, as_of=None, include_closed=False):
        today = as_of or date.today()
        q = "SELECT l.*, s.title AS source_title FROM loops l JOIN sources s ON l.source_id = s.id"
        clauses, params = [], []
        if status:
            clauses.append("l.status = ?"); params.append(status)
        if owner:
            clauses.append("LOWER(l.owner) = LOWER(?)"); params.append(owner)
        if unassigned:
            clauses += ["(l.owner IS NULL OR TRIM(l.owner) = '')", "l.status IN ('open', 'snoozed', 'blocked')"]
        if overdue:
            clauses += ["l.due_date IS NOT NULL", "l.due_date < ?", "l.status IN ('open', 'snoozed', 'blocked')"]
            params.append(today.isoformat())
        if due_within_days is not None:
            end = today + timedelta(days=due_within_days)
            clauses += ["l.due_date IS NOT NULL", "l.due_date >= ?", "l.due_date <= ?", "l.status IN ('open', 'snoozed', 'blocked')"]
            params.extend([today.isoformat(), end.isoformat()])
        if priority:
            clauses.append("l.priority = ?"); params.append(priority.lower())
        if tag:
            clauses.append("INSTR(',' || REPLACE(LOWER(l.tags), ' ', '') || ',', ?)")
            params.append(f",{tag.lower().strip()},")
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY IFNULL(l.due_date, '9999') ASC, l.priority ASC, l.created_at DESC"
        with self._connect() as conn:
            rows = [dict(r) for r in conn.execute(q, params).fetchall()]
        if stale_days is not None:
            rows = [r for r in rows if is_stale(r, days=stale_days, as_of=today)]
        return rows

    def get(self, item_id: str):
        with self._connect() as conn:
            row = conn.execute("SELECT l.*, s.title AS source_title FROM loops l JOIN sources s ON l.source_id = s.id WHERE l.id = ?", (item_id,)).fetchone()
            if row:
                return dict(row)
            for r in conn.execute("SELECT l.*, s.title AS source_title FROM loops l JOIN sources s ON l.source_id = s.id").fetchall():
                if r["id"].startswith(item_id):
                    return dict(r)
        return None

    def update(self, item_id: str, *, status=None, owner=None, due_date=None, clear_due=False, priority=None, tags=None, notes=None, blocked_reason=None, log=True) -> bool:
        current = self.get(item_id)
        if not current:
            return False
        if status:
            try:
                LoopStatus(status)
            except ValueError:
                return False
        if priority:
            try:
                LoopPriority(priority.lower())
            except ValueError:
                return False
        sets, params = [], []
        if status:
            sets.append("status = ?"); params.append(status)
        if owner is not None:
            sets.append("owner = ?"); params.append(owner if owner else None)
        if clear_due:
            sets += ["due_date = NULL", "due_text = NULL"]
        elif due_date is not None:
            iso = due_date.isoformat() if isinstance(due_date, date) else str(due_date)[:10]
            sets.append("due_date = ?"); params.append(iso)
        if priority:
            sets.append("priority = ?"); params.append(priority.lower())
        if tags is not None:
            sets.append("tags = ?"); params.append(tags)
        if notes is not None:
            sets.append("notes = ?"); params.append(notes)
        if blocked_reason is not None:
            sets.append("blocked_reason = ?"); params.append(blocked_reason)
        if not sets:
            return False
        sets.append("updated_at = ?"); params.append(now_iso()); params.append(current["id"])
        with self._connect() as conn:
            ok = conn.execute(f"UPDATE loops SET {', '.join(sets)} WHERE id = ?", params).rowcount > 0
        if ok and log:
            if status and status != current.get("status"):
                self.log_activity(current["id"], "status", old_value=current.get("status"), new_value=status)
            if owner is not None and owner != current.get("owner"):
                self.log_activity(current["id"], "owner", old_value=current.get("owner"), new_value=owner)
            if due_date is not None or clear_due:
                self.log_activity(current["id"], "due", old_value=current.get("due_date"), new_value=None if clear_due else str(due_date))
            if notes is not None:
                self.log_activity(current["id"], "note", note=notes)
        return ok

    def search(self, query: str) -> list[dict]:
        q = f"%{query.lower()}%"
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT l.*, s.title AS source_title FROM loops l JOIN sources s ON l.source_id = s.id "
                "WHERE LOWER(l.text) LIKE ? OR LOWER(IFNULL(l.owner,'')) LIKE ? OR LOWER(IFNULL(l.notes,'')) LIKE ? "
                "OR LOWER(IFNULL(l.tags,'')) LIKE ? OR LOWER(IFNULL(l.evidence,'')) LIKE ? ORDER BY l.updated_at DESC",
                (q, q, q, q, q),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_sources(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT s.*, COUNT(l.id) AS loop_count FROM sources s LEFT JOIN loops l ON l.source_id = s.id GROUP BY s.id ORDER BY s.ingested_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def archive_done(self) -> int:
        with self._connect() as conn:
            return conn.execute(
                "UPDATE loops SET status = 'archived', updated_at = ? WHERE status IN ('done', 'cancelled')", (now_iso(),)
            ).rowcount

    def stats(self, *, as_of=None, stale_days=14) -> dict:
        today = as_of or date.today()
        with self._connect() as conn:
            rows = [dict(r) for r in conn.execute("SELECT * FROM loops").fetchall()]
        by_status, by_owner = {}, {}
        for r in rows:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
            if r["status"] in {"open", "snoozed", "blocked"}:
                key = (r.get("owner") or "(unassigned)").strip() or "(unassigned)"
                by_owner[key] = by_owner.get(key, 0) + 1
        return {
            "total": len(rows), "by_status": by_status,
            "by_owner": dict(sorted(by_owner.items(), key=lambda kv: (-kv[1], kv[0]))),
            "overdue": len(self.list_loops(overdue=True, as_of=today)),
            "stale": len([r for r in rows if is_stale(r, days=stale_days, as_of=today)]),
            "as_of": today.isoformat(),
        }

    def today_board(self, owner: str, *, as_of=None, days=2) -> dict:
        today = as_of or date.today()
        mine = [r for r in self.list_loops(owner=owner) if r["status"] in {"open", "snoozed", "blocked"}]
        overdue = [r for r in mine if r.get("due_date") and r["due_date"] < today.isoformat()]
        due_soon = [r for r in mine if r.get("due_date") and today.isoformat() <= r["due_date"] <= (today + timedelta(days=days)).isoformat()]
        blocked = [r for r in mine if r["status"] == "blocked"]
        rest = [r for r in mine if r not in overdue and r not in due_soon and r not in blocked]
        return {"owner": owner, "as_of": today.isoformat(), "overdue": overdue, "due_soon": due_soon, "blocked": blocked, "open": rest}

    def digest(self, *, days=7, as_of=None, stale_days=14) -> dict:
        today = as_of or date.today()
        open_loops = self.list_loops(status="open")
        snoozed = self.list_loops(status="snoozed")
        blocked = self.list_loops(status="blocked")
        overdue = self.list_loops(overdue=True, as_of=today)
        due_soon = self.list_loops(due_within_days=days, as_of=today)
        unassigned = self.list_loops(unassigned=True)
        no_due = [L for L in open_loops if not L.get("due_date")]
        stale = [r for r in self.list_loops(stale_days=stale_days, include_closed=True, as_of=today) if r["status"] in {"open", "snoozed", "blocked"}]
        by_owner = {}
        for L in open_loops + snoozed + blocked:
            key = (L.get("owner") or "(unassigned)").strip() or "(unassigned)"
            by_owner[key] = by_owner.get(key, 0) + 1
        nudges = sorted(open_loops + snoozed + blocked, key=lambda r: aging_score(r, as_of=today), reverse=True)[:8]
        for n in nudges:
            n["aging_score"] = aging_score(n, as_of=today)
            n["age_days"] = age_days(n, as_of=today)
        return {
            "as_of": today.isoformat(), "days": days, "open": len(open_loops),
            "snoozed": len(snoozed), "blocked": len(blocked), "overdue": overdue,
            "due_soon": due_soon, "unassigned": unassigned, "no_due": no_due,
            "stale": stale, "nudges": nudges,
            "by_owner": dict(sorted(by_owner.items(), key=lambda kv: (-kv[1], kv[0]))),
        }
