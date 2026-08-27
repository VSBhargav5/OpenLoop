from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
from uuid import uuid4

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import load_config
from .dates import normalize_deadline
from .digest import format_digest_json, format_digest_markdown, format_digest_slack
from .exporter import export_csv, export_json
from .extractor import extract
from .html_digest import format_digest_html
from .importer import import_csv
from .owners import normalize_owner
from .store import LoopStore

app = typer.Typer(help="OpenLoop – catch commitments that die in chat and notes", no_args_is_help=True)
console = Console()


def _store(db: Optional[Path] = None) -> LoopStore:
    return LoopStore(db) if db else LoopStore()


def _cfg():
    return load_config()


def _print_loops(rows: list[dict], title: str) -> None:
    table = Table(title=title)
    table.add_column("ID", style="dim", max_width=8)
    table.add_column("P")
    table.add_column("Owner")
    table.add_column("Commitment")
    table.add_column("Due")
    table.add_column("Status")
    table.add_column("Source", style="cyan")
    for r in rows:
        due = r.get("due_date") or r.get("due_text") or "—"
        table.add_row(r["id"][:8], r.get("priority") or "p2", r.get("owner") or "—", r["text"], str(due), r["status"], r.get("source_title") or "")
    console.print(table)
    if not rows:
        console.print("[dim]None.[/dim]")


def _require(store: LoopStore, item_id: str) -> dict:
    item = store.get(item_id)
    if not item:
        console.print(f"[red]Not found: {item_id}[/red]")
        raise typer.Exit(1)
    return item


@app.command("ingest")
def ingest_cmd(
    file: Path = typer.Argument(...),
    title: str = typer.Option(..., "--title", "-t"),
    date_str: Optional[str] = typer.Option(None, "--date", "-d"),
    me: Optional[str] = typer.Option(None, "--me"),
    rules: bool = typer.Option(False, "--rules"),
    replace: bool = typer.Option(False, "--replace"),
    min_confidence: Optional[float] = typer.Option(None, "--min-confidence"),
    no_dedupe: bool = typer.Option(False, "--no-dedupe"),
    model: str = typer.Option("gpt-4o-mini", "--model"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    db: Optional[Path] = typer.Option(None, "--db"),
):
    cfg = _cfg()
    if not file.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)
    text = file.read_text(encoding="utf-8").strip()
    if not text:
        console.print("[red]File is empty[/red]")
        raise typer.Exit(1)
    ref = date.today()
    if date_str:
        try:
            ref = date.fromisoformat(date_str)
        except ValueError:
            console.print("[red]--date must be YYYY-MM-DD[/red]")
            raise typer.Exit(1)
    source_id = str(uuid4())
    store = _store(db)
    me = me or cfg.get("me")
    floor = min_confidence if min_confidence is not None else float(cfg.get("min_confidence") or 0)
    console.print(f"[bold]Ingesting[/bold] {file.name} ...")
    result = extract(
        text, source_id=source_id, reference_date=ref, model=model, base_url=base_url,
        default_owner=me, force_rules=rules, min_confidence=floor, aliases=cfg.get("aliases") or {},
    )
    sid, inserted = store.save_ingest(title, result, path=str(file), source_id=source_id, replace_title=replace, dedupe=not no_dedupe)
    skipped = result.skipped_dupes
    extra = f" · skipped {skipped} duplicate(s)" if skipped else ""
    console.print(f"[green]Saved[/green] {inserted} loop(s) under '{title}' ({sid[:8]}){extra}")
    if result.loops:
        _print_loops(
            [{**L.model_dump(), "due_date": L.due_date.isoformat() if L.due_date else None, "source_title": title, "status": L.status.value, "priority": L.priority.value if hasattr(L.priority, "value") else L.priority} for L in result.loops],
            "Extracted loops",
        )


