"""Tailored CV generation (Fase 3): offer + master CV -> markdown + PDF.

Flow: build a prompt with the resolved (bilingual) master CV and the offer
signals, ask the LLM for a strict JSON CV, validate it and render markdown and
PDF deterministically. If the LLM is unavailable or misbehaves, a heuristic
renderer falls back to the master CV with the offer as headline, so the command
always produces files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .. import storage as store
from ..config import Config, MasterCV
from ..llm import LLMError, complete_json
from ..matching.extract import extract_offer_signals
from ..matching.taxonomy import normalize_skill
from ..models import Offer
from .score import offer_from_row, pick_family

MAX_DESC = 4000

HEADINGS = {
    "es": {
        "skills": "Competencias técnicas",
        "experience": "Experiencia profesional",
        "education": "Educación",
        "projects": "Proyectos técnicos",
        "certifications": "Certificaciones y formación",
    },
    "en": {
        "skills": "Technical Skills",
        "experience": "Professional Experience",
        "education": "Education",
        "projects": "Technical Projects",
        "certifications": "Certifications & Training",
    },
}


class CVError(RuntimeError):
    """Raised for unusable model output or missing data."""


# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #
def _master_payload(master: MasterCV) -> dict[str, Any]:
    return {
        "name": master.contact.get("name", ""),
        "contact": master.contact,
        "summary": master.summary,
        "skills": master.skills,
        "experience": master.experience,
        "education": master.education,
        "projects": master.projects,
        "certifications": master.certifications,
    }


def build_prompt(offer: Offer, master: MasterCV, signals: dict, lang: str, score_row=None) -> str:
    matched = list((signals.get("skills") or {}).keys())
    offer_block = {
        "title": offer.title,
        "company": offer.company,
        "location": offer.location,
        "remote": bool(offer.remote),
        "source": offer.source,
        "description": (offer.description or "")[:MAX_DESC],
    }
    return f"""You are an expert technical CV writer tailoring ONE CV for ONE job offer.

OUTPUT LANGUAGE: "{lang}" ("es" = Spanish, "en" = English). Every human-readable
string you produce (title, summary, bullets, headings) must be in that language.

MASTER CV (source of truth - never invent employers, dates, degrees or skills):
{json.dumps(_master_payload(master), ensure_ascii=False, indent=1)}

JOB OFFER:
{json.dumps(offer_block, ensure_ascii=False, indent=1)}

SIGNALS FROM THE MATCHING ENGINE (skills already found in the offer):
{json.dumps(matched, ensure_ascii=False)}
Seniority signal: {signals.get("seniority") or "n/a"}

REQUIREMENTS
1. Output ONLY a single JSON object. No markdown fences, no commentary, no prose.
2. Schema:
{{
 "name": str,
 "title": str,           // 1-line role headline tailored to THIS offer
 "contact": {{"email": str, "phone": str, "city": str, "linkedin": str, "github": str}},
 "summary": str,         // 2-4 sentences tailored to the offer
 "sections": [
   {{"heading": str, "items": [
     {{"title": str, "subtitle": str, "date": str, "bullets": [str], "text": str}}
   ]}}
 ]
}}
3. Keep EVERY employer, school, date and degree exactly as in the MASTER CV.
   You may rewrite/reorder/translate bullets and drop irrelevant content, but
   never fabricate experience, tools or credentials.
4. Tailor: put skills/projects/bullets that match the offer first; drop the rest
   (max 3 bullets per job, max 4 skill groups, max 4 projects).
5. Section headings in the output language, usual order: skills, experience,
   education, projects, certifications.
6. "text" is used for inline items (skill groups); "bullets" for narrative items.
   Empty fields can be "".
