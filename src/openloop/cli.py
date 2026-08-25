from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Optional
from uuid import uuid4

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .digest import format_digest_markdown, format_digest_slack
from .extractor import extract
from .store import LoopStore

app = typer.Typer(
    help="OpenLoop – catch commitments that die in chat and notes",
    no_args_is_help=True,
)
console = Console()


def _store(db: Optional[Path] = None) -> LoopStore:
    return LoopStore(db) if db else LoopStore()


def _print_loops(rows: list[dict], title: str) -> None:
    table = Table(title=title)
    table.add_column("ID", style="dim", max_width=8)
    table.add_column("Owner")
    table.add_column("Commitment")
    table.add_column("Due")
    table.add_column("Status")
    table.add_column("Source", style="cyan")
    for r in rows:
        due = r.get("due_date") or r.get("due_text") or "—"
        table.add_row(
            r["id"][:8],
            r.get("owner") or "—",
            r["text"],
            str(due),
            r["status"],
            r.get("source_title") or "",
        )
    console.print(table)
    if not rows:
        console.print("[dim]None.[/dim]")


@app.command("ingest")
def ingest_cmd(
    file: Path = typer.Argument(..., help="Chat export, notes, or email dump"),
    title: str = typer.Option(..., "--title", "-t", help="Source label"),
    date_str: Optional[str] = typer.Option(
        None, "--date", "-d", help="Reference date YYYY-MM-DD for relative deadlines"
    ),
    me: Optional[str] = typer.Option(
        None, "--me", help="Your name — maps I/I'll commitments to this owner"
    ),
    rules: bool = typer.Option(
        False, "--rules", help="Force offline rule extractor (no API)"
    ),
    replace: bool = typer.Option(
        False, "--replace", help="Replace loops from a previous ingest with same title"
    ),
    model: str = typer.Option("gpt-4o-mini", "--model"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    db: Optional[Path] = typer.Option(None, "--db"),
):
    """Ingest a text file and extract open commitments (loops)."""
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
    console.print(f"[bold]Ingesting[/bold] {file.name} ...")
    try:
        result = extract(
            text,
            source_id=source_id,
            reference_date=ref,
            model=model,
            base_url=base_url,
            default_owner=me,
            force_rules=rules,
        )
    except Exception as e:
        console.print(f"[red]Extract failed:[/red] {e}")
        raise typer.Exit(1) from e

    sid = store.save_ingest(
        title,
        result,
        path=str(file),
        source_id=source_id,
        replace_title=replace,
    )
    console.print(f"[green]Saved[/green] {len(result.loops)} loop(s) under '{title}' ({sid[:8]})")
    if result.loops:
        _print_loops(
            [
                {
                    **L.model_dump(),
                    "due_date": L.due_date.isoformat() if L.due_date else None,
                    "source_title": title,
                    "status": L.status.value,
                }
                for L in result.loops
            ],
            "Extracted loops",
        )


@app.command("list")
def list_cmd(
    status: Optional[str] = typer.Option("open", "--status", "-s"),
    owner: Optional[str] = typer.Option(None, "--owner", "-o"),
    overdue: bool = typer.Option(False, "--overdue"),
    due_soon: Optional[int] = typer.Option(None, "--due-soon"),
    unassigned: bool = typer.Option(False, "--unassigned"),
    db: Optional[Path] = typer.Option(None, "--db"),
):
    """List loops."""
    store = _store(db)
    rows = store.list_loops(
        status=None if overdue or due_soon is not None or unassigned else status,
        owner=owner,
        overdue=overdue,
        due_within_days=due_soon,
        unassigned=unassigned,
    )
    title = "Loops"
    if overdue:
        title = "Overdue"
    elif due_soon is not None:
        title = f"Due within {due_soon}d"
    elif unassigned:
        title = "Unassigned"
    _print_loops(rows, title)


@app.command("digest")
def digest_cmd(
    days: int = typer.Option(7, "--days", "-n"),
    format: str = typer.Option("rich", "--format", "-f", help="rich | md | slack"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    db: Optional[Path] = typer.Option(None, "--db"),
):
    """Still-open digest — the artifact you paste into standup."""
    store = _store(db)
    d = store.digest(days=days)
    fmt = format.lower().strip()
    if fmt == "md":
        content = format_digest_markdown(d)
    elif fmt == "slack":
        content = format_digest_slack(d)
    elif fmt == "rich":
        content = None
    else:
        console.print("[red]--format must be rich, md, or slack[/red]")
        raise typer.Exit(1)

    if content is not None:
        if output:
            output.write_text(content, encoding="utf-8")
            console.print(f"[green]Wrote[/green] {output}")
        else:
            console.print(content, highlight=False)
        return

    console.print(
        Panel.fit(
            f"[bold]OpenLoop digest[/bold]  ·  {d['as_of']}\n"
            f"Open {d['open']}  ·  Overdue {len(d['overdue'])}  ·  "
            f"Due {days}d {len(d['due_soon'])}  ·  Unassigned {len(d['unassigned'])}",
            border_style="cyan",
        )
    )
    if d["by_owner"]:
        console.print("[bold]Load[/bold]")
        for n, c in d["by_owner"].items():
            console.print(f"  {n}: {c}")
    console.print()
    _print_loops(d["overdue"], "Overdue")
    console.print()
    _print_loops(d["due_soon"], f"Due within {days}d")
    console.print()
    _print_loops(d["unassigned"], "Unassigned")
    console.print()
    _print_loops(d["no_due"][:15], "Open · no deadline")


@app.command("done")
def done_cmd(
    item_id: str = typer.Argument(...),
    db: Optional[Path] = typer.Option(None, "--db"),
):
    """Close a loop."""
    store = _store(db)
    item = store.get(item_id)
    if not item:
        console.print(f"[red]Not found: {item_id}[/red]")
        raise typer.Exit(1)
    store.update(item["id"], status="done")
    console.print(f"[green]Done[/green] {item['id'][:8]} — {item['text']}")


@app.command("assign")
def assign_cmd(
    item_id: str = typer.Argument(...),
    owner: str = typer.Argument(..., help="Owner name, or - to clear"),
    db: Optional[Path] = typer.Option(None, "--db"),
):
    store = _store(db)
    item = store.get(item_id)
    if not item:
        console.print(f"[red]Not found: {item_id}[/red]")
        raise typer.Exit(1)
    new = None if owner.strip() in {"-", ""} else owner.strip()
    store.update(item["id"], owner=new if new is not None else "")
    console.print(f"[green]Assigned[/green] {item['id'][:8]} → {new or 'unassigned'}")


@app.command("snooze")
def snooze_cmd(
    item_id: str = typer.Argument(...),
    days: int = typer.Argument(3, help="Push due date by N days"),
    db: Optional[Path] = typer.Option(None, "--db"),
):
    store = _store(db)
    item = store.get(item_id)
    if not item:
        console.print(f"[red]Not found: {item_id}[/red]")
        raise typer.Exit(1)
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


@app.command("show")
def show_cmd(
    item_id: str = typer.Argument(...),
    db: Optional[Path] = typer.Option(None, "--db"),
):
    store = _store(db)
    item = store.get(item_id)
    if not item:
        console.print(f"[red]Not found: {item_id}[/red]")
        raise typer.Exit(1)
    body = (
        f"[bold]{item['text']}[/bold]\n\n"
        f"Owner    : {item.get('owner') or '(unassigned)'}\n"
        f"Due      : {item.get('due_date') or item.get('due_text') or '—'}\n"
        f"Status   : {item['status']}\n"
        f"Source   : {item.get('source_title')}\n"
        f"ID       : {item['id']}\n"
    )
    if item.get("evidence"):
        body += f"\nEvidence : {item['evidence']}"
    console.print(Panel(body, title="Loop", border_style="blue"))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
