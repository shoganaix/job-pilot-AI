"""JobPilot command line interface.

    jobpilot init        scaffold config + database
    jobpilot sources     show which sources are available (and why any is off)
    jobpilot plan        dry-run: show exactly what a sync would call
    jobpilot sync        run the multi-source search and store offers
    jobpilot offers      list stored offers
    jobpilot queue       show the application queue
    jobpilot queue set <id> --status <s>   move an offer through the pipeline
    jobpilot open <id>   open an offer in the browser
    jobpilot score       (Fase 2)   run the matching engine
    jobpilot cv          (Fase 3)   tailor + export tailored CVs
    jobpilot report      (Fase 4)   generate the HTML dashboard
"""

from __future__ import annotations

import argparse
import shutil
import sys
import webbrowser
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .config import (
    DEFAULT_DB_PATH,
    REPO_ROOT,
    ConfigError,
    load_config,
    load_dotenv,
)
from .models import AppStatus

RESOURCES = Path(__file__).parent / "resources"
CONSOLE = Console()


# --------------------------------------------------------------------------- #
# Entry point / routing
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobpilot", description="Personal job application agent")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="scaffold config files and database")

    sub.add_parser("sources", help="list available/disabled job sources")

    p = sub.add_parser("plan", help="show exactly what the next sync would do")
    p.add_argument("--family", help="only plan this family")

    p = sub.add_parser("sync", help="run the multi-source search and store offers")
    p.add_argument("--family", help="only sync this family")
    p.add_argument("--dry-run", action="store_true", help="fetch but do not persist")
    p.add_argument("--source", action="append", default=None, help="only use these sources")
    p.add_argument("--max-pages", type=int, default=None, help="override max pages per query")

    p = sub.add_parser("offers", help="list stored offers")
    p.add_argument("--family", action="append", default=None)
    p.add_argument("--source", action="append", default=None)
    p.add_argument("--limit", type=int, default=40)
    p.add_argument("--has-description", action="store_true", help="only offers with full description")

    p = sub.add_parser("queue", help="show the application queue")
    p.add_argument("set", nargs="?", help="offer id to update")
    p.add_argument("--status", choices=[s.value for s in AppStatus], help="new status (with `set`)")
    p.add_argument("--notes", default="")

    p = sub.add_parser("open", help="open an offer in the browser")
    p.add_argument("id", type=int)

    p = sub.add_parser("score", help="run the matching engine over stored offers")
    p.add_argument("--family", help="only score this family")
    p.add_argument("--limit", type=int, default=None, help="max offers to score")
    p.add_argument("--show", type=int, default=5, help="rows shown per triage")
    p.add_argument("--details", action="store_true", help="print dimension breakdown")

    for name in ("cv", "report"):
        p = sub.add_parser(name, help=f"({name} module) ")
        p.add_argument("--family")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _dispatch(args)
    except ConfigError as exc:
        CONSOLE.print(f"[red]config error:[/] {exc}")
        return 2
    except KeyboardInterrupt:
        CONSOLE.print("\n[dim]interrupted[/]")
        return 130


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "init":
        return _cmd_init()
    if args.command == "sources":
        return _cmd_sources()
    if args.command == "plan":
        return _cmd_plan(args)
    if args.command in ("sync",):
        return _cmd_sync(args)
    if args.command == "offers":
        return _cmd_offers(args)
    if args.command == "queue":
        return _cmd_queue(args)
    if args.command == "open":
        return _cmd_open(args)
    if args.command == "score":
        return _cmd_score(args)
    if args.command == "cv":
        CONSOLE.print("[yellow]cv[/]: tailleur de CV llega en Fase 3.")
        return 0
    if args.command == "report":
        CONSOLE.print("[yellow]report[/]: dashboard HTML llega en Fase 4.")
        return 0
    return 1


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def _cmd_init() -> int:
    config_dir = REPO_ROOT / "config"
    config_dir.mkdir(exist_ok=True)
    (REPO_ROOT / "data").mkdir(exist_ok=True)

    for target, name in (
        (config_dir / "profile.yaml", "profile.yaml"),
        (config_dir / "master_cv.yaml", "master_cv.yaml"),
    ):
        if target.exists():
            CONSOLE.print(f"[dim]exists[/] {target.relative_to(REPO_ROOT)}")
        else:
            shutil.copy(RESOURCES / name, target)
            CONSOLE.print(f"[green]created[/] {target.relative_to(REPO_ROOT)}")

    env_target = REPO_ROOT / ".env"
    if not env_target.exists():
        shutil.copy(REPO_ROOT / ".env.example", env_target)
        CONSOLE.print("[green]created[/] .env  <- pon tu ADZUNA_APP_ID/KEY (free: developer.adzuna.com)")
    else:
        CONSOLE.print("[dim]exists[/] .env")

    from . import storage

    storage.connect(DEFAULT_DB_PATH)
    CONSOLE.print(f"[green]db ready[/] {DEFAULT_DB_PATH}")
    CONSOLE.print("\nSiguientes pasos:\n  1. Edita config/master_cv.yaml y config/profile.yaml\n  2. jobpilot plan   (qué se buscará)\n  3. jobpilot sync   (descarga ofertas)")
    return 0


