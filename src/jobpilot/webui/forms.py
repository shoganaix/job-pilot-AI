"""HTML form builders for the local web UI (f-strings, no template engine).

Conventions the parsers in ``payload.py`` rely on:

* singleton inputs are named ``section.field`` (e.g. ``contact.email``);
* list rows are named ``prefix.<index>.<field>``; the index lives in the DOM
  only and may be sparse after a delete, which ``payload.rows`` handles;
* checkboxes share one name and carry the value to store (one input per
  selected option); a single on/off box is just ``name="x" value="1"``;
* textareas encode a YAML list as one entry per line.

JS only adds/removes rows; without it every static field still posts fine.
"""

from __future__ import annotations

import html
from typing import Any

from ..sources.registry import SOURCE_META

_FAMILY_SOURCES = tuple(
    s for s in SOURCE_META if s not in ("greenhouse", "lever")
)
_SENIORITY_LEVELS = ("junior", "midlevel", "senior", "lead")
_KINDS = ("onsite", "hybrid", "remote")

_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { font-family: ui-sans-serif, system-ui, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
       margin: 0; background: #f1f5f9; color: #0f172a; }
header { background: #0f172a; color: #e2e8f0; padding: 16px 28px 0; }
header h1 { margin: 0 0 10px; font-size: 20px; }
nav { display: flex; gap: 4px; flex-wrap: wrap; }
nav a { color: #94a3b8; text-decoration: none; font-size: 13px; padding: 8px 14px;
        border-radius: 8px 8px 0 0; }
nav a:hover { color: #e2e8f0; background: #1e293b; }
nav a.active { color: #fff; background: #1e293b; font-weight: 600; }
main { padding: 22px 28px 48px; max-width: 1100px; margin: 0 auto; }
h2 { font-size: 15px; text-transform: uppercase; letter-spacing: .06em; color: #475569;
     border-bottom: 1px solid #cbd5e1; padding-bottom: 6px; margin: 30px 0 14px; }
h2:first-child { margin-top: 0; }
.flash, .error { border-radius: 8px; padding: 10px 14px; margin-bottom: 16px; font-size: 13px; }
.flash { background: #dcfce7; border: 1px solid #86efac; color: #14532d; }
.error { background: #fee2e2; border: 1px solid #fca5a5; color: #7f1d1d; }
.hint { color: #64748b; font-size: 12px; margin-top: 4px; display: block; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; }
.grid { display: grid; gap: 12px; }
.grid.cols2 { grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
.grid.cols3 { grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); }
label.f { display: block; font-size: 13px; color: #334155; }
label.f > span.lbl { display: block; font-weight: 600; margin-bottom: 4px; }
input[type=text], input[type=number], input[type=email], textarea, select {
  width: 100%; padding: 7px 9px; border: 1px solid #cbd5e1; border-radius: 7px;
  font: inherit; font-size: 13px; background: #fff; color: #0f172a; }
textarea { resize: vertical; font-family: ui-monospace, Consolas, monospace; font-size: 12.5px; }
input:focus, textarea:focus, select:focus { outline: 2px solid #93c5fd; border-color: #2563eb; }
.checks { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 13px; }
.checks label { display: flex; align-items: center; gap: 6px; }
.rowblock { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
            padding: 12px 14px; margin-bottom: 12px; }
.rowblock > h3 { margin: 0 0 10px; font-size: 13px; color: #475569; }
.row { border-top: 1px dashed #e2e8f0; padding-top: 10px; margin-top: 10px; }
.row:first-of-type { border-top: 0; padding-top: 0; margin-top: 0; }
.rowhead { display: flex; justify-content: space-between; align-items: center;
           margin-bottom: 8px; font-size: 12px; color: #64748b; text-transform: uppercase;
           letter-spacing: .05em; }
button { font: inherit; font-size: 13px; border: 0; border-radius: 7px; cursor: pointer;
         padding: 9px 18px; background: #2563eb; color: #fff; font-weight: 600; }
button:hover { background: #1d4ed8; }
button.ghost { background: #f1f5f9; color: #475569; padding: 4px 10px; font-weight: 500; }
button.ghost:hover { background: #e2e8f0; }
.actions { display: flex; gap: 10px; align-items: center; margin-top: 18px; }
.actions .note { color: #64748b; font-size: 12px; }
table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e2e8f0;
        border-radius: 10px; overflow: hidden; font-size: 13px; }
th { text-align: left; padding: 8px 10px; background: #f8fafc; color: #475569;
     border-bottom: 1px solid #e2e8f0; font-weight: 600; }
td { padding: 8px 10px; border-top: 1px solid #f1f5f9; }
a { color: #2563eb; text-decoration: none; }
a:hover { text-decoration: underline; }
footer { text-align: center; color: #94a3b8; font-size: 12px; padding: 24px 0 48px; }
"""

_JS = """
function jpAdd(wrapId, tplId) {
  const wrap = document.getElementById(wrapId);
  const used = new Set(Array.from(wrap.querySelectorAll('input,textarea,select'))
    .map(el => parseInt(el.name.split('.')[1], 10)).filter(n => !isNaN(n)));
  let i = 0;
  while (used.has(i)) i++;
  const node = document.getElementById(tplId).content.cloneNode(true);
  node.querySelectorAll('[name]').forEach(el => { el.name = el.name.replace('__I__', i); });
  wrap.appendChild(node);
}
function jpDel(btn) { btn.closest('.row').remove(); }
"""

NAV = (
    ("/", "Panel"),
    ("/cv", "Mi CV"),
    ("/prefs", "Preferencias"),
    ("/families", "Familias"),
)


def esc(value: Any) -> str:
    return "" if value is None else html.escape(str(value), quote=True)


def page(title: str, body: str, active: str, flash: str = "", error: str = "") -> str:
    nav = "".join(
        f'<a href="{href}" class="{"active" if href == active else ""}">{label}</a>'
        for href, label in NAV
    )
    notices = ""
    if flash:
        notices += f'<div class="flash">{esc(flash)}</div>'
    if error:
        notices += f'<div class="error">{esc(error)}</div>'
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · JobPilot</title>
<style>{_CSS}</style>
</head>
<body>
<header><h1>JobPilot</h1><nav>{nav}</nav></header>
<main>{notices}<h2>{esc(title)}</h2>{body}</main>
<footer>Solo accesible desde 127.0.0.1 · cada guardado deja un copia .bak al lado del YAML</footer>
<script>{_JS}</script>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# Field primitives
# --------------------------------------------------------------------------- #
def text(label: str, name: str, value: str = "", hint: str = "") -> str:
    h = f'<span class="hint">{esc(hint)}</span>' if hint else ""
    return (
        f'<label class="f"><span class="lbl">{esc(label)}</span>'
        f'<input type="text" name="{esc(name)}" value="{esc(value)}">{h}</label>'
    )


def num(label: str, name: str, value: Any, hint: str = "") -> str:
    h = f'<span class="hint">{esc(hint)}</span>' if hint else ""
    return (
        f'<label class="f"><span class="lbl">{esc(label)}</span>'
        f'<input type="number" step="any" name="{esc(name)}" value="{esc(value)}">{h}</label>'
    )


def area(label: str, name: str, value: str = "", rows: int = 4, hint: str = "") -> str:
    h = f'<span class="hint">{esc(hint)}</span>' if hint else ""
    body = esc(value)
    return (
        f'<label class="f"><span class="lbl">{esc(label)}</span>'
        f'<textarea name="{esc(name)}" rows="{rows}">{body}</textarea>{h}</label>'
    )


def checks(name: str, options: tuple[str, ...] | list[str], selected: list[str],
           labels: dict[str, str] | None = None) -> str:
    items = "".join(
        f'<label><input type="checkbox" name="{esc(name)}" value="{esc(opt)}"'
        f'{" checked" if opt in selected else ""}> {esc((labels or {}).get(opt, opt))}</label>'
        for opt in options
    )
    return f'<div class="checks">{items}</div>'


def select(label: str, name: str, options: list[str], value: str) -> str:
    opts = "".join(
        f'<option value="{esc(opt)}"{" selected" if opt == value else ""}>{esc(opt)}</option>'
        for opt in options
    )
    return (
        f'<label class="f"><span class="lbl">{esc(label)}</span>'
        f'<select name="{esc(name)}">{opts}</select></label>'
    )


def onoff(label: str, name: str, value: bool, hint: str = "") -> str:
    h = f'<span class="hint">{esc(hint)}</span>' if hint else ""
    return (
        f'<label class="f"><span class="lbl">{esc(label)}</span>'
        f'<span class="checks"><label><input type="checkbox" name="{esc(name)}"'
        f' value="1"{" checked" if value else ""}> sí</label></span>{h}</label>'
    )


def _lines_of(value: Any) -> str:
    """Render a YAML list of strings (or a bilingual dict) as textarea lines."""
    if isinstance(value, list):
        return "\n".join(
            _dict_to_line(v) if isinstance(v, dict) else str(v) for v in value
        )
    return str(value or "")


def _dict_to_line(value: dict) -> str:
    return str(value.get("es", next(iter(value.values()), "")) if value else "")


def _bi(value: Any) -> tuple[str, str]:
    """(es, en) of a bilingual field: a dict {es, en}, a plain string, or ''."""
    if isinstance(value, dict):
        return str(value.get("es") or ""), str(value.get("en") or "")
    if isinstance(value, str):
        return value, ""
    return "", ""


def row_block(
    title: str,
    wrap_id: str,
    tpl_id: str,
    rows_html: str,
    add_label: str,
    hint: str = "",
) -> str:
    h = f'<span class="hint">{esc(hint)}</span>' if hint else ""
    body = rows_html
    return (
        f'<div class="rowblock"><h3>{esc(title)}</h3>{h}'
        f'<div id="{wrap_id}">{body}</div>'
        f'<button type="button" class="ghost" onclick="jpAdd(\'{wrap_id}\',\'{tpl_id}\')">'
        f"+ {esc(add_label)}</button></div>"
    )


# --------------------------------------------------------------------------- #
# CV form
# --------------------------------------------------------------------------- #
def cv_form(cv: dict[str, Any], flash: str = "", error: str = "") -> str:
    contact = cv.get("contact", {}) or {}
    summary = cv.get("summary", {}) or {}

    contact_grid = "".join(
        text(label, f"contact.{key}", str(contact.get(key, "")))
        for key, label in (
            ("name", "Nombre"),
            ("email", "Email"),
            ("phone", "Teléfono"),
            ("city", "Ciudad"),
            ("linkedin", "LinkedIn"),
            ("github", "GitHub"),
        )
    )

    exp_rows, exp_tpl = _cv_rows(
        "exp",
        [
            ("company", "Empresa", "text", ""),
            ("role_es", "Puesto (es)", "text", ""),
            ("role_en", "Puesto (en)", "text", ""),
            ("start", "Inicio (MM/AAAA)", "text", ""),
            ("end", "Fin (MM/AAAA o 'actual')", "text", ""),
            ("bullets_es", "Logros (es)", "area", "una viñeta por línea"),
            ("bullets_en", "Logros (en)", "area", "una línea por viñeta, alineada con la es"),
        ],
        cv.get("experience", []) or [],
        lambda item: {
            "company": item.get("company", ""),
            "role_es": (item.get("role") or {}).get("es", ""),
            "role_en": (item.get("role") or {}).get("en", ""),
            "start": item.get("start", ""),
            "end": item.get("end", ""),
            "bullets_es": _lines_of([b.get("es", "") for b in item.get("bullets", [])]),
            "bullets_en": _lines_of([b.get("en", "") for b in item.get("bullets", [])]),
        },
    )

    edu_rows, edu_tpl = _cv_rows(
        "edu",
        [
            ("degree_es", "Título (es)", "text", ""),
            ("degree_en", "Título (en)", "text", ""),
            ("school", "Centro", "text", ""),
            ("start", "Inicio (MM/AAAA)", "text", ""),
            ("end", "Fin (MM/AAAA)", "text", ""),
        ],
        cv.get("education", []) or [],
        lambda item: {
            "degree_es": (item.get("degree") or {}).get("es", ""),
            "degree_en": (item.get("degree") or {}).get("en", ""),
            "school": item.get("school", ""),
            "start": item.get("start", ""),
            "end": item.get("end", ""),
        },
    )

    skill_rows, skill_tpl = _cv_rows(
        "sgrp",
        [
            ("group", "Grupo", "text", "p.ej. Lenguajes, Robótica y control"),
            ("items", "Herramientas", "area", "una por línea; igual en ambos idiomas"),
        ],
        [{"group": name, "items": "\n".join(str(i) for i in items)}
         for name, items in (cv.get("skills", {}) or {}).items()],
        lambda item: {
            "group": item.get("group", ""),
            "items": item.get("items", ""),
        },
    )

    proj_rows, proj_tpl = _cv_rows(
        "proj",
        [
            ("name_es", "Nombre (es)", "text", ""),
            ("name_en", "Nombre (en)", "text", ""),
            ("url", "URL", "text", ""),
            ("desc_es", "Descripción (es)", "area", ""),
            ("desc_en", "Descripción (en)", "area", ""),
        ],
        cv.get("projects", []) or [],
        lambda item: {
            "name_es": (item.get("name") or {}).get("es", "")
            if isinstance(item.get("name"), dict) else str(item.get("name") or ""),
            "name_en": (item.get("name") or {}).get("en", "")
            if isinstance(item.get("name"), dict) else "",
            "url": item.get("url", ""),
            "desc_es": _bi(item.get("description"))[0],
            "desc_en": _bi(item.get("description"))[1],
        },
    )

    cert_rows, cert_tpl = _cv_rows(
        "cert",
        [
            ("name_es", "Nombre (es)", "text", ""),
            ("name_en", "Nombre (en)", "text", ""),
            ("issuer", "Emisor", "text", ""),
            ("year", "Año", "text", ""),
            ("note_es", "Nota (es)", "area", ""),
            ("note_en", "Nota (en)", "area", ""),
        ],
        cv.get("certifications", []) or [],
        lambda item: {
            "name_es": (item.get("name") or {}).get("es", "")
            if isinstance(item.get("name"), dict) else str(item.get("name") or ""),
            "name_en": (item.get("name") or {}).get("en", "")
            if isinstance(item.get("name"), dict) else "",
            "issuer": item.get("issuer", ""),
            "year": item.get("year", ""),
            "note_es": _bi(item.get("note"))[0],
            "note_en": _bi(item.get("note"))[1],
        },
    )

    body = f"""
<form method="post" action="/cv">
  <div class="card">
    <div class="grid cols3">{contact_grid}</div>
  </div>

  <h2>Resumen</h2>
  <div class="grid cols2">
    {area("Resumen (es)", "summary.es", str(summary.get("es", "")), 5,
          "se usa en los CV en español")}
    {area("Resumen (en)", "summary.en", str(summary.get("en", "")), 5,
          "used by the English CVs")}
  </div>

  <h2>Experiencia</h2>
  {row_block("Puestos", "exp-rows", "exp-tpl", exp_rows, "Añadir puesto",
             "los campos es/en deben alinearse línea a línea")}
  {exp_tpl}

  <h2>Educación</h2>
  {row_block("Títulos", "edu-rows", "edu-tpl", edu_rows, "Añadir título")}
  {edu_tpl}

  <h2>Skills</h2>
  {row_block("Grupos de skills", "sgrp-rows", "sgrp-tpl", skill_rows, "Añadir grupo")}

  <h2>Proyectos (opcional)</h2>
  {row_block("Proyectos", "proj-rows", "proj-tpl", proj_rows, "Añadir proyecto")}
  {proj_tpl}

  <h2>Certificaciones (opcional)</h2>
  {row_block("Certificados", "cert-rows", "cert-tpl", cert_rows, "Añadir certificación")}
  {cert_tpl}

  <div class="actions">
    <button type="submit">Guardar CV</button>
    <span class="note">Se valida con el mismo parser que usa la CLI antes de escribir.</span>
  </div>
</form>"""
    return page("Mi CV", body, "/cv", flash=flash, error=error)


def _cv_rows(
    prefix: str,
    spec: list[tuple[str, str, str, str]],
    items: list[Any],
    extract: Any,
) -> tuple[str, str]:
    """Build rendered rows plus a <template> for JS cloning."""
    return _simple_rows(prefix, spec, items, extract)


# --------------------------------------------------------------------------- #
# Preferences form
# --------------------------------------------------------------------------- #
def prefs_form(
    search: dict[str, Any],
    profile: dict[str, Any],
    ats: dict[str, Any],
    flash: str = "",
    error: str = "",
) -> str:
    sloc_rows, sloc_tpl = _simple_rows(
        "sloc",
        [
            ("name", "Nombre (tal y como lo busca Adzuna)", "text", 'p.ej. "Spain"'),
            ("country", "País ISO-2", "text", 'para Adzuna: es, de, gb…'),
        ],
        search.get("locations", []) or [],
        lambda item: {
            "name": item.get("name", ""),
            "country": item.get("adzuna_country") or "",
        },
    )
    ploc_rows, ploc_tpl = _simple_rows(
        "ploc",
        [
            ("area", "Área", "text", 'p.ej. "Madrid (Spain)", "Remote EU"'),
            ("kind", "Tipo", "select", ""),
            ("weight", "Peso 0-100", "text", ""),
        ],
        profile.get("locations", []) or [],
        lambda item: {
            "area": item.get("area", ""),
            "kind": item.get("kind", "onsite"),
            "weight": str(item.get("weight", 50)),
        },
        select_options={"kind": list(_KINDS)},
    )

    body = f"""
<form method="post" action="/prefs">
  <div class="card">
    <div class="grid cols3">
      {num("Objetivo de ofertas", "search.target_offers",
           search.get("target_offers", 300))}
      {num("Máx. resultados por query", "search.max_results_per_query",
           search.get("max_results_per_query", 50))}
      {num("Máx. páginas por query", "search.max_pages_per_query",
           search.get("max_pages_per_query", 2))}
    </div>
    <div class="grid" style="margin-top:12px">
      {onoff("Excluir presencial/híbrido fuera de España",
             "search.exclude_foreign_onsite",
             bool(search.get("exclude_foreign_onsite", True)),
             "se mantienen 100% remoto y todo lo que esté en España")}
      <label class="f"><span class="lbl">Excluir niveles de seniority</span>
        {checks("search.exclude_seniority", list(_SENIORITY_LEVELS),
                [str(x).lower() for x in search.get("exclude_seniority", []) or []])}
        <span class="hint">estos títulos se descartan en vez de solo bajar la puntuación</span>
      </label>
    </div>
  </div>

  <h2>Ubicaciones de búsqueda</h2>
  {row_block("Adzuna busca por país", "sloc-rows", "sloc-tpl", sloc_rows,
             "Añadir ubicación")}
  {sloc_tpl}

  <h2>Tu perfil</h2>
  <div class="card">
    <div class="grid cols3">
      {select("Seniority objetivo", "profile.seniority_target",
              list(_SENIORITY_LEVELS), str(profile.get("seniority_target", "junior")))}
      {text("Idiomas", "profile.languages",
            ", ".join(profile.get("languages", ["es", "en"])),
            "separados por coma; el primero es el idioma por defecto")}
    </div>
    <label class="f" style="margin-top:12px"><span class="lbl">Empresas excluidas</span>
      <textarea name="profile.exclude_companies" rows="3">{esc(
          chr(10).join(profile.get("exclude_companies", []) or []))}</textarea>
      <span class="hint">una por línea; cualquier oferta de estas empresas se descarta</span>
    </label>
  </div>

  <h2>Ubicaciones preferidas (scoring)</h2>
  {row_block("Dónde quieres trabajar", "ploc-rows", "ploc-tpl", ploc_rows,
             "Añadir ubicación", "el peso decide cuánto puntúa la dimensión location")}
  {ploc_tpl}

  <h2>ATS (Greenhouse / Lever)</h2>
  <div class="grid cols2">
    {area("Greenhouse (slug por línea)", "ats.greenhouse",
          chr(10).join(ats.get("greenhouse", []) or []), 3,
          "boards-api.greenhouse.io/v1/boards/{slug}")}
    {area("Lever (slug por línea)", "ats.lever",
          chr(10).join(ats.get("lever", []) or []), 3,
          "api.lever.co/v0/postings/{slug}")}
  </div>

  <div class="actions">
    <button type="submit">Guardar preferencias</button>
    <span class="note">project: y scoring: del YAML no se tocan.</span>
  </div>
</form>"""
    return page("Preferencias", body, "/prefs", flash=flash, error=error)


def _field_for(
    key: str,
    label: str,
    kind: str,
    hint: str,
    value: str,
    name: str,
    options: list[str] | None = None,
) -> str:
    if kind == "select":
        return select(label, name, options or [], value)
    if kind == "area":
        return area(label, name, value, 4, hint)
    return text(label, name, value, hint)


def _simple_rows(
    prefix: str,
    spec: list[tuple[str, str, str, str]],
    items: list[Any],
    extract: Any,
    select_options: dict[str, list[str]] | None = None,
) -> tuple[str, str]:
    select_options = select_options or {}
    rows_html: list[str] = []
    for idx, item in enumerate(items):
        values = extract(item) if item else {}
        fields = "".join(
            _field_for(
                key,
                label,
                "select" if key in select_options else kind,
                hint,
                values.get(key, ""),
                f"{prefix}.{idx}.{key}",
                options=select_options.get(key, []),
            )
            for key, label, kind, hint in spec
        )
        rows_html.append(
            f'<div class="row"><div class="rowhead"><span>{prefix} #{idx + 1}</span>'
            f'<button type="button" class="ghost" onclick="jpDel(this)">Quitar</button>'
            f"</div>{fields}</div>"
        )
    tpl_fields = "".join(
        _field_for(
            key,
            label,
            "select" if key in select_options else kind,
            hint,
            "",
            f"{prefix}.__I__.{key}",
            options=select_options.get(key, []),
        )
        for key, label, kind, hint in spec
    )
    tpl = (
        f'<template id="{prefix}-tpl"><div class="row">'
        f'<div class="rowhead"><span>{prefix}</span>'
        f'<button type="button" class="ghost" onclick="jpDel(this)">Quitar</button>'
        f"</div>{tpl_fields}</div></template>"
    )
    return "".join(rows_html), tpl


# --------------------------------------------------------------------------- #
# Families
# --------------------------------------------------------------------------- #
def families_list(families: list[dict[str, Any]], flash: str = "", error: str = "") -> str:
    if not families:
        rows = '<tr><td colspan="5" class="hint">Sin familias: edita config/profile.yaml</td></tr>'
    else:
        rows = "".join(
            f'<tr><td><a href="/families/{esc(fam.get("id", ""))}">{esc(fam.get("id", ""))}</a></td>'
            f'<td>{esc(fam.get("label", ""))}</td>'
            f'<td>{esc(fam.get("interest", ""))}</td>'
            f'<td>{len(fam.get("queries", []) or [])}</td>'
            f'<td>{len(fam.get("skills", {}) or {})}</td></tr>'
            for fam in families
        )
    body = f"""
<table>
  <tr><th>id</th><th>label</th><th>interest</th><th>queries</th><th>skills</th></tr>
  {rows}
</table>"""
    return page("Familias", body, "/families", flash=flash, error=error)


def family_form(
    fam: dict[str, Any],
    flash: str = "",
    error: str = "",
) -> str:
    fam_id = str(fam.get("id", ""))
    adzuna = fam.get("adzuna_queries", {}) or {}
    queries = "\n".join(fam.get("queries", []) or [])
    sources = [str(s) for s in fam.get("sources", []) or []]

    skill_rows, skill_tpl = _simple_rows(
        "fskill",
        [
            ("name", "Keyword", "text", 'p.ej. ros, "motion planning"'),
            ("weight", "Peso", "text", "0-10"),
        ],
        [{"name": k, "weight": v} for k, v in (fam.get("skills", {}) or {}).items()],
        lambda item: {"name": item.get("name", ""), "weight": str(item.get("weight", 1))},
    )

    body = f"""
<form method="post" action="/families/{esc(fam_id)}">
  <div class="card">
    <div class="grid cols3">
      {text("Label", "family.label", str(fam.get("label", fam_id)))}
      {num("Interest", "family.interest", fam.get("interest", 10))}
      {text("Seniority hint (opcional)", "family.seniority_hint",
            str(fam.get("seniority_hint", "")),
            "empuja el score hacia ese nivel, p.ej. junior")}
    </div>
    <label class="f" style="margin-top:12px"><span class="lbl">Queries (una por línea)</span>
      <textarea name="family.queries" rows="6">{esc(queries)}</textarea>
      <span class="hint">las que usan Adzuna/remoteok/himalayas; exige al menos una</span>
    </label>
    <label class="f" style="margin-top:12px"><span class="lbl">Sources activas</span>
      {checks("family.sources", list(_FAMILY_SOURCES), sources)}
      <span class="hint">greenhouse/lever se configuran en Preferencias (ats_companies)</span>
    </label>
  </div>

  <h2>Queries de Adzuna por país</h2>
  <div class="grid cols2">
    {area("España (es)", "family.adzuna.es",
          chr(10).join(adzuna.get("es", []) or []), 5)}
    {area("Alemania (de)", "family.adzuna.de",
          chr(10).join(adzuna.get("de", []) or []), 5)}
  </div>

  <h2>Skills de la familia</h2>
  {row_block("keyword -> peso", "fskill-rows", "fskill-tpl", skill_rows, "Añadir skill")}
  {skill_tpl}

  <div class="actions">
    <button type="submit">Guardar familia</button>
    <a href="/families">← volver</a>
  </div>
</form>"""
    return page(f"Familia · {fam_id}", body, "/families", flash=flash, error=error)


def home(
    cv_path: str,
    profile_path: str,
    families_count: int,
    flash: str = "",
) -> str:
    body = f"""
<div class="grid cols2">
  <div class="card">
    <h3 style="margin-top:0">Mi CV</h3>
    <p class="hint">{esc(cv_path)}</p>
    <p>Edita contacto, resumen, experiencia, educación, skills, proyectos y
       certificaciones (es/en).</p>
    <a href="/cv">Abrir →</a>
  </div>
  <div class="card">
    <h3 style="margin-top:0">Preferencias</h3>
    <p class="hint">{esc(profile_path)}</p>
    <p>Búsqueda (objetivos, exclusiones, ubicaciones), tu perfil (seniority,
       idiomas, empresas excluidas, pesos por ubicación) y ATS.</p>
    <a href="/prefs">Abrir →</a>
  </div>
  <div class="card">
    <h3 style="margin-top:0">Familias ({families_count})</h3>
    <p class="hint">sección families del profile</p>
    <p>Queries, sources y skills por familia de búsqueda.</p>
    <a href="/families">Abrir →</a>
  </div>
  <div class="card">
    <h3 style="margin-top:0">Cómo funciona</h3>
    <p class="hint">guardar = validar + backup + escribir</p>
    <p>Cada guardado pasa por los parsers de la CLI; si algo no cuadra no se
       escribe nada. El YAML anterior queda en <code>*.bak</code> (PyYAML
       pierde los comentarios al reescribir).</p>
  </div>
</div>"""
    return page("Panel", body, "/", flash=flash)
