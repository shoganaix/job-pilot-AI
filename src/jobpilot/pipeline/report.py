"""Fase 4: self-contained HTML dashboard over the queue, scores and pipeline health.

``jobpilot report`` renders a single ``report.html`` (no external assets) with
KPI cards, the application queue, the latest scoring run and a per-family
breakdown. Everything is escaped so the report is safe to open locally.
"""

from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jobpilot.config import Config
from jobpilot.models import AppStatus

STATUS_COLORS: dict[str, str] = {
    AppStatus.NEW.value: "#64748b",
    AppStatus.REVIEW.value: "#eab308",
    AppStatus.APPLY.value: "#16a34a",
    AppStatus.APPLIED.value: "#2563eb",
    AppStatus.INTERVIEWING.value: "#7c3aed",
    AppStatus.OFFER.value: "#0d9488",
    AppStatus.REJECTED.value: "#dc2626",
    AppStatus.DISCARDED.value: "#9ca3af",
    AppStatus.WITHDRAWN.value: "#9ca3af",
}
TRIAGE_COLORS: dict[str, str] = {"apply": "#16a34a", "review": "#eab308", "discard": "#dc2626"}
DIM_ORDER = ("skills", "experience", "education", "location", "seniority", "interest")

_BASE_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { font-family: ui-sans-serif, system-ui, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
       margin: 0; background: #f1f5f9; color: #0f172a; }
header { background: #0f172a; color: #e2e8f0; padding: 20px 28px; }
header h1 { margin: 0; font-size: 20px; }
header p { margin: 4px 0 0; color: #94a3b8; font-size: 13px; }
main { padding: 20px 28px 48px; max-width: 1100px; margin: 0 auto; }
section { margin-top: 28px; }
h2 { font-size: 15px; text-transform: uppercase; letter-spacing: .06em; color: #475569;
     border-bottom: 1px solid #cbd5e1; padding-bottom: 6px; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 14px; }
.card .label { font-size: 12px; color: #64748b; }
.card .value { font-size: 26px; font-weight: 700; margin-top: 2px; }
.card .sub { font-size: 12px; color: #94a3b8; margin-top: 2px; }
table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e2e8f0;
        border-radius: 10px; overflow: hidden; font-size: 13px; }
th { text-align: left; padding: 8px 10px; background: #f8fafc; color: #475569;
     border-bottom: 1px solid #e2e8f0; font-weight: 600; }
td { padding: 8px 10px; border-top: 1px solid #f1f5f9; vertical-align: top; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
tr:hover td { background: #f8fafc; }
a { color: #2563eb; text-decoration: none; }
a:hover { text-decoration: underline; }
.badge { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 11px;
         font-weight: 600; color: #fff; white-space: nowrap; }
.muted { color: #94a3b8; }
.center { text-align: center; padding: 24px; }
details { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 12px; margin-top: 8px; }
summary { cursor: pointer; color: #475569; font-size: 13px; }
.dims { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px 18px;
        margin-top: 6px; }
.dim { font-size: 12px; }
.dim .row { display: flex; justify-content: space-between; color: #475569; }
.bar { height: 6px; background: #e2e8f0; border-radius: 999px; overflow: hidden; margin-top: 2px; }
.bar > div { height: 100%; background: #2563eb; border-radius: 999px; }
.bar.apply > div { background: #16a34a; }
.bar.review > div { background: #eab308; }
.evidence { color: #94a3b8; font-size: 11px; margin-top: 2px; }
footer { text-align: center; color: #94a3b8; font-size: 12px; padding: 24px 0 48px; }
"""


def _esc(value: Any) -> str:
    return "" if value is None else html.escape(str(value), quote=True)


def _badge(text: str, color: str) -> str:
    return f'<span class="badge" style="background:{color}">{_esc(text)}</span>'


def _card(label: str, value: Any, sub: str = "", color: str = "#0f172a") -> str:
    return (
        f'<div class="card"><div class="label">{_esc(label)}</div>'
        f'<div class="value" style="color:{color}">{_esc(value)}</div>'
        f'<div class="sub">{_esc(sub)}</div></div>'
    )


def _json_dict(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def _breakdown(row) -> list[tuple[str, float, float, str]]:
    data = _json_dict(row["breakdown"])
    out: list[tuple[str, float, float, str]] = []
    for key in DIM_ORDER:
        d = data.get(key)
        if isinstance(d, dict):
            out.append(
                (key, float(d.get("value") or 0), float(d.get("weight") or 0), _esc(d.get("evidence") or ""))
            )
    return out


def _score_badge(row) -> str:
    triage = str(row["triage"] or "discard")
    color = TRIAGE_COLORS.get(triage, "#9ca3af")
    score = f"{float(row['score']):.0f}"
    return f"{_badge(score, color)} {_badge(triage, color)}"


def _top_scores(scores: list, limit: int = 250) -> str:
    if not scores:
        return '<div class="center muted">Sin puntúaciones. Ejecuta <code>jobpilot score</code>.</div>'
    body: list[str] = []
    for row in scores[:limit]:
        title = _esc(row["title"] or "")
        company = _esc(row["company"] or "")
        link = row["apply_url"] or row["url"]
        title_cell = (
            f'<a href="{_esc(link)}" target="_blank" rel="noopener">{title}</a>' if link else title
        )
        family = _esc((row["family"] or "").replace(",", ", "))
        body.append(
            f"<tr><td class='num'>{row['offer_id']}</td>"
            f"<td>{_score_badge(row)}</td>"
            f"<td>{family}</td><td>{company}</td><td>{title_cell}</td></tr>"
        )
    head = "<tr><th>id</th><th>score</th><th>familia</th><th>empresa</th><th>posición</th></tr>"
    return f"<table>{head}{''.join(body)}</table>"


def _cv_cell(row) -> str:
    cv = str(row["cv_file"] or "")
    if not cv:
        return '<span class="muted">-</span>'
    p = Path(cv)
    if p.is_absolute():
        return f'<a href="{p.as_uri()}">{_esc(p.name)}</a>'
    return f'<a href="{_esc(cv)}">{_esc(p.name)}</a>'


def _queue_table(apps: list) -> str:
    if not apps:
        return (
            '<div class="center muted">La cola está vacía. Encolar: '
            '<code>jobpilot queue set &lt;id&gt; --status apply</code>.</div>'
        )
    body: list[str] = []
    for row in apps:
        status = str(row["status"])
        color = STATUS_COLORS.get(status, "#64748b")
        cv_cell = _cv_cell(row)
        link = row["url"] or row["apply_url"]
        t = _esc(row["title"] or "")
        title_cell = f'<a href="{_esc(link)}" target="_blank" rel="noopener">{t}</a>' if link else t
        body.append(
            f"<tr><td>{_badge(status, color)}</td>"
            f"<td class='num'>{row['offer_id']}</td>"
            f"<td>{_esc(row['company'] or '')}</td><td>{title_cell}</td>"
            f"<td>{cv_cell}</td>"
            f"<td>{_esc(row['notes'] or '')}</td>"
            f"<td>{_esc(row['updated_at'] or '')}</td></tr>"
        )
    head = (
        "<tr><th>estado</th><th>id</th><th>empresa</th><th>posición</th>"
        "<th>cv</th><th>notas</th><th>actualizado</th></tr>"
    )
    return f"<table>{head}{''.join(body)}</table>"


def _family_stats(scores: list) -> str:
    stats: dict[str, dict] = {}
    for row in scores:
        for fam in (row["family"] or "").split(","):
            fam = fam.strip()
            if not fam:
                continue
            s = stats.setdefault(fam, {"n": 0, "sum": 0.0, "apply": 0, "review": 0, "discard": 0})
            s["n"] += 1
            s["sum"] += float(row["score"] or 0)
            s[str(row["triage"] or "discard")] += 1
    if not stats:
        return '<div class="center muted">Sin datos por familia.</div>'
    rows: list[str] = []
    for fam, s in sorted(stats.items(), key=lambda kv: -kv[1]["n"]):
        avg = s["sum"] / s["n"] if s["n"] else 0
        rows.append(
            f"<tr><td>{_esc(fam)}</td><td class='num'>{s['n']}</td>"
            f"<td class='num'>{avg:.0f}</td>"
            f"<td class='num'>{s['apply']}</td>"
            f"<td class='num'>{s['review']}</td>"
            f"<td class='num'>{s['discard']}</td></tr>"
        )
    head = (
        "<tr><th>familia</th><th>ofertas</th><th>avg</th>"
        "<th>apply</th><th>review</th><th>discard</th></tr>"
    )
    return f"<table>{head}{''.join(rows)}</table>"


def _breakdown_panels(scores: list, limit: int = 5) -> str:
    if not scores:
        return ""
    panels: list[str] = ['<div class="dims-repeat"></div>']
    for row in scores[:limit]:
        dims = _breakdown(row)
        bars = ""
        for name, value, weight, evidence in dims:
            cls = "apply" if value >= 70 else ("review" if value >= 45 else "")
            bars += (
                f'<div class="dim"><div class="row"><span>{_esc(name)}</span>'
                f"<span>{value:.0f} · peso {weight:.0f}</span></div>"
                f'<div class="bar {cls}"><div style="width:{value:.0f}%"></div></div>'
                f'<div class="evidence">{_esc(evidence)}</div></div>'
            )
        reason = _esc(row["reason"] or "")
        company = _esc(row["company"] or "")
        title = _esc(row["title"] or "")
        panels.append(
            f"<details><summary>{_score_badge(row)} &nbsp;{company} — {title}"
            + (f" &nbsp;<span class='muted'>{reason}</span>" if reason else "")
            + f"</summary><div class='dims'>{bars}</div></details>"
        )
    return "".join(panels)


def build_report(
    config: Config,
    conn,
    *,
    family: str | None = None,
    out: Path | None = None,
) -> Path:
    """Render the dashboard and write it as a single self-contained HTML file."""
    from .. import storage

    total_offers = storage.count_offers(conn)
    run = storage.latest_run(conn)
    run_id = storage.latest_scored_run(conn)
    scores = storage.scores_for_run(conn, run_id) if run_id else []
    if family:
        scores = [r for r in scores if family in (r["family"] or "").split(",")]
    apps = storage.list_applications(conn)
    cv_count = len(storage.list_cv_variants(conn))

    status_counts = {s: 0 for s in AppStatus}
    for row in apps:
        status_counts[row["status"]] += 1
    queue_open = status_counts[AppStatus.APPLY] + status_counts[AppStatus.REVIEW]
    queue_progress = sum(status_counts[s] for s in (AppStatus.APPLIED, AppStatus.INTERVIEWING, AppStatus.OFFER))

    triage_counts = {"apply": 0, "review": 0, "discard": 0}
    for row in scores:
        triage_counts[str(row["triage"] or "discard")] += 1

    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    run_note = _esc(run.notes) if run else ""
    subtitle = (
        f"{generated} · run#{run_id or '-'}"
        + (f" · {run_note}" if run_note else "")
        + (f" · filtro familia: {family}" if family else "")
    )

    kpis = "".join(
        [
            _card("Ofertas almacenadas", total_offers, "en la base local"),
            _card("Puntuadas (último run)", len(scores), f"run #{run_id or '-'}"),
            _card("Apply", triage_counts["apply"], "score ≥ 65", TRIAGE_COLORS["apply"]),
            _card("Review", triage_counts["review"], "score ≥ 45", TRIAGE_COLORS["review"]),
            _card("Descartadas", triage_counts["discard"], "score < 45 / filtros duros", TRIAGE_COLORS["discard"]),
            _card("En cola", queue_open, "apply + review"),
            _card("Progreso", queue_progress, "applied · interviewing · offer"),
            _card("CV generados", cv_count, "en output/cv/"),
        ]
    )

    body = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JobPilot Report</title>
<style>{_BASE_CSS}</style>
</head>
<body>
<header><h1>JobPilot · Dashboard de aplicaciones</h1><p>{_esc(subtitle)}</p></header>
<main>
<section><h2>Resumen</h2><div class="kpis">{kpis}</div></section>
<section><h2>Cola de aplicaciones</h2>{_queue_table(apps)}</section>
<section><h2>Mejores posiciones (último run)</h2>{_top_scores(scores)}</section>
<section><h2>Desglose de scoring (top {min(len(scores), 5) if scores else 0})</h2>{_breakdown_panels(scores)}</section>
<section><h2>Familias</h2>{_family_stats(scores)}</section>
<footer>Generado por jobpilot · datos locales en data/jobpilot.db</footer>
</main>
</body>
</html>"""

    out_path = Path(out if out is not None else Path(config.output_dir) / "report.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    return out_path