def _cmd_sources() -> int:
    config = load_config()
    from .sources.registry import SOURCE_META, build_sources

    enabled, disabled = build_sources(config)
    table = Table(title="Fuentes de ofertas")
    table.add_column("source")
    table.add_column("estado")
    table.add_column("descripción")
    for name in SOURCE_META:
        if name in enabled:
            locs = ", ".join(loc.name for loc in enabled[name].locations()) or "per-profile countries"
            table.add_row(name, "[green]enabled[/]", f"{SOURCE_META[name]} ({locs})")
        elif name in disabled:
            table.add_row(name, "[red]disabled[/]", disabled[name])
        else:
            table.add_row(name, "[dim]not used[/]", SOURCE_META[name])
    CONSOLE.print(table)
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    config = load_config()
    from .pipeline.search import (
        guess_family,  # noqa: F401
        plan,
    )
    from .sources.registry import build_sources

    enabled, disabled = build_sources(config)
    planned = plan(config, enabled)
    if args.family:
        planned = [p for p in planned if p.family.id == args.family]

    table = Table(title="Plan de sync (proyección)")
    table.add_column("familia")
    table.add_column("consulta")
    table.add_column("fuente")
    table.add_column("ubicación")
    table.add_column("páginas")
    rows: dict[tuple, int] = {}
    for p in planned:
        key = (p.family.id, p.query, p.source, p.location.name)
        rows[key] = config.search.max_pages_per_query
    for (fam, query, source, loc), pages in sorted(rows.items()):
        table.add_row(fam, query, source, loc, str(pages))
    CONSOLE.print(table)

    ats = []
    for s in ("greenhouse", "lever"):
        for c in config.ats_companies.get(s, []):
            ats.append(f"{s}: {c}")
    if ats:
        CONSOLE.print(f"[dim]ATS watchlist:[/] {', '.join(ats)}")

    calls = sum(rows.values()) + len(ats)
    CONSOLE.print(f"\nUso proyectado: [bold]{calls}[/] llamadas a APIs"
                  + ("  ([red]aviso: Adzuna free ~250/día[/])" if calls > 200 else "  [green]dentro de límites free[/]"))
    for src, reason in disabled.items():
        CONSOLE.print(f"[yellow]~ desactivada:[/] {src}: {reason}")
    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    load_dotenv()
    config = load_config()
    from . import storage
    from .pipeline.search import run_sync
    from .sources.registry import build_sources

    conn = storage.connect(config.db_path)
    enabled, disabled = build_sources(config, requested=args.source)

    with CONSOLE.status("Buscando ofertas…") as status:
        import time

        if args.dry_run:
            run = None
        else:
            run = storage.run_start(conn, notes=f"sync família={args.family or 'todas'}")
        started = time.time()
        stats = run_sync(
            config, conn, enabled,
            run=run,
            family_filter=args.family,
            max_pages=args.max_pages,
            dry_run=args.dry_run,
        )
        elapsed = time.time() - started
        if run and not args.dry_run:
            run_fin = storage.run_finish(conn, run, stats.to_dict())
            status.update(f"sync #{run_fin.id} en {elapsed:.1f}s")

    table = Table(title="Resultado del sync" + (f" — run #{run.id}" if run else " (dry-run)"))
    table.add_column("fuente")
    table.add_column("llamadas")
    table.add_column("ofertas vistas")
    table.add_column("nuevas")
    table.add_column("actualizadas")
    table.add_column("duplicadas")
    for src in sorted(stats.calls):
        inserted, updated, dupes = stats.stored.get(src, [0, 0, 0])
        table.add_row(src, str(stats.calls[src]), str(stats.raw_rows.get(src, 0)),
                      str(inserted), str(updated), str(dupes))
    CONSOLE.print(table)

    if stats.seen_by_family:
        fams = Table(title="Ofertas vistas por familia")
        fams.add_column("familia")
        fams.add_column("vistas")
        for fam, n in sorted(stats.seen_by_family.items(), key=lambda x: -x[1]):
            fams.add_row(fam, str(n))
        CONSOLE.print(fams)

    if not args.dry_run:
        total = storage.count_offers(conn)
        CONSOLE.print(f"[bold]{stats.total_inserted}[/] nuevas guardadas. Total en BBDD: [bold]{total}[/] ofertas.")
        CONSOLE.print("Siguiente: `jobpilot score` (Fase 2) para el matching.")
    for src, reason in disabled.items():
        CONSOLE.print(f"[yellow]~ sin fuente:[/] {src}: {reason}")
    return 0