7. Total length ~450 words (one printed page)."""


# --------------------------------------------------------------------------- #
# Heuristic fallback
# --------------------------------------------------------------------------- #
def heuristic_cv(master: MasterCV, offer: Offer, signals: dict, lang: str) -> dict:
    """Deterministic CV: master content, offer headline, matched-first skills."""
    headings = HEADINGS.get(lang, HEADINGS["en"])
    matched = {normalize_skill(str(s)) for s in (signals.get("skills") or {})}

    def group_hits(items: list) -> int:
        hits = 0
        for item in items:
            token = normalize_skill(str(item))
            if token and (token in matched or any(m in token or token in m for m in matched)):
                hits += 1
        return hits

    skill_items = sorted(
        (
            {"title": str(name), "text": ", ".join(str(i) for i in items), "bullets": [],
             "subtitle": "", "date": ""}
            for name, items in master.skills.items()
        ),
        key=lambda it: -group_hits(master.skills.get(it["title"], [])),
    )[:4]

    sections = [{"heading": headings["skills"], "items": skill_items}]

    exp_items = [
        {
            "title": str(e.get("role", "")),
            "subtitle": str(e.get("company", "")),
            "date": f"{e.get('start', '')}–{e.get('end', '')}".strip("–"),
            "bullets": [str(b) for b in e.get("bullets", [])],
            "text": "",
        }
        for e in master.experience
    ]
    sections.append({"heading": headings["experience"], "items": exp_items})

    edu_items = [
        {
            "title": str(e.get("degree", "")),
            "subtitle": str(e.get("school", "")),
            "date": f"{e.get('start', '')}–{e.get('end', '')}".strip("–"),
            "bullets": ([str(e["note"])] if e.get("note") else []),
            "text": "",
        }
        for e in master.education
    ]
    sections.append({"heading": headings["education"], "items": edu_items})

    proj_items = [
        {
            "title": str(p.get("name", "")),
            "subtitle": "",
            "date": "",
            "bullets": [],
            "text": str(p.get("description", "")),
        }
        for p in master.projects[:4]
    ]
    sections.append({"heading": headings["projects"], "items": proj_items})

    cert_items = [
        {
            "title": str(c.get("name", "")),
            "subtitle": str(c.get("issuer", "")),
            "date": str(c.get("year", "")),
            "bullets": ([str(c["note"])] if c.get("note") else []),
            "text": "",
        }
        for c in master.certifications
    ]
    sections.append({"heading": headings["certifications"], "items": cert_items})

    return {
        "name": str(master.contact.get("name", "")),
        "title": offer.title,
        "contact": {
            k: str(master.contact.get(k, ""))
            for k in ("email", "phone", "city", "linkedin", "github")
        },
        "summary": str(master.summary),
        "sections": sections,
    }


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def validate_cv(data: Any) -> dict:
    """Coerce model output into the canonical CV dict or raise CVError."""
    if not isinstance(data, dict):
        raise CVError(f"expected a JSON object, got {type(data).__name__}")
    cv = {
        "name": str(data.get("name") or "").strip(),
        "title": str(data.get("title") or "").strip(),
        "summary": str(data.get("summary") or "").strip(),
        "contact": {
            str(k): str(v)
            for k, v in (data.get("contact") or {}).items()
            if v not in (None, "")
        },
        "sections": [],
    }
    for sec in data.get("sections") or []:
        if not isinstance(sec, dict):
            continue
        items = []
        for item in sec.get("items") or []:
            if not isinstance(item, dict):
                continue
            coerced = {
                "title": str(item.get("title") or item.get("label") or "").strip(),
                "subtitle": str(item.get("subtitle") or "").strip(),
                "date": str(item.get("date") or "").strip(),
                "text": str(item.get("text") or "").strip(),
                "bullets": [str(b).strip() for b in (item.get("bullets") or []) if str(b).strip()],
            }
            if any(coerced.values()):
                items.append(coerced)
        if items:
            cv["sections"].append(
                {"heading": str(sec.get("heading") or "").strip(), "items": items}
            )
    if not cv["name"] or not cv["summary"] or not cv["sections"]:
        raise CVError("model returned an incomplete CV (need name, summary, sections)")
    return cv


# --------------------------------------------------------------------------- #
# Renderers
# --------------------------------------------------------------------------- #
def render_markdown(cv: dict) -> str:
    lines = [f"# {cv['name']}", ""]
    if cv.get("title"):
        lines += [f"**{cv['title']}**", ""]
    contact = " | ".join(str(v) for v in cv.get("contact", {}).values() if v)
    if contact:
        lines += [contact, ""]
    if cv.get("summary"):
        lines += [cv["summary"], ""]
    for sec in cv.get("sections", []):
        if sec.get("heading"):
            lines += [f"## {sec['heading']}", ""]
        for item in sec.get("items", []):
            head = " — ".join(x for x in (item.get("title"), item.get("subtitle")) if x)
            if head:
                tail = f" · {item['date']}" if item.get("date") else ""
                lines += [f"**{head}**{tail}"]
            if item.get("text"):
                lines += [item["text"]]
            for bullet in item.get("bullets", []):
                lines.append(f"- {bullet}")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def _load_font(pdf) -> str:
    """Register a Unicode TTF when available; fall back to core Helvetica."""
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]
    bold_candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ]
    for path in candidates:
        if path.exists():
            pdf.add_font("cv", "", str(path))
            bold = next((b for b in bold_candidates if b.exists()), path)
            pdf.add_font("cv", "B", str(bold))
            return "cv"
    return "helvetica"


def render_pdf(cv: dict, path: Path) -> Path:
    try:
        from fpdf import FPDF
    except ImportError as exc:  # pragma: no cover - dependency declared in pyproject
        raise CVError("fpdf2 is not installed (pip install fpdf2)") from exc

    class CVDoc(FPDF):
        pass

    pdf = CVDoc(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 12, 15)
    pdf.add_page()
    family = _load_font(pdf)
    core = family == "helvetica"

    def safe(text: str) -> str:
        if not core:
            return text
        return text.encode("cp1252", "replace").decode("cp1252")

    def w(text: str, size: float, *, bold: bool = False, color=(30, 30, 30),
          height: float = 5.0, align: str = "L") -> None:
        pdf.set_font(family, "B" if bold else "", size)
        pdf.set_text_color(*color)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin, height, safe(text), align=align)

    w(cv["name"], 17, bold=True, height=7)
    if cv.get("title"):
        w(cv["title"], 11, color=(70, 70, 70), height=5.5)
    contact = " | ".join(str(v) for v in cv.get("contact", {}).values() if v)
    if contact:
        w(contact, 9, color=(110, 110, 110), height=5)
    pdf.ln(1)
    if cv.get("summary"):
        w(cv["summary"], 9.5, color=(40, 40, 40), height=4.8)
        pdf.ln(1)

    for sec in cv.get("sections", []):
        heading = sec.get("heading")
        if not heading:
            continue
        pdf.ln(1.5)
        pdf.set_font(family, "B", 11.5)
        pdf.set_text_color(20, 60, 120)
        pdf.cell(0, 6, safe(heading), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(20, 60, 120)
        pdf.set_line_width(0.3)
        y = pdf.get_y()
        pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
        pdf.ln(1.5)
        for item in sec.get("items", []):
            head = " — ".join(x for x in (item.get("title"), item.get("subtitle")) if x)
            if head:
                pdf.set_font(family, "B", 10)
                pdf.set_text_color(30, 30, 30)
                label = head + (f"   ({item['date']})" if item.get("date") else "")
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin, 5, safe(label))
            if item.get("text"):
                pdf.set_font(family, "", 9.5)
                pdf.set_text_color(50, 50, 50)
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin, 4.7, safe(item["text"]))
            if item.get("bullets"):
                pdf.set_font(family, "", 9.5)
                pdf.set_text_color(50, 50, 50)
                for bullet in item["bullets"]:
                    x0 = pdf.l_margin + 3
                    pdf.set_x(x0)
                    pdf.multi_cell(pdf.w - pdf.r_margin - x0, 4.7, safe(f"-  {bullet}"))
            pdf.ln(0.6)
        pdf.ln(0.6)

    pdf.output(str(path))
    return Path(path)


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def _latest_score_row(conn, offer_id: int):
    return conn.execute(
        "SELECT * FROM offer_scores WHERE offer_id = ? ORDER BY run_id DESC LIMIT 1",
        (offer_id,),
    ).fetchone()


def _signals_for(offer: Offer, family_id: str, config: Config, score_row) -> dict:
    if score_row and score_row["extracted"]:
        try:
            return json.loads(score_row["extracted"])
        except ValueError:
            pass
    try:
        family = config.family(family_id)
    except Exception:
        return {}
    return extract_offer_signals(offer, family, config)


def generate_cv(
    config: Config,
    conn,
    offer_id: int,
    *,
    lang: str | None = None,
    family_filter: str | None = None,
    use_llm: bool = True,
    model: str | None = None,
    to_pdf: bool = True,
    out_dir: Path | None = None,
    timeout: float = 300.0,
) -> dict:
    """Generate a tailored CV for ``offer_id``; returns cv, markdown, files, meta."""
    row = store.get_offer(conn, offer_id)
    if row is None:
        raise CVError(f"offer {offer_id} not found")
    offer = offer_from_row(row)
    lang = lang or (config.profile.languages[0] if config.profile.languages else "es")
    family_id = pick_family(config, offer, family_filter)
    score_row = _latest_score_row(conn, offer_id)
    signals = _signals_for(offer, family_id, config, score_row)
    master = config.master(lang)

    meta: dict[str, Any] = {
        "offer_id": offer_id,
        "lang": lang,
        "family": family_id,
        "backend": "llm",
        "fallback": None,
        "score": score_row["score"] if score_row else None,
        "triage": score_row["triage"] if score_row else None,
    }

    cv: dict | None = None
    if use_llm:
        try:
            prompt = build_prompt(offer, master, signals, lang, score_row)
            cv = validate_cv(complete_json(prompt, model=model, timeout=timeout))
        except (LLMError, CVError) as exc:
            meta["fallback"] = str(exc)
    if cv is None:
        meta["backend"] = "heuristic"
        cv = heuristic_cv(master, offer, signals, lang)

    markdown = render_markdown(cv)
    out = Path(out_dir if out_dir is not None else config.output_dir) / "cv"
    out.mkdir(parents=True, exist_ok=True)
    md_path = out / f"cv_{offer_id}_{lang}.md"
    md_path.write_text(markdown, encoding="utf-8")
    files = {"md": str(md_path)}

    if to_pdf:
        try:
            pdf_path = render_pdf(cv, out / f"cv_{offer_id}_{lang}.pdf")
            files["pdf"] = str(pdf_path)
        except CVError as exc:
            meta["pdf_error"] = str(exc)

    store.save_cv_variant(conn, family_id, markdown, offer.title)
    return {"cv": cv, "markdown": markdown, "files": files, "meta": meta}
