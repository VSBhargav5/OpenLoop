from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import uuid4

from .models import ExtractResult, LoopStatus

DEFAULT_DB = Path.home() / ".openloop" / "loops.db"


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
                CREATE INDEX IF NOT EXISTS idx_loops_status ON loops(status);
                CREATE INDEX IF NOT EXISTS idx_loops_owner ON loops(owner);
                CREATE INDEX IF NOT EXISTS idx_loops_due ON loops(due_date);
                """
            )

    def save_ingest(
        self,
        title: str,
        result: ExtractResult,
        *,
        path: Optional[str] = None,
        source_id: Optional[str] = None,
        replace_title: bool = False,
    ) -> str:
        sid = source_id or str(uuid4())
        now = datetime.utcnow().isoformat()

        with self._connect() as conn:
            if replace_title:
                row = conn.execute(
                    "SELECT id FROM sources WHERE title = ? ORDER BY ingested_at DESC LIMIT 1",
                    (title,),
                ).fetchone()
                if row:
                    sid = row["id"]
                    conn.execute("DELETE FROM loops WHERE source_id = ?", (sid,))
                    conn.execute(
                        "UPDATE sources SET path = COALESCE(?, path), ingested_at = ? WHERE id = ?",
                        (path, now, sid),
                    )
                else:
                    conn.execute(
                        "INSERT INTO sources (id, title, path, ingested_at) VALUES (?, ?, ?, ?)",
                        (sid, title, path, now),
                    )
            else:
                conn.execute(
                    "INSERT INTO sources (id, title, path, ingested_at) VALUES (?, ?, ?, ?)",
                    (sid, title, path, now),
                )

            for loop in result.loops:
                conn.execute(
                    """
                    INSERT INTO loops
                    (id, source_id, text, owner, due_date, due_text, status,
                     evidence, confidence, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        loop.id,
                        sid,
                        loop.text,
                        loop.owner,
                        loop.due_date.isoformat() if loop.due_date else None,
                        loop.due_text,
                        loop.status.value,
                        loop.evidence,
                        loop.confidence,
                        loop.created_at.isoformat(),
                        loop.updated_at.isoformat(),
                    ),
                )
        return sid

    def list_loops(
        self,
        *,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        overdue: bool = False,
        due_within_days: Optional[int] = None,
        unassigned: bool = False,
        as_of: Optional[date] = None,
    ) -> list[dict]:
        today = as_of or date.today()
        q = (
            "SELECT l.*, s.title AS source_title FROM loops l "
            "JOIN sources s ON l.source_id = s.id"
        )
        clauses: list[str] = []
        params: list = []
        if status:
            clauses.append("l.status = ?")
            params.append(status)
        if owner:
            clauses.append("LOWER(l.owner) = LOWER(?)")
            params.append(owner)
        if unassigned:
            clauses.append("(l.owner IS NULL OR TRIM(l.owner) = '')")
            clauses.append("l.status = 'open'")
        if overdue:
            clauses.append("l.due_date IS NOT NULL")
            clauses.append("l.due_date < ?")
            params.append(today.isoformat())
            clauses.append("l.status IN ('open', 'snoozed')")
        if due_within_days is not None:
            end = today + timedelta(days=due_within_days)
            clauses.append("l.due_date IS NOT NULL")
            clauses.append("l.due_date >= ?")
            clauses.append("l.due_date <= ?")
            params.extend([today.isoformat(), end.isoformat()])
            clauses.append("l.status IN ('open', 'snoozed')")
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY IFNULL(l.due_date, '9999') ASC, l.created_at DESC"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(q, params).fetchall()]

    def get(self, item_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT l.*, s.title AS source_title FROM loops l "
                "JOIN sources s ON l.source_id = s.id WHERE l.id = ?",
                (item_id,),
            ).fetchone()
            if row:
                return dict(row)
            for r in conn.execute(
                "SELECT l.*, s.title AS source_title FROM loops l "
                "JOIN sources s ON l.source_id = s.id"
            ).fetchall():
                if r["id"].startswith(item_id):
                    return dict(r)
        return None

    def update(
        self,
        item_id: str,
        *,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        due_date: Optional[date | str] = None,
        clear_due: bool = False,
    ) -> bool:
        if status:
            try:
                LoopStatus(status)
            except ValueError:
                return False
        sets: list[str] = []
        params: list = []
        if status:
            sets.append("status = ?")
            params.append(status)
        if owner is not None:
            sets.append("owner = ?")
            params.append(owner if owner else None)
        if clear_due:
            sets.append("due_date = NULL")
            sets.append("due_text = NULL")
        elif due_date is not None:
            iso = due_date.isoformat() if isinstance(due_date, date) else str(due_date)[:10]
            sets.append("due_date = ?")
            params.append(iso)
        if not sets:
            return False
        sets.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        params.append(item_id)
        with self._connect() as conn:
            cur = conn.execute(
                f"UPDATE loops SET {', '.join(sets)} WHERE id = ?",
                params,
            )
            return cur.rowcount > 0

    def digest(self, *,
               days: int = 7,
               as_of: Optional[date] = None) -> dict:
        today = as_of or date.today()
        open_loops = self.list_loops(status="open")
        snoozed = self.list_loops(status="snoozed")
        overdue = self.list_loops(overdue=True, as_of=today)
        due_soon = self.list_loops(due_within_days=days, as_of=today)
        unassigned = self.list_loops(unassigned=True)
        no_due = [L for L in open_loops if not L.get("due_date")]

        by_owner: dict[str, int] = {}
        for L in open_loops + snoozed:
            key = (L.get("owner") or "(unassigned)").strip() or "(unassigned)"
            by_owner[key] = by_owner.get(key, 0) + 1

        return {
            "as_of": today.isoformat(),
            "days": days,
            "open": len(open_loops),
            "snoozed": len(snoozed),
            "overdue": overdue,
            "due_soon": due_soon,
            "unassigned": unassigned,
            "no_due": no_due,
            "by_owner": dict(sorted(by_owner.items(), key=lambda kv: (-kv[1], kv[0]))),
        }