def _cmd_offers(args: argparse.Namespace) -> int:
    config = load_config()
    from . import storage

    conn = storage.connect(config.db_path)
    rows = storage.list_offers(
        conn,
        families=args.family,
        sources=args.source,
        has_description=args.has_description,
        limit=args.limit,
    )
    if not rows:
        CONSOLE.print("[yellow]Sin ofertas. Ejecuta `jobpilot sync` primero.[/]")
        return 0
    table = Table(title=f"Ofertas almacenadas ({min(len(rows), args.limit)})")
    for col in ("id", "fuente", "empresa", "título", "ubicación", "familia"):
        table.add_column(col)
    for row in rows:
        table.add_row(str(row["id"]), row["source"], row["company"], row["title"], row["location"], row["family"] or "")
    CONSOLE.print(table)
    return 0


def _cmd_queue(args: argparse.Namespace) -> int:
    config = load_config()
    from . import storage

    conn = storage.connect(config.db_path)

    if args.set is not None:
        if not args.status:
            CONSOLE.print("[red]necesitas --status al usar `queue set`[/]")
            return 2
        offer_id = int(args.set)
        try:
            storage.set_application(
                conn, offer_id, AppStatus(args.status),
                notes=args.notes,
            )
        except KeyError as exc:
            CONSOLE.print(f"[red]{exc}[/]")
            return 1
        CONSOLE.print(f"[green]oferta {offer_id} → {args.status}[/]")
        return 0

    rows = storage.list_applications(conn)
    if not rows:
        CONSOLE.print("[yellow]Cola vacía. Usa `jobpilot queue set <id> --status apply|review|…`[/]")
        return 0
    table = Table(title="Cola de aplicaciones")
    for col in ("id", "estado", "empresa", "título", "cv", "notas"):
        table.add_column(col)
    for row in rows:
        table.add_row(str(row["offer_id"]), row["status"], row["company"],
                      row["title"], row["cv_file"] or "-", row["notes"] or "-")
    CONSOLE.print(table)
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    config = load_config()
    from . import storage
    from .models import Triage
    from .pipeline.score import run_score

    conn = storage.connect(config.db_path)

    with CONSOLE.status("Puntuando ofertas…") as status:
        run = storage.run_start(conn, notes=f"score família={args.family or 'todas'}")
        stats = run_score(
            config, conn,
            run=run,
            family_filter=args.family,
            limit=args.limit,
        )
        run_fin = storage.run_finish(conn, run, stats.to_dict())
        status.update("ok")

    if not stats.scored:
        CONSOLE.print("[yellow]Sin ofertas que puntuar. Ejecuta `jobpilot sync` primero.[/]")
        return 0

    triage_styles = {Triage.APPLY.value: "green", Triage.REVIEW.value: "yellow", Triage.DISCARD.value: "red"}

    summary = Table(title=f"Resultado del scoring — run #{run_fin.id}")
    summary.add_column("triage")
    summary.add_column("nº")
    summary.add_column("%")
    for t in Triage:
        n = stats.by_triage.get(t.value, 0)
        pct = 100.0 * n / stats.scored
        summary.add_row(f"[{triage_styles[t.value]}]{t.value}[/]", str(n), f"{pct:.0f}%")
    summary.add_row("[bold]media total[/]", str(stats.scored), f"[bold]{stats.to_dict()['avg']}[/]")
    summary.add_row("[dim]hard filters[/]", str(stats.discarded_by_hard_filters), "")
    CONSOLE.print(summary)

    rows = storage.scores_for_run(conn, run_fin.id)
    per_triage: dict[str, list] = {t.value: [] for t in Triage}
    for row in rows:
        per_triage[row["triage"]].append(row)
    for t in (Triage.APPLY, Triage.REVIEW):
        top = per_triage[t.value][: args.show]
        if not top:
            continue
        table = Table(title=f"{t.value} (top {len(top)})")
        for col in ("id", "score", "empresa", "título", "ubicación"):
            table.add_column(col)
        for row in top:
            _f = row["family"]
            table.add_row(str(row["offer_id"]), f"[{triage_styles[t.value]}]{row['score']:.0f}[/]",
                          row["company"], row["title"] or "", row["location"] or "")
        CONSOLE.print(table)
    CONSOLE.print("Siguiente: `jobpilot cv` (Fase 3) para generar el CV tailorizado "
                  "o `jobpilot queue set <id> --status apply` para cargarlo en la cola.")
    return 0


def _cmd_open(args: argparse.Namespace) -> int:
    config = load_config()
    from . import storage

    conn = storage.connect(config.db_path)
    row = storage.get_offer(conn, args.id)
    if row is None:
        CONSOLE.print(f"[red]oferta {args.id} no encontrada[/]")
        return 1
    url = row["apply_url"] or row["url"]
    CONSOLE.print(f"Abrindo [bold]{row['company']} — {row['title']}[/]")
    CONSOLE.print(f"[dim]{url}[/]")
    webbrowser.open(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