@app.command("list")
def list_cmd(
    status: Optional[str] = typer.Option("open", "--status", "-s"),
    owner: Optional[str] = typer.Option(None, "--owner", "-o"),
    overdue: bool = typer.Option(False, "--overdue"),
    due_soon: Optional[int] = typer.Option(None, "--due-soon"),
    unassigned: bool = typer.Option(False, "--unassigned"),
    priority: Optional[str] = typer.Option(None, "--priority", "-p"),
    tag: Optional[str] = typer.Option(None, "--tag"),
    stale: bool = typer.Option(False, "--stale"),
    db: Optional[Path] = typer.Option(None, "--db"),
):
    cfg = _cfg()
    rows = _store(db).list_loops(
        status=None if overdue or due_soon is not None or unassigned or stale else status,
        owner=owner, overdue=overdue, due_within_days=due_soon, unassigned=unassigned,
        priority=priority, tag=tag,
        stale_days=int(cfg.get("stale_days") or 14) if stale else None,
        include_closed=stale,
    )
    title = "Overdue" if overdue else f"Due within {due_soon}d" if due_soon is not None else "Unassigned" if unassigned else "Stale" if stale else "Loops"
    _print_loops(rows, title)


@app.command("digest")
def digest_cmd(
    days: int = typer.Option(7, "--days", "-n"),
    format: str = typer.Option("rich", "--format", "-f"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    db: Optional[Path] = typer.Option(None, "--db"),
):
    cfg = _cfg()
    d = _store(db).digest(days=days, stale_days=int(cfg.get("stale_days") or 14))
    fmt = format.lower().strip()
    mapping = {"md": format_digest_markdown, "slack": format_digest_slack, "html": format_digest_html, "json": format_digest_json}
    if fmt == "rich":
        content = None
    elif fmt in mapping:
        content = mapping[fmt](d)
    else:
        console.print("[red]--format must be rich, md, slack, html, or json[/red]")
        raise typer.Exit(1)
    if content is not None:
        if output:
            output.write_text(content, encoding="utf-8")
            console.print(f"[green]Wrote[/green] {output}")
        else:
            console.print(content, highlight=False)
        return
    console.print(Panel.fit(
        f"[bold]OpenLoop digest[/bold]  ·  {d['as_of']}\nOpen {d['open']}  ·  Overdue {len(d['overdue'])}  ·  Due {days}d {len(d['due_soon'])}  ·  Unassigned {len(d['unassigned'])}  ·  Stale {len(d['stale'])}  ·  Blocked {d['blocked']}",
        border_style="cyan",
    ))
    if d["by_owner"]:
        console.print("[bold]Load[/bold]")
        for n, c in d["by_owner"].items():
            console.print(f"  {n}: {c}")
    _print_loops(d["overdue"], "Overdue")
    _print_loops(d["due_soon"], f"Due within {days}d")
    _print_loops(d["unassigned"], "Unassigned")
    _print_loops(d["stale"], "Stale")
    _print_loops(d["nudges"], "Nudge first")
    _print_loops(d["no_due"][:15], "Open · no deadline")


@app.command("done")
def done_cmd(item_id: str, db: Optional[Path] = typer.Option(None, "--db")):
    store = _store(db)
    item = _require(store, item_id)
    store.update(item["id"], status="done")
    console.print(f"[green]Done[/green] {item['id'][:8]} — {item['text']}")


@app.command("cancel")
def cancel_cmd(item_id: str, db: Optional[Path] = typer.Option(None, "--db")):
    store = _store(db)
    item = _require(store, item_id)
    store.update(item["id"], status="cancelled")
    console.print(f"[yellow]Cancelled[/yellow] {item['id'][:8]}")


@app.command("reopen")
def reopen_cmd(item_id: str, db: Optional[Path] = typer.Option(None, "--db")):
    store = _store(db)
    item = _require(store, item_id)
    store.update(item["id"], status="open")
    console.print(f"[green]Reopened[/green] {item['id'][:8]}")


@app.command("assign")
def assign_cmd(item_id: str, owner: str, db: Optional[Path] = typer.Option(None, "--db")):
    cfg = _cfg()
    store = _store(db)
    item = _require(store, item_id)
    new = None if owner.strip() in {"-", ""} else normalize_owner(owner, aliases=cfg.get("aliases") or {}, default_self=cfg.get("me"))
    store.update(item["id"], owner=new if new is not None else "")
    console.print(f"[green]Assigned[/green] {item['id'][:8]} → {new or 'unassigned'}")


@app.command("priority")
def priority_cmd(item_id: str, level: str, db: Optional[Path] = typer.Option(None, "--db")):
    store = _store(db)
    item = _require(store, item_id)
    if not store.update(item["id"], priority=level.lower()):
        console.print("[red]priority must be p0, p1, p2, or p3[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Priority[/green] {item['id'][:8]} → {level.lower()}")


@app.command("tag")
def tag_cmd(item_id: str, tags: str, db: Optional[Path] = typer.Option(None, "--db")):
    store = _store(db)
    item = _require(store, item_id)
    store.update(item["id"], tags=tags)
    console.print(f"[green]Tags[/green] {item['id'][:8]} → {tags}")


@app.command("note")
def note_cmd(item_id: str, text: str, db: Optional[Path] = typer.Option(None, "--db")):
    store = _store(db)
    item = _require(store, item_id)
    prev = item.get("notes") or ""
    store.update(item["id"], notes=(prev + "\n" + text).strip() if prev else text)
    console.print(f"[green]Noted[/green] {item['id'][:8]}")


@app.command("due")
def due_cmd(item_id: str, when: str, db: Optional[Path] = typer.Option(None, "--db")):
    store = _store(db)
    item = _require(store, item_id)
    if when.lower() in {"clear", "-", "none"}:
        store.update(item["id"], clear_due=True)
        console.print(f"[green]Cleared due[/green] {item['id'][:8]}")
        return
    parsed, _ = normalize_deadline(when)
    if not parsed:
        console.print("[red]Could not parse deadline[/red]")
        raise typer.Exit(1)
    store.update(item["id"], due_date=parsed)
    console.print(f"[green]Due[/green] {item['id'][:8]} → {parsed.isoformat()}")


@app.command("block")
def block_cmd(item_id: str, reason: str = "blocked", db: Optional[Path] = typer.Option(None, "--db")):
    store = _store(db)
    item = _require(store, item_id)
    store.update(item["id"], status="blocked", blocked_reason=reason)
    console.print(f"[yellow]Blocked[/yellow] {item['id'][:8]} — {reason}")


@app.command("unblock")
def unblock_cmd(item_id: str, db: Optional[Path] = typer.Option(None, "--db")):
    store = _store(db)
    item = _require(store, item_id)
    store.update(item["id"], status="open", blocked_reason="")
    console.print(f"[green]Unblocked[/green] {item['id'][:8]}")


@app.command("snooze")
def snooze_cmd(item_id: str, days: int = 3, db: Optional[Path] = typer.Option(None, "--db")):
    store = _store(db)
    item = _require(store, item_id)
    today = date.today()
    current = None
    if item.get("due_date"):
        try:
            current = date.fromisoformat(str(item["due_date"])[:10])
        except ValueError:
            current = None
    base = current if current and current > today else today
    new_due = base + timedelta(days=max(days, 0))
    store.update(item["id"], status="snoozed", due_date=new_due)
    console.print(f"[green]Snoozed[/green] {item['id'][:8]} → {new_due.isoformat()}")


@app.command("today")
def today_cmd(owner: Optional[str] = typer.Option(None, "--owner", "-o"), db: Optional[Path] = typer.Option(None, "--db")):
    cfg = _cfg()
    who = owner or cfg.get("me")
    if not who:
        console.print("[red]Pass --owner or set 'me' in ~/.openloop/config.json[/red]")
        raise typer.Exit(1)
    board = _store(db).today_board(who)
    console.print(Panel.fit(f"[bold]Today · {who}[/bold]  ·  {board['as_of']}", border_style="green"))
    _print_loops(board["overdue"], "Overdue")
    _print_loops(board["due_soon"], "Due soon")
    _print_loops(board["blocked"], "Blocked")
    _print_loops(board["open"], "Open")


@app.command("mine")
def mine_cmd(owner: Optional[str] = typer.Option(None, "--owner", "-o"), db: Optional[Path] = typer.Option(None, "--db")):
    cfg = _cfg()
    who = owner or cfg.get("me")
    if not who:
        console.print("[red]Pass --owner or set 'me' in ~/.openloop/config.json[/red]")
        raise typer.Exit(1)
    rows = [r for r in _store(db).list_loops(owner=who) if r["status"] in {"open", "snoozed", "blocked"}]
    _print_loops(rows, f"Mine · {who}")


@app.command("search")
def search_cmd(query: str, db: Optional[Path] = typer.Option(None, "--db")):
    _print_loops(_store(db).search(query), f"Search · {query}")


@app.command("stats")
def stats_cmd(db: Optional[Path] = typer.Option(None, "--db")):
    console.print(json.dumps(_store(db).stats(), indent=2))


@app.command("sources")
def sources_cmd(db: Optional[Path] = typer.Option(None, "--db")):
    table = Table(title="Sources")
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Loops")
    table.add_column("Ingested")
    for s in _store(db).list_sources():
        table.add_row(s["id"][:8], s["title"], str(s["loop_count"]), str(s["ingested_at"])[:19])
    console.print(table)


@app.command("history")
def history_cmd(item_id: str, db: Optional[Path] = typer.Option(None, "--db")):
    store = _store(db)
    item = _require(store, item_id)
    rows = store.history(item["id"])
    if not rows:
        console.print("[dim]No activity yet.[/dim]")
        return
    table = Table(title=f"History · {item['id'][:8]}")
    table.add_column("When")
    table.add_column("Kind")
    table.add_column("Old")
    table.add_column("New")
    table.add_column("Note")
    for r in rows:
        table.add_row(str(r["at"])[:19], r["kind"], r.get("old_value") or "", r.get("new_value") or "", r.get("note") or "")
    console.print(table)


@app.command("show")
def show_cmd(item_id: str, db: Optional[Path] = typer.Option(None, "--db")):
    item = _require(_store(db), item_id)
    body = (
        f"[bold]{item['text']}[/bold]\n\n"
        f"Owner    : {item.get('owner') or '(unassigned)'}\n"
        f"Due      : {item.get('due_date') or item.get('due_text') or '—'}\n"
        f"Status   : {item['status']}\n"
        f"Priority : {item.get('priority') or 'p2'}\n"
        f"Tags     : {item.get('tags') or '—'}\n"
        f"Source   : {item.get('source_title')}\n"
        f"ID       : {item['id']}\n"
    )
    if item.get("blocked_reason"):
        body += f"Blocked  : {item['blocked_reason']}\n"
    if item.get("notes"):
        body += f"\nNotes:\n{item['notes']}\n"
    if item.get("evidence"):
        body += f"\nEvidence : {item['evidence']}"
    console.print(Panel(body, title="Loop", border_style="blue"))


@app.command("archive")
def archive_cmd(db: Optional[Path] = typer.Option(None, "--db")):
    n = _store(db).archive_done()
    console.print(f"[green]Archived[/green] {n} done/cancelled loop(s)")


@app.command("export")
def export_cmd(path: Path, status: Optional[str] = typer.Option(None, "--status"), db: Optional[Path] = typer.Option(None, "--db")):
    rows = _store(db).list_loops(status=status, include_closed=status is None)
    (export_csv if path.suffix.lower() == ".csv" else export_json)(rows, path)
    console.print(f"[green]Exported[/green] {len(rows)} → {path}")


@app.command("import-csv")
def import_csv_cmd(file: Path, title: str = typer.Option("csv-import", "--title", "-t"), db: Optional[Path] = typer.Option(None, "--db")):
    if not file.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)
    cfg = _cfg()
    sid = str(uuid4())
    result = import_csv(file, source_id=sid, default_owner=cfg.get("me"), aliases=cfg.get("aliases") or {})
    sid, n = _store(db).save_ingest(title, result, path=str(file), source_id=sid)
    console.print(f"[green]Imported[/green] {n} loop(s) from {file.name}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
