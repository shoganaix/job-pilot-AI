# Job Pilot AI 
# [ENGLISH]
Personal AI-powered job application agent (CLI + SQLite). Searches for job opportunities across free sources, ranks them using a matching engine (0–100), generates a tailored CV for each position, and manages an application queue.

[![CI](https://github.com/shoganaix/job-pilot-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/shoganaix/job-pilot-AI/actions/workflows/ci.yml)

> Designed as a Python/CLI programming portfolio project, not as a commercial product. The job search engine relies on free APIs (keyless or with free API keys).

## Features

| Command | Description |
|---|---|
| `jobpilot init` | Initializes the project structure (configuration, data directories, SQLite schema) |
| `jobpilot setup` | Guided first-time setup: writes your profile and master CV without editing YAML |
| `jobpilot doctor` | Diagnoses why results are empty, thin or wrong, and tells you how to fix it |
| `jobpilot family [list\|add\|edit\|rm]` | Manages job families interactively, preserving your YAML comments |
| `jobpilot tutorial` | Step-by-step tour of the whole workflow |
| `jobpilot plan` | Displays a summary of your configuration: job families, queries, and sources |
| `jobpilot sources` | Tests connectivity to the configured job sources |
| `jobpilot sync` | Fetches job listings based on each family's search queries |
| `jobpilot score [--family X --limit N]` | Scores stored job listings (0–100) and classifies them |
| `jobpilot offers [--family X]` | Lists saved job opportunities and their corresponding families |
| `jobpilot query <text>` | Searches through previously stored job listings |
| `jobpilot queue set <id> --status apply` | Adds a job opportunity to your application queue |
| `jobpilot open <id>` | Opens the job listing URL in your browser |
| `jobpilot cv <id>` | Generates the tailored CV (markdown + PDF) into `output/cv/` |
| `jobpilot cv list` | Lists the CVs already generated, with size and generation date |
| `jobpilot report` | Generates the HTML dashboard (`output/report.html`) |

> `jobpilot cv <id>` takes the offer id from `jobpilot offers`. Both forms are valid: `jobpilot cv 42` and `jobpilot cv list`.

### Scoring and triage

- **apply** → Score ≥ 65 (and minimum skill relevance met) → Recommended for application.
- **review** → Score ≥ 45 → Requires manual review.
- **discard** → Score < 45 or fails hard filters (US citizenship, security clearance, excluded company).

## Job source portals

Every board is fetched through one `JobSource` adapter per source (see `src/jobpilot/sources/`); adding a portal means writing one adapter and registering it.

| Portal | Adapter | Key | Coverage |
|---|---|---|---|
| Adzuna | `adzuna.py` | Free App ID/Key | EU/ES aggregator; short excerpts only |
| InfoJobs (retired) | `infogobs.py` | n/a | Official API unavailable; adapter kept but unused |
| Arbeitnow | `arbeitnow.py` | Keyless | European remote-first feed, full descriptions |
| RemoteOK | `remoteok.py` | Keyless | Global remote tech board |
| Himalayas | `himalayas.py` | Keyless | Remote jobs, structured salary/seniority |
| Greenhouse (ATS) | `ats_boards.py` | Keyless | Target-company boards |
| Lever (ATS) | `ats_boards.py` | Keyless | Target-company postings |
| Teamtailor (ATS) | `ats_boards.py` | Keyless | Target-company boards (e.g. Sateliot, ARQUIMEA) |
| Personio (ATS) | `ats_boards.py` | Keyless | Target-company boards (e.g. Alén Space) |
| Ashby (ATS) | `ats_boards.py` | Keyless | Target-company boards |
| Workable (ATS) | `ats_boards.py` | Keyless | Target-company boards |
| SmartRecruiters (ATS) | `ats_boards.py` | Keyless | Target-company postings |
| Workday CXS (ATS) | `ats_boards.py` | Keyless | Target-company boards (e.g. Airbus, Thales Alenia Space); country facet + per-posting detail |
| Cornerstone CSOD (ATS) | `ats_boards.py` | Keyless | Target-company career sites (e.g. GMV); ephemeral bearer token read from `csod.context` |
| ESA | `space_boards.py` | Keyless | European Space Agency careers (SuccessFactors) |
| SatCen | `space_boards.py` | Keyless | EU Satellite Centre vacancies |
| UARX Space | `space_boards.py` | Keyless | UARX careers (Spain) |
| SATLANTIS | `space_boards.py` | Keyless | SATLANTIS careers (Spain) |
| EUSPA | `space_boards.py` | Keyless | EU Agency for the Space Programme vacancies (open only) |
| PLD Space | `space_boards.py` | Keyless | PLD Space careers, Spain + Kourou (needs the OS trust store) |
| Pangea Propulsion | `space_boards.py` | Keyless | Factorial board: sitemap + full descriptions and salary |
| Indra Space | `space_boards.py` | Keyless | Space unit of Indra, isolated from the group sitemap |
| Space-Careers | `space_portals.py` | Keyless | International space-industry board |
| Find a Space Job | `space_portals.py` | Keyless | International space board |
| Space Career Launchpad | `space_portals.py` | Keyless | Starseu SmartJobBoard |
| EURAXESS | `space_portals.py` | Keyless | Generic research board (noisy, opt-in) |
| USAJOBS / NASA | `usajobs.py` | Free key | US federal jobs (NASA) |

### InfoJobs (retired: official API unavailable)

InfoJobs' official REST API (`api.infojobs.net`, credentials from `developer.infojobs.net`) is **not available**, so the source is disabled: no family in `config/profile.yaml` lists `infogobs` any more and no credentials are needed. The adapter `sources/infojobs.py` and its registry entry are kept intact, so the source can be re-enabled without code changes if the API ever comes back. Set `INFOJOBS_CLIENT_ID`/`INFOJOBS_CLIENT_SECRET` in `.env` and add `infogobs` back to a family's `sources` to reactivate it.

### LinkedIn (not feasible for free, not included)

There is **no free public LinkedIn jobs API**. The official routes (Marketing Developer platform, Talent Solutions) are partner-approved and aimed at companies; the remaining options are paid third-party APIs (e.g. credit plans at ~$45/month) or unofficial scrapers that violate the ToS and risk account bans. That conflicts with this project's keyless/free-key approach, so LinkedIn is intentionally left out. A future optional adapter could be enabled only if a paid provider key is ever added.

## Requirements

- Python 3.12+ (tested on Python 3.14).
- Internet connection for job synchronization (all sources are keyless except Adzuna and USAJOBS).

## Installation

```bash
git clone https://github.com/shoganaix/job-pilot-AI.git
cd job-pilot-AI
python -m venv .venv
.venv\Scripts\activate        # Windows (PowerShell)
pip install -e ".[dev]"       # Installs the jobpilot CLI + ruff + pytest

jobpilot init
```

The `init` command generates the `config/` and `data/` directories, plus a
placeholder `config/master_cv.yaml` (generated from code, so it is always
available) and a `.env` from the packaged template. It never overwrites an
existing file.

Everything lives under one "home" directory: the repository checkout when you run
from a clone, otherwise `$JOBSOURCE_HOME`, otherwise your home directory. Set it
explicitly to keep several independent setups (e.g. a private search and a
portfolio one):

```bash
JOBSOURCE_HOME=D:\jobpilot jobpilot init
```

Copy `.env.example` to `.env` and add your API credentials:

```env
ADZUNA_APP_ID=
ADZUNA_APP_KEY=

USAJOBS_API_KEY=         # free at developer.usajobs.gov/apirequest (NASA)
USAJOBS_EMAIL=           # the e-mail you registered with
USAJOBS_ORGANIZATION=NN  # optional, defaults to NN (NASA); empty = all federal
```

Two optional knobs tune the shared HTTP client used by the keyless sources
(`remoteok`, `arbeitnow`, `himalayas`, the ATS boards, …):

| Variable | Default | Effect |
|---|---|---|
| `JOBSOURCE_TIMEOUT_SECONDS` | `30` | Per-request timeout. Raise it for slow ATS boards, lower it to fail over to the next source faster. |
| `JOBSOURCE_USER_AGENT` | `jobpilot/0.1 (personal job application agent)` | `User-Agent` sent by those adapters. Please keep a contact string; some boards rate-limit anonymous agents. |

Adzuna remains disabled until valid credentials are provided in `.env`; USAJOBS only enables the `usajobs` custom source. InfoJobs needs no credentials because it is retired (its official API is unavailable) — `INFOJOBS_CLIENT_ID` / `INFOJOBS_CLIENT_SECRET` are not read by any code path and are listed as commented-out lines in `.env.example` only to explain why.

> `.env` is gitignored, **`.env.example` is not**. Never paste a real key into `.env.example`: it is committed. If you ever did, rotate the key — removing it from the file does not remove it from the Git history.

Adzuna is the only source with a rate limit of 25 requests/minute and 250 requests/day. The agent spaces its calls, stops cleanly once the daily budget is spent (exceeding it locks the key) and retries `429`/`5xx` with backoff.

Adzuna posts largely local-language roles, so each family can declare `adzuna_queries` (per-country keyword sets, e.g. `es:` Spanish terms) — see `config/profile.yaml`. Offers are filtered at ingestion to drop clearly non-technical categories.

## Quick Configuration

If you do not want to touch YAML at all, run **`jobpilot setup`** (see below). Otherwise all settings are managed through YAML files, without modifying the source code.

### Guided setup: `jobpilot setup`

A terminal wizard for people who should not have to learn a config format. It asks for your contact details, years of experience, current role, target profession, search phrases, skill weights, target seniority and countries, then writes `config/profile.yaml` and `config/master_cv.yaml` for you.

- Typing a profession such as `pilotos`, `software`, `enfermería`, `docencia` or `ventas` offers a starting point you can edit. It is only a suggestion: every value is yours to change.
- It pre-fills your master CV with your data and the skill groups of your families, so the only thing left to write is your own history.
- If `config/profile.yaml` already exists, it asks before overwriting and keeps a `profile.yaml.bak` copy.
- Everything it writes is ordinary YAML. It never invents achievements: the example bullets stay marked as placeholders, because scoring against a fictional CV produces meaningless numbers.

### Diagnostics: `jobpilot doctor`

Checks the things that silently produce empty or wrong results, and prints what to do about each:

- `config/profile.yaml` parses, and scoring weights sum to ~100.
- `ADZUNA_APP_KEY` is present in `.env` (otherwise the keyed sources stay disabled).
- The master CV has skills and experience — an empty one makes the `skills` dimension score ~0, so nothing ever reaches `apply`.
- **`exclude_foreign_onsite: true` together with an on-site profession.** This is the mistake that costs the most: pilots, nurses, teachers or chefs with that flag on have almost every posting discarded, and the reason is not obvious from the results.
- Families with no skills (always discarded), too few skills, or no queries (nothing is ever searched).

### Changing your searches: `jobpilot family`

- `jobpilot family list` — table of families with their skill and query counts.
- `jobpilot family add` — interactive creation of a new family.
- `jobpilot family edit <id>` — change label, queries and skills (empty input keeps the current value).
- `jobpilot family rm <id>` — delete one family, after confirmation.

These edit the YAML **surgically**: only the affected list item is rewritten, so your comments, the rest of the file and every other family are preserved byte for byte. A full load-and-dump would silently delete the notes explaining your weights.

### Guided tour: `jobpilot tutorial`

Prints the seven steps from an empty install to a tracked application, marking the ones you have already completed.

### `config/profile.yaml`

- **`search`** — Search locations (`adzuna_country`), `target_offers`, and per-query limits.
- **`search.exclude_foreign_onsite`** — when `true` (default), hybrid/on-site postings **outside Spain** are dropped at ingestion and scoring (you cannot relocate!); 100 % remote roles from any country and any posting in Spain are kept. Set `false` for hybrid/on-site in the UK/Germany too.
- **`families`** — Groups your target job roles. Each family includes:
  - `queries`: Search phrases sent to each job source.
  - `sources`: `adzuna, arbeitnow, remoteok, himalayas` (+ ATS boards).
  - `skills`: A `skill → weight (1–10)` mapping used to calculate skill relevance.
  - `interest`: Editorial interest score (0–10), used as a scoring dimension.
- **`scoring`** — `threshold` (apply), `review_threshold`, and the weights of the seven scoring dimensions (`skills, experience, education, location, seniority, interest, industry`), which must sum to 100. A typo in a dimension name, or weights that drift away from 100, is rejected at load time instead of silently rescaling every score.
- **`profile`** — `seniority_target`, `languages`, location preferences (area + weight), and `exclude_companies`.
  - `seniority_target` — one of the levels in `profile.seniority_levels` (default: `junior`, `midlevel`, `senior`, `lead`, `entry`). Offers are scored by their distance to the target (`100 - |target − offer|`), so you can point the same engine at a different profession or career stage without code changes. An unknown level is rejected at load time.
  - `seniority_levels` — the vocabulary used to read seniority out of a job description. It defaults to the list above; extend or replace it to describe your own field.
  - `education_levels` — the same idea for qualifications, with the same defaults.
  - `hard_filters` — requirements a posting must satisfy to be scored at all: `regex` (a pattern that must appear in the description) and `min_education_level` (the weakest level you will accept). Set `enabled: false` to switch a filter off without deleting it.
- **Not robotics-specific.** The engine has no built-in assumption about space, aerospace or engineering. The shipped families are an example; add, edit or replace them with `jobpilot family` or by hand, and the same scoring, filtering and CV-tailoring code works for pilots, nurses, teachers, chefs or sales roles.
- **`search.max_pages_by_source`** — Optional per-source page ceiling (e.g. `csod: 3`). It takes precedence over `max_pages_per_query` for that source, and the `--max-pages` CLI flag overrides both.
- **`ats_companies`** — Company slugs per ATS platform (greenhouse, lever, teamtailor, personio, ashby, workable, smartrecruiters, workday, csod), for keyless access to each employer's own board. Teamtailor slugs are the full host (`sateliot.com`); the rest are board slugs. `workday` and `csod` are keyed APIs, so each entry is a mapping with the board coordinates (`host`/`tenant`/`site`, or `portal_url`/`career_site_id`) plus an optional `variant`, which lets the same company appear twice — e.g. `country: ES` and a second `search_text: remote` with `remote_only: true`.
- **`custom_sources`** — Explicit adapters for single-organisation boards (`esa`, `satcen`, `uarx`, `satlantis`, `euspa`, `pld`, `pangea`, `indra_space`, `space_careers`, `find_a_space_job`, `scl`, `euraxess`, `usajobs`).

### `config/master_cv.yaml`

Your master CV, used by the scoring engine to determine which skills you already possess and by Phase 3 to generate tailored CVs.

The master CV is bilingual (**es/en**): narrative fields are stored as `{es: ..., en: ...}`, and `Config.master(lang)` resolves them deterministically.

- `contact` — Always language-neutral.
- `summary`, `experience`, `education`, `projects`, `certifications` — Support `{es, en}` dictionaries for individual fields.
- `education` — Contains only actual university degree qualifications. Other qualifications (microdegrees, ongoing training, and certifications) belong in `certifications`.
- `skills` — Groups of technologies and technical competencies. Any group whose name contains `camino` (e.g., `En camino (robótica/embedded)`) is assigned a 0.5 factor in the scoring engine. This allows you to highlight skills you are currently developing without presenting them as established professional experience.

## Personal Configuration

The README describes the configuration pattern rather than individual user settings. Each user can customize the following:

1. **Search queries and job families** in `profile.yaml` → `families`. Add or remove `queries` to cover approximately 20 target roles, and assign skill weights based on their requirements.
2. **Scoring** → Increase `threshold` to reduce irrelevant results, or adjust `weights` (e.g., increase `location` if you are only interested in remote positions within your country).
3. **Your technical stack** in `master_cv.yaml` → `skills`. Place technologies you genuinely master in standard skill groups, and technologies you are currently learning in an `En camino (...)` group.
4. **Location preferences** → `profile.locations`: Define each `area` with its corresponding `weight`. Job listings are scored against the best matching location preference (onsite in Spain, Remote EU, etc.).
5. **Excluded companies and eligibility filters** → Configure `profile.exclude_companies`. Positions requiring US citizenship, security clearance, or candidates to be located in the US are automatically discarded.

## Bilingual Support (ES/EN)

The master CV is bilingual by design.

Example:

```python
from jobpilot.config import load_config

config = load_config()
cv_en = config.master("en")   # All narrative fields resolved to English
cv_es = config.master("es")   # All narrative fields resolved to Spanish (default)
```

The generated CV language is determined by `languages[0]` unless explicitly overridden with `--lang`.

## Tailored CV (`jobpilot cv`)

Writes an offer-specific CV to `output/cv/cv_<id>_<lang>.md` and
`output/cv/cv_<id>_<lang>.pdf`:

- **LLM backend** (default): builds a prompt from your `master_cv` plus the offer
  description and drafts the CV through `opencode run --format json`
  (`complete_json`). If it fails, it falls back to the heuristic backend.
- **Heuristic backend** (`--no-llm`): reorders your `skills` by the ones the offer
  actually asks for (`En camino` groups at half weight) and surfaces the closest
  experience, without inventing content.
- `--lang es|en` forces the language; `--show` prints the markdown; `--no-pdf` skips
  the PDF; `--family X` restricts the skill set to that family.
- `jobpilot cv list` lists what you have already generated (id, language, size, date),
  so you do not have to remember the naming scheme or walk `output/cv/` by hand.

## Application queue (2.0)

`jobpilot queue` tracks each application with `created_at`, `applied_on` (stamped automatically when a job moves to `applied`), how long it has been in its current status and a suggested next step per status. Filter the board with `--status X`. Notes and the attached CV survive a status change: an empty `--notes` means "unchanged", not "clear it".

## Sync resilience and deduplication

`jobpilot sync` is designed so that one broken portal cannot waste the whole run:

- **Every source is isolated.** Each adapter call goes through a guard that catches
  timeouts, HTTP errors, rate limits (429) and malformed payloads. A failing source is
  recorded as blocked in the run stats and the sync continues with the next one.
- **Per-source daily quotas** are read from the database before each call, so a
  repeated sync cannot burn a source's quota.
- **Retries with exponential backoff** apply to transient failures only.
- **One run row per sync** records inserted/updated/duplicate counts per source, so a
  bad run is diagnosable after the fact.
- `Ctrl+C` (or `Esc` on the spinner) stops after the current batch and still finalises
  the run row, so the data committed so far is not lost.

**Cross-source duplicates.** Offers are fingerprinted by `source + source_id` for the
per-source upsert, plus a content hash (title + company + location) so the same
posting syndicated on two boards is stored once.

The exact hash is deliberately conservative: it does *not* merge "Sr. Python
Developer" with "Senior Python Developer", because guessing wrong silently drops a
real offer. When you want the tighter result, opt in per run:

```bash
jobpilot sync --relaxed-dedupe
```

`--relaxed-dedupe` additionally collapses postings whose titles differ only in
wording: it expands abbreviations (`Sr.` → `senior`), drops parentheticals
(`(m/f/d)`), ignores token order and location wording, and **requires the
descriptions to also match** before merging. Both conditions must hold, so a
genuinely different role is kept. The trade-off, in one line: fewer duplicates, but a
wrongly merged pair means a lost offer — so it stays off by default. Offers that
already existed in the database keep their original relaxed key until they are seen
again; a one-off re-sync is enough to backfill them.

## Scoring calibration

The **skills dimension** rewards how much of the offer's *asked* skills you cover, and normalizes short postings instead of crushing them: an offer citing only 2-3 skills of the family domain is no longer penalized for the tiny share it represents. Tune the gate keepers in `profile.yaml` → `scoring` (`threshold`, `min_skills_for_apply`, `weights`).

## HTML Dashboard

`jobpilot report` renders a self-contained `output/report.html` (no external assets) with KPI cards, the application queue, the latest scoring run, a score breakdown for the top offers and a per-family summary. Use `--open` to view it in your browser, or `--family X` to filter the scoring tables.

## Development

Run linting and tests:

```bash
.\.venv\Scripts\ruff.exe check src tests
.\.venv\Scripts\python.exe -m pytest
```

Coverage and type checks (neither blocks a merge today):

```bash
.\.venv\Scripts\python.exe -m pytest --cov=jobpilot --cov-report=term --cov-report=xml
.\.venv\Scripts\python.exe -m mypy src/jobpilot --ignore-missing-imports
```

- **CI** runs on Python 3.11, 3.12, 3.13 and 3.14 (`.github/workflows/ci.yml`).
- **mypy** is *advisory*: the job is `continue-on-error` so new type findings never block a PR. The package ships `py.typed`.
- **Coverage** is reported (currently ~72%) and floored at 70% via `fail_under` in `pyproject.toml`.

### Project Structure

```text
src/jobpilot/
  cli.py            # CLI (argparse + rich): all commands, incl. `cv list`
  config.py         # YAML loader + bilingual resolver (MasterCV.in_lang) + validation
  wizard.py         # Guided setup, doctor, family editor, tutorial
  yaml_edit.py      # Comment-preserving YAML block editing (used by wizard.py)
  dedupe.py         # Cross-source fingerprints: exact + opt-in relaxed matching
  llm.py            # Optional LLM client for CV tailoring (falls back to the template engine)
  models.py         # Data types: Offer, SourcePage, Triage...
  storage.py        # SQLite (upsert, deduplication, offers, scores, schema migrations)
  py.typed          # PEP 561 marker
  resources/
    profile.yaml    # Shipped default profile (copied to config/ on first run)
  sources/          # One JobSource adapter per board
    base.py         # HTTP plumbing, retry/backoff, quotas, guarded fetching
    registry.py     # Builds the enabled adapters from the profile
    adzuna.py  arbeitnow.py  remoteok.py  himalayas.py
    ats_boards.py   # Greenhouse, Lever, Teamtailor, Personio, Ashby, Workable,
                    #   SmartRecruiters, Workday CXS, Cornerstone CSOD
    space_boards.py # ESA careers
    space_portals.py# Company-specific space career portals
    usajobs.py      # US federal jobs (filtered out by the default hard filters)
    infojobs.py     # Retired: the official InfoJobs API is unavailable
  pipeline/         # search.py (sync), score.py, cv.py, report.py
  matching/         # taxonomy.py (aliases), extract.py, industry.py, scoring.py
```

## Privacy
- ``.env`` (API keys), ``data/`` (your job listings), ``output/`` (generated CVs),
  ``config/profile.yaml`` and ``config/master_cv.yaml`` are all in ``.gitignore``:
  they are **not** committed.
- Keep the repository private if your local SQLite database or CVs were ever
  committed before this rule existed — removing a file from the index does not
  remove it from the Git history. Rotate any key that was ever pushed.
- Everything the tool needs to run lives in your home directory (or the
  checkout), so a fork is safe to publish.

## Security notes
The job descriptions this tool reads are third-party, attacker-controlled text,
so they are treated as data, never as instructions:

- **Credentials**: Adzuna authenticates with an `Authorization: Basic` header
  instead of query parameters, and every error message, run statistic and log
  line is passed through a redactor, so a key cannot end up in `runs.stats` or in
  the run manifest. The LLM subprocess also receives a minimal environment: the
  job-board API keys are not inherited.
- **Prompt injection**: the offer is wrapped in explicit
  `UNTRUSTED ... DATA` delimiters, and — the part that actually enforces it —
  the returned CV is checked against your master CV. A name, e-mail, employer or
  degree that is not in the master aborts the tailored CV and falls back to the
  heuristic renderer, so a hostile posting cannot rewrite your identity.
- **HTML report**: all text is escaped and every link goes through a scheme
  allowlist (`http`, `https`, `mailto`, `file`), so a stored `javascript:` URL
  from a scraped offer is rendered as plain text instead of a live link.
- **Network**: `429` and `5xx` are retried with exponential backoff honouring
  `Retry-After`; other `4xx` are not retried, because retrying them only burns
  quota. Sources with a free daily cap (Adzuna) stop cleanly once the budget is
  spent.
  
# [ESPAÑOL]

Agente personal de aplicación de empleo (CLI + SQLite). Busca ofertas en fuentes
gratuitas, las puntúa con un motor de matching (0-100), genera un CV tailorizado
por oferta y mantiene una cola de aplicaciones.

> Diseñado como portafolio de programación (Python/CLI), no como un producto
> comercial. El motor de búsqueda usa APIs sin coste (keyless o con clave gratuita).

## Qué hace
<img width="519" height="175" alt="image" src="https://github.com/user-attachments/assets/0f178ab6-b5cd-45a1-b7c9-fe6d0db865b7" />

| Comando | Qué hace |
|---|---|
| `jobpilot init` | Crea el esqueleto (config, datos, esquema SQLite) |
| `jobpilot setup` | Configuración guiada: escribe tu perfil y CV maestro sin editar YAML |
| `jobpilot doctor` | Diagnostica por qué los resultados salen vacíos, pobres o mal, y cómo arreglarlo |
| `jobpilot family [list\|add\|edit\|rm]` | Gestiona familias interactivamente, conservando tus comentarios del YAML |
| `jobpilot tutorial` | Recorrido paso a paso del flujo completo |
| `jobpilot plan` | Resumen de tu configuración: familias, queries, fuentes |
| `jobpilot sources` | Test de conectividad de las fuentes configuradas |
| `jobpilot sync` | Descarga ofertas según las queries de cada familia |
| `jobpilot score [--family X --limit N]` | Puntúa las ofertas almacenadas (0-100) y las clasifica |
| `jobpilot offers [--family X]` | Lista ofertas guardadas con su familia |
| `jobpilot query <text>` | Busca ofertas ya guardadas |
| `jobpilot queue set <id> --status apply` | Añade una oferta a tu cola de aplicaciones |
| `jobpilot open <id>` | Abre la URL de la oferta en el navegador |
| `jobpilot cv <id>` | Genera el CV tailorizado (markdown + PDF) en `output/cv/` |
| `jobpilot cv list` | Lista los CVs ya generados, con tamaño y fecha |
| `jobpilot report` | Genera el dashboard HTML (`output/report.html`) |

> `jobpilot cv <id>` toma el id de `jobpilot offers`. Ambas formas son válidas: `jobpilot cv 42` y `jobpilot cv list`.

Triage del scoring:
- **apply** → score ≥ 65 (y relevancia de skills mínima) → aplicar.
- **review** → score ≥ 45 → revisar manualmente.
- **discard** → score < 45 o incumple filtros duros (ciudadanía US, clearance, empresa excluida).

## Portales de búsqueda / fuentes

Cada bolsa se consulta mediante un adaptador `JobSource` por fuente (en `src/jobpilot/sources/`); añadir un portal es escribir un adaptador y registrarlo.

| Portal | Adaptador | Clave | Cobertura |
|---|---|---|---|
| Adzuna | `adzuna.py` | App ID/Key gratis | Agregador EU/ES; solo extractos |
| InfoJobs (retirada) | `infogobs.py` | n/d | API oficial no disponible; se conserva el adaptador |
| Arbeitnow | `arbeitnow.py` | Keyless | Feed europeo remote-first, descripción completa |
| RemoteOK | `remoteok.py` | Keyless | Bolsa remota global tech |
| Himalayas | `himalayas.py` | Keyless | Remoto, salario/seniority estructurados |
| Greenhouse (ATS) | `ats_boards.py` | Keyless | Empresas objetivo |
| Lever (ATS) | `ats_boards.py` | Keyless | Ofertas de empresas objetivo |
| Teamtailor (ATS) | `ats_boards.py` | Keyless | Boards de empresas objetivo (Sateliot, ARQUIMEA) |
| Personio (ATS) | `ats_boards.py` | Keyless | Boards de empresas objetivo (Alén Space) |
| Ashby (ATS) | `ats_boards.py` | Keyless | Boards de empresas objetivo |
| Workable (ATS) | `ats_boards.py` | Keyless | Boards de empresas objetivo |
| SmartRecruiters (ATS) | `ats_boards.py` | Keyless | Ofertas de empresas objetivo |
| Workday CXS (ATS) | `ats_boards.py` | Keyless | Boards de empresas objetivo (Airbus, Thales Alenia Space); facet de país + detalle por oferta |
| Cornerstone CSOD (ATS) | `ats_boards.py` | Keyless | Career sites de empresas objetivo (GMV); token efímero leído de `csod.context` |
| ESA | `space_boards.py` | Keyless | Empleo en la Agencia Espacial Europea (SuccessFactors) |
| SatCen | `space_boards.py` | Keyless | Vacantes del Centro Satelital de la UE |
| UARX Space | `space_boards.py` | Keyless | Empleo en UARX (España) |
| SATLANTIS | `space_boards.py` | Keyless | Empleo en SATLANTIS (España) |
| EUSPA | `space_boards.py` | Keyless | Vacantes de la Agencia de la UE para el Programa Espacial (solo abiertas) |
| PLD Space | `space_boards.py` | Keyless | Empleo en PLD Space, España y Kourou (requiere el almacén de CA del sistema) |
| Pangea Propulsion | `space_boards.py` | Keyless | Board Factorial: sitemap + descripción completa y salario |
| Indra Space | `space_boards.py` | Keyless | Unidad espacial de Indra, aislada del sitemap del grupo |
| Space-Careers | `space_portals.py` | Keyless | Bolsa internacional del sector espacial |
| Find a Space Job | `space_portals.py` | Keyless | Bolsa espacial internacional |
| Space Career Launchpad | `space_portals.py` | Keyless | Starseu SmartJobBoard |
| EURAXESS | `space_portals.py` | Keyless | Bolsa de investigación genérica (ruidosa, opt-in) |
| USAJOBS / NASA | `usajobs.py` | Clave gratis | Empleo federal USA (NASA) |

### InfoJobs (retirada: API oficial no disponible)

La API REST oficial de InfoJobs (`api.infojobs.net`, credenciales en `developer.infojobs.net`) **no está disponible**, así que la fuente queda desactivada: ninguna familia de `config/profile.yaml` lista ya `infogobs` y no hacen falta credenciales. El adaptador `sources/infojobs.py` y su entrada en el registro se conservan intactos, de modo que la fuente puede volver a activarse sin tocar código si la API regresara. Para reactivarla, define `INFOJOBS_CLIENT_ID`/`INFOJOBS_CLIENT_SECRET` en `.env` y vuelve a añadir `infogobs` al campo `sources` de una familia.

### LinkedIn (no factible gratis, no incluida)

No existe una **API pública gratuita de ofertas de LinkedIn**. Las vías oficiales (Marketing Developer platform, Talent Solutions) requieren aprobación como partner y están orientadas a empresas; el resto son APIs de terceros de pago (p. ej. planes de crédito ~45 $/mes) o scrapers no oficiales que incumplen los términos de uso y arriesgan el baneo de la cuenta. Eso choca con el enfoque del proyecto (keyless o clave gratuita), así que LinkedIn queda fuera a propósito. Si algún día se añadiera una clave de un proveedor de pago, podría habilitarse un adaptador opcional.

## Requisitos

- Python 3.12+ (probado en 3.14).
- Conexión a internet para el sync (excepto Adzuna y USAJOBS, todas las fuentes son keyless).

## Instalación

```bash
git clone https://github.com/shoganaix/job-pilot-AI.git
cd job-pilot-AI
python -m venv .venv
.venv\Scripts\activate        # Windows (PowerShell)
pip install -e ".[dev]"       # instala el CLI jobpilot + ruff + pytest

jobpilot init
```

`init` genera `config/` y `data/`, un `config/master_cv.yaml` de ejemplo (generado
por código, así que siempre está disponible) y un `.env` desde la plantilla
empaquetada. Nunca sobrescribe un fichero existente.

Todo vive bajo un único directorio "home": el checkout del repo si ejecutas desde
un clon, si no `$JOBSOURCE_HOME`, si no tu directorio home. Fíjalalo para mantener
montajes independientes (p. ej. una búsqueda privada y otra de portafolio):

```bash
JOBSOURCE_HOME=D:\jobpilot jobpilot init
```

`init` también crea el `.env`; rellena las claves que uses:

```
ADZUNA_APP_ID=
ADZUNA_APP_KEY=

USAJOBS_API_KEY=         # gratis en developer.usajobs.gov/apirequest (NASA)
USAJOBS_EMAIL=           # el e-mail con el que te registraste
USAJOBS_ORGANIZATION=NN  # opcional, por defecto NN (NASA); vacío = todo el gobierno federal
```

Dos knobs opcionales ajustan el cliente HTTP compartido por las fuentes sin clave
(`remoteok`, `arbeitnow`, `himalayas`, los tableros ATS, …):

| Variable | Por defecto | Efecto |
|---|---|---|
| `JOBSOURCE_TIMEOUT_SECONDS` | `30` | Timeout por petición. Súbelo para tableros ATS lentos, bájalo para saltar a la siguiente fuente antes. |
| `JOBSOURCE_USER_AGENT` | `jobpilot/0.1 (personal job application agent)` | `User-Agent` que envían esos adaptadores. Deja una>string de contacto; algunos tableros limitan los agentes anónimos. |

Adzuna queda deshabilitada hasta que completes el `.env` (es la única con techo de
25 llamadas/min y 250/día, y el agente se detiene solo al agotar ese presupuesto
para no comerse la clave). InfoJobs no necesita credenciales porque está retirada:
su API oficial no está disponible. `INFOJOBS_CLIENT_ID` / `INFOJOBS_CLIENT_SECRET`
no las lee ningún camino de código; aparecen comentadas en `.env.example` sólo para
explicar por qué.

> `.env` está en `.gitignore`, **`.env.example` no**. Nunca pegues una clave real en
> `.env.example`: ese fichero se versiona. Si alguna vez lo hiciste, rota la clave —
> borrarla del fichero no la borra del historial de Git.

Las fuentes con contenido en el idioma local publican sobre todo ofertas en ese
idioma, así que cada familia puede declarar `adzuna_queries` (conjuntos de
keywords por país, p. ej. `es:` términos en español; los usa Adzuna) — ver
`config/profile.yaml`. Las ofertas se filtran en la
ingesta para descartar categorías claramente no técnicas.

## Configuración rápida

Si no quieres tocar YAML, ejecuta **`jobpilot setup`** (ver abajo). Si prefieres
editarlo a mano, todo se edita en YAML, sin tocar código:

### Configuración guiada: `jobpilot setup`

Un asistente de terminal para quien no debería tener que aprender un formato de
configuración. Te pregunta tus datos, años de experiencia, puesto actual,
profesión objetivo, búsquedas, pesos de skills, seniority objetivo y países, y
escribe `config/profile.yaml` y `config/master_cv.yaml` por ti.

- Si escribes una profesión como `pilotos`, `software`, `enfermería`, `docencia` o
  `ventas`, te propone un punto de partida que puedes cambiar. Es solo una
  sugerencia: todos los valores son tuyos.
- Rellena el CV maestro con tus datos y los grupos de skills de tus familias, así
  que lo único que queda por escribir es tu propia historia.
- Si `config/profile.yaml` ya existe, pregunta antes de sobrescribir y guarda una
  copia en `profile.yaml.bak`.
- Todo lo que escribe es YAML normal. **No inventa logros**: los ejemplos se
  quedan marcados como placeholders, porque puntuar contra un CV inventado da
  números sin sentido.

### Diagnóstico: `jobpilot doctor`

Comprueba lo que falla en silencio y produce resultados vacíos o incorrectos:

- Que `config/profile.yaml` cargue y que los pesos sumen ~100.
- Que exista `ADZUNA_APP_KEY` en `.env` (si no, las fuentes con clave quedan
  desactivadas).
- Que el CV maestro tenga skills y experiencia: uno vacío hace que la dimensión
  `skills` valga ~0 y nada llegue nunca a `apply`.
- **`exclude_foreign_onsite: true` junto con una profesión presencial.** Es el
  error que más caro sale: pilotos, enfermería, docencia o cocina con esa opción
  activa descartan casi todas las ofertas, y el motivo no se ve en los
  resultados.
- Familias sin skills (se descartan siempre), con pocas skills, o sin queries (no
  se busca nada).

### Cambiar tus búsquedas: `jobpilot family`

- `jobpilot family list` — tabla de familias con nº de skills y de queries.
- `jobpilot family add` — creación interactiva de una familia nueva.
- `jobpilot family edit <id>` — cambia label, queries y skills (intro vacío =
  no cambiar).
- `jobpilot family rm <id>` — borra una familia, con confirmación.

Estos comandos editan el YAML **de forma quirúrgica**: solo se reescribe el item
afectado, así que tus comentarios, el resto del fichero y todas las demás
familias se conservan intactos. Un load-and-dump completo borraría en silencio las
notas que explican tus pesos.

### Guía rápida: `jobpilot tutorial`

Imprime los siete pasos, desde una instalación vacía hasta una candidatura
registrada, marcando los que ya has completado.

### `config/profile.yaml`

- **`search`** — ubicaciones (`adzuna_country`), `target_offers`, límites por query.
- **`search.exclude_foreign_onsite`** — en `true` (por defecto) descarta en la ingesta y el
  scoring las ofertas **híbridas o presenciales fuera de España** (¡no puedes
  trasladarte!): se mantienen las 100% remoto de cualquier país y todo lo de
  España. Pon `false` solo si quieres también híbridas/presenciales UK/Alemania.
- **`families`** — agrupa tus roles objetivo. Cada familia tiene:
  - `queries`: frases que se envían a cada fuente.
  - `sources`: `adzuna, arbeitnow, remoteok, himalayas` (+ boards ATS).
  - `skills`: mapa `skill → peso (1-10)` usado para medir la relevancia.
  - `interest`: interés editorial (0-10) como dimensión del scoring.
- **`scoring`** — `threshold` (apply), `review_threshold`, `weights` de las 7 dimensiones
  (`skills, experience, education, location, seniority, interest, industry`; suma 100).
  Una errata en el nombre de una dimensión, o pesos que se alejen de 100, se rechazan al
  cargar en vez de reescalar en silencio todas las puntuaciones.
- **`profile`** — `seniority_target`, `languages`, preferencias de ubicación
  (área + peso), `exclude_companies`.
  - `seniority_target` — uno de los niveles de `profile.seniority_levels` (por
    defecto `junior`, `midlevel`, `senior`, `lead`, `entry`). Las ofertas se
    puntúan por su distancia al objetivo (`100 - |objetivo − oferta|`), así que
    puedes apuntar el mismo motor a otra profesión o etapa profesional sin tocar
    código. Un nivel desconocido se rechaza al cargar.
  - `seniority_levels` — el vocabulario con el que se lee el seniority de una
    oferta. Por defecto es la lista de arriba; amplíala o cámbiala para describir
    tu propio sector.
  - `education_levels` — la misma idea para titulaciones, con los mismos valores
    por defecto.
  - `hard_filters` — requisitos que una oferta debe cumplir para puntuar:
    `regex` (un patrón que debe aparecer en la descripción) y
    `min_education_level` (el nivel mínimo que aceptas). Con `enabled: false` se
    desactiva un filtro sin borrarlo.
- **No es específico de robótica.** El motor no asume space, aeronáutica ni
  ingeniería. Las familias que trae el repo son un ejemplo: añade, edita o
  sustituye las tuyas con `jobpilot family` o a mano, y el mismo scoring,
  filtrado y tailoring de CV vale para pilotos, enfermería, docencia, cocina o
  ventas.
- **`search.max_pages_by_source`** — techo de páginas opcional por fuente (p. ej.
  `csod: 3`). Tiene prioridad sobre `max_pages_per_query` para esa fuente, y el
  flag `--max-pages` del CLI pisa ambos.
- **`ats_companies`** — slugs de empresas por plataforma ATS (greenhouse, lever,
  teamtailor, personio, ashby, workable, smartrecruiters, workday, csod) para
  consultar keyless el board de cada empresa. Teamtailor usa el host completo
  (`sateliot.com`); el resto, el slug del board. `workday` y `csod` son APIs con
  claves, así que cada entrada es un mapa con las coordenadas del board
  (`host`/`tenant`/`site`, o `portal_url`/`career_site_id`) y un `variant`
  opcional que permite repetir la misma empresa: por ejemplo `country: ES` y una
  segunda con `search_text: remote` y `remote_only: true`.
- **`custom_sources`** — adaptadores explícitos para boards de una sola
  organización (`esa`, `satcen`, `uarx`, `satlantis`, `euspa`, `pld`, `pangea`,
  `indra_space`, `space_careers`, `find_a_space_job`, `scl`, `euraxess`,
  `usajobs`).

### `config/master_cv.yaml`

Tu CV maestro, usado por el scoring (qué skills cuentas como "ya los tengo") y por
la Fase 3 (generación del CV). Bilingüe **es/en**: los campos narrativos se guardan
como `{es: ..., en: ...}` y `Config.master(lang)` los resuelve de forma determinista.

- `contact` — siempre lenguaje-neutral.
- `summary`, `experience`, `education`, `projects`, `certifications` — soportan
  dicts `{es, en}` por campo.
- `education` — solo títulos de grado reales. El resto (microgrados, formaciones,
  certificaciones en curso) va a `certifications`.
- `skills` — grupos de tecnologías. Un grupo cuyo nombre contenga `camino`
  (p. ej. `En camino (robótica/embedded)`) cuenta con factor 0.5 en el scoring:
  puedes hablar de ellas pero no son experiencia productiva todavía.

## Personalización por persona

El README describe el patrón, no los valores concretos; cada persona ajusta:

1. **Queries y familias** en `profile.yaml` → `families`. Añade/quita `queries`
   hasta cubrir tus ~20 roles objetivo y pondera `skills` según lo que exijan.
2. **Scoring** → mueve `threshold` arriba si quieres menos ruido, o ajusta `weights`
   (p. ej. sube `location` si solo te interesa remoto en tu país).
3. **Tu stack** en `master_cv.yaml` → `skills`. Lo que realmente dominas en grupos
   sin `camino`; lo que estás aprendiendo, en un grupo `En camino (...)`.
4. **Ubicación** → `profile.locations`: cada `area` con un `weight`. Las ofertas
   se puntúan contra la mejor coincidencia (onsite España, Remote EU, etc.).
5. **Empresas que evitas** → `profile.exclude_companies`; los roles con
   ciudadanía US, clearance o "located in US" se descartan automáticamente.

## Idiomas es/en

El CV master es bilingüe por diseño. En código:

```python
from jobpilot.config import load_config

config = load_config()
cv_en = config.master("en")   # todos los campos narrativos resueltos a inglés
cv_es = config.master("es")   # a español (idioma por defecto)
```

El idioma del CV generado se elige por `languages[0]` a menos que pases `--lang`.

## CV tailorizado (`jobpilot cv`)

Genera un CV adaptado a cada oferta en `output/cv/cv_<id>_<lang>.md` y
`output/cv/cv_<id>_<lang>.pdf`:

- **Backend LLM** (por defecto): construye un prompt con tu `master_cv` + la
  descripción de la oferta y redacta el CV vía `opencode run --format json`
(backend `complete_json`). Si falla, cae al backend heurístico.

La generación con IA reescribe y prioriza material del CV maestro para una oferta; **revisa siempre el resultado**. El prompt prohíbe inventar experiencia, pero la validación actual verifica principalmente la estructura, no todas las afirmaciones. 
*Si prefieres una generación determinista sin LLM, usa `--no-llm`.*

- **Backend heurístico** (`--no-llm`): reordena tus `skills` según las señaladas
  en la oferta (grupos `En camino` con factor 0.5) y las experiencias afines,
  sin texto inventado.
- `--lang es|en` fuerza idioma; `--show` imprime el markdown; `--no-pdf` omite el
  PDF; `--family X` restringe skills al conjunto de esa familia.
- `jobpilot cv list` lista lo ya generado (id, idioma, tamaño, fecha), para no tener
  que recordar el esquema de nombres ni recorrer `output/cv/` a mano.

## Dashboard de aplicaciones (`jobpilot report`)

Genera `output/report.html` autocontenido (sin assets externos) con tarjetas KPI
(ofertas, último run de scoring, triage, cola, CV generados), la cola de
aplicaciones, las mejores posiciones del último run con desglose de scoring
(top 5 con barras por dimensión) y un resumen por familia.

- `jobpilot queue set <id> --status apply --cv-file output/cv/cv_<id>_<lang>.md`
  enlaza el CV generado en la cola y el report lo muestra como link.
- `--notes` guarda el seguimiento (contacto, referidor, resultado). Al avanzar
  de estado (`--status applied`) las notas y el CV adjunto **se conservan**: un
  argumento vacío significa "sin cambios", no "bórralo".
- `jobpilot queue --status apply` filtra la cola por estado.
- La cola guarda `created_at` (cuando entró) y `applied_on` (fecha de aplicación,
  se rellena sola al pasar a `applied`), muestra la antigüedad por estado y
  sugiere el siguiente paso.
- El report muestra esas fechas y la antigüedad en la tabla de la cola.
- `--open` abre el report en el navegador; `--family X` filtra las tablas de scoring.

## Resiliencia del sync y deduplicación

`jobpilot sync` está pensado para que un portal roto no arruine la ejecución entera:

- **Cada fuente va aislada.** Toda llamada a un adaptador pasa por una guarda que
  captura timeouts, errores HTTP, límites de tasa (429) y respuestas malformadas. La
  fuente que falla queda registrada como bloqueada en las estadísticas del run y el
  sync continúa con la siguiente.
- **Cuotas diarias por fuente** se leen de la base de datos antes de cada llamada, así
  que un sync repetido no puede agotar la cuota de una fuente.
- **Reintentos con backoff exponencial**, sólo ante fallos transitorios.
- **Una fila de run por sync** con los contadores de insertadas/actualizadas/duplicadas
  por fuente, para que un run malo se pueda diagnosticar a posteriori.
- `Ctrl+C` (o `Esc` en el spinner) detiene tras el lote en curso y aun así cierra la
  fila del run, así que no se pierde lo ya confirmado.

**Duplicados entre fuentes.** Las ofertas se identifican por `source + source_id`
para el upsert por fuente, más un hash de contenido (título + empresa + ubicación)
para que el mismo posting sindicado en dos portales se guarde una sola vez.

Ese hash exacto es deliberadamente conservador: *no* fusiona "Sr. Python Developer"
con "Senior Python Developer", porque equivocarse descarta en silencio una oferta
real. Si prefieres el resultado más agresivo, actívalo por ejecución:

```bash
jobpilot sync --relaxed-dedupe
```

`--relaxed-dedupe` fusiona además los postings cuyos títulos sólo difieren en la
formulación: expande abreviaturas (`Sr.` → `senior`), elimina paréntesis (`(m/f/d)`),
ignora el orden de las palabras y la forma de la ubicación, y **exige además que las
descripciones coincidan** antes de fusionar. Hay que cumplir las dos condiciones, así
que un puesto realmente distinto se conserva. El intercambio, en una línea: menos
duplicados, pero una pareja fusionada por error significa una oferta perdida — por eso
viene desactivado. Las ofertas que ya estaban en la base conservan su clave relajada
original hasta que vuelven a aparecer; un único re-sync basta para backfillearlas.

## Calibración del scoring

La dimensión **skills** premia cuánto cubres las skills que *pide* la oferta y ya
no castiga a los postings cortos (una oferta que cita 2-3 skills del dominio de la
familia ya no recibe un valor mínimo por su escasa representación). Ajusta
`threshold`, `min_skills_for_apply` y `weights` en `profile.yaml` → `scoring`.

## Desarrollo

```bash
  git clone https://github.com/shoganaix/job-pilot-AI.git
  cd job-pilot-AI
  python3 -m venv .venv
  source .venv/bin/activate
  python -m pip install -e ".[dev]"
  jobpilot init
```
Si ya has clonado el proyecto, entra en su carpeta, activa `.venv` y ejecuta `python -m pip install -e ".[dev]"` para actualizar la instalación editable. `jobpilot init` conserva los archivos de configuración existentes.

```powershell
git clone https://github.com/shoganaix/job-pilot-AI.git
cd job-pilot-AI
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
jobpilot init
Copy-Item .env.example .env -ErrorAction SilentlyContinue
```
Si PowerShell bloquea la activación, puedes usar directamente `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"` y `.\.venv\Scripts\jobpilot.exe <comando>`; no necesitas cambiar la política global de ejecución.

Cobertura y chequeos de tipos (hoy ninguno bloquea un merge):

```bash
.\.venv\Scripts\python.exe -m pytest --cov=jobpilot --cov-report=term --cov-report=xml
.\.venv\Scripts\python.exe -m mypy src/jobpilot --ignore-missing-imports
```

- **CI** corre en Python 3.11, 3.12, 3.13 y 3.14 (`.github/workflows/ci.yml`).
- **mypy** es *advisory*: el job es `continue-on-error`, así que un hallazgo nuevo de
  tipado nunca bloquea una PR. El paquete publica `py.typed`.
- **Cobertura** se reporta (actualmente ~72%) y tiene suelo del 70% vía `fail_under`
  en `pyproject.toml`.

Estructura:

```text
src/jobpilot/
  cli.py            # CLI (argparse + rich): todos los comandos, incluido `cv list`
  config.py         # carga YAML + resolver bilingüe (MasterCV.in_lang) + validación
  llm.py            # backend LLM (opencode run --format json) + extract_json
  wizard.py         # setup guiado, doctor, editor de familias, tutorial
  yaml_edit.py      # edición de bloques YAML conservando comentarios (la usa wizard.py)
  models.py         # tipos Offer, SourcePage, Triage...
  storage.py        # SQLite (upsert, dedupe, ofertas, scores, migraciones de esquema)
  py.typed          # marcador PEP 561
  resources/
    profile.yaml    # perfil por defecto empaquetado (se copia a config/ al iniciar)
  sources/          # un adaptador JobSource por portal
    base.py         # HTTP, retry/backoff, cuotas, descargas protegidas
    registry.py     # construye los adaptadores activos según el perfil
    adzuna.py  arbeitnow.py  remoteok.py  himalayas.py
    ats_boards.py   # Greenhouse, Lever, Teamtailor, Personio, Ashby, Workable,
                    #   SmartRecruiters, Workday CXS, Cornerstone CSOD
    space_boards.py # carreras en la ESA
    space_portals.py# portales de empleo aeroespaciales por empresa
    usajobs.py      # empleo federal de EE.UU. (lo filtran los hard filters por defecto)
    infojobs.py     # retirada: la API oficial de InfoJobs no está disponible
  pipeline/         # search.py (sync), score.py, cv.py, report.py
  matching/         # taxonomy (variantes), extract, industry, scoring
```
## 3. Ejemplo completo: desde arrancar hasta enviar una candidatura

El ID `125` es **solo un ejemplo**. Sustitúyelo por un ID real que aparezca en tu base de datos. Los comandos se ejecutan dentro de la carpeta del repositorio, con el entorno virtual activado.

```powershell
# 0. En una sesión posterior, abre el proyecto y activa el entorno
cd ruta\a\job-pilot-AI
.\.venv\Scripts\Activate.ps1

# 1. Revisa las fuentes y el plan
jobpilot sources
jobpilot plan

# 2. Descarga ofertas y calcula su ajuste a tu CV
jobpilot sync
jobpilot score --show 10 --details

# 3. Consulta los IDs; opcionalmente busca en las ofertas ya almacenadas
jobpilot offers --limit 50 --has-description
jobpilot query "robotics"

# 4. Elige un ID REAL de la tabla. Ejemplo: 125
jobpilot cv 125 --lang en --show

# 5. Comprueba el PDF generado en output/cv/cv_125_en.pdf
#    Revisa experiencia, tecnologías, titulaciones, idioma y contenido.

# 6. Añade la oferta a la cola, asociando el CV generado
jobpilot queue set 125 --status apply --cv-file "output/cv/cv_125_en.pdf"

# 7. Abre la oferta en tu navegador
jobpilot open 125

# 8. PASO MANUAL: rellena el formulario de la empresa, adjunta el PDF,
#    responde a las preguntas y pulsa Enviar. Comprueba la confirmación.

# 9. SOLO DESPUÉS de haber enviado la candidatura, registra el estado
jobpilot queue set 125 --status applied

# 10. Consulta el seguimiento y abre el dashboard
jobpilot queue
jobpilot report --open
```

**Opción sin IA:** sustituye el paso 4 por `jobpilot cv 125 --lang en --no-llm --show`. Si la oferta está en español: `jobpilot cv 125 --lang es --no-llm`.

**Atención al fichero del CV:** `--cv-file` asocia una ruta a la cola, pero no adjunta ese archivo a ningún formulario ni lo envía. El README anterior utilizaba la ruta `.md`; puedes asociar el PDF si ese es el documento que vas a presentar. El comando de apertura abre la URL de la oferta, no el PDF.

## 4. Referencia completa de comandos y flags

`<id>` significa ID entero de oferta; `<familia>` es el identificador exacto definido en `config/profile.yaml` (por ejemplo, `robotics`). Los flags que no aparecen bajo un comando no se aplican a él.

| Comando | Flags/argumentos | Para qué sirven |
|---|---|---|
| `jobpilot init` | ninguno | Inicializa carpetas, configuración y SQLite sin sobrescribir la configuración existente. |
| `jobpilot sources` | ninguno | Muestra fuentes habilitadas o deshabilitadas y el motivo. |
| `jobpilot plan` | `--family <familia>` | Muestra solo el plan de una familia; sin flag, todas. |
| `jobpilot sync` | `--family <familia>` | Descarga solo esa familia. |
| | `--dry-run` | Consulta las fuentes sin persistir ofertas; **puede consumir llamadas API**. |
| | `--source <fuente>` | Limita a una fuente; se puede repetir: `--source adzuna --source arbeitnow`. |
| | `--max-pages <n>` | Sobrescribe el máximo de páginas por consulta. |
| `jobpilot offers` | `--family <familia>` | Filtra por familia; se puede repetir. |
| | `--source <fuente>` | Filtra por fuente; se puede repetir. |
| | `--limit <n>` | Número máximo de filas (valor por defecto: 40). |
| | `--has-description` | Solo ofertas con descripción completa. |
| `jobpilot query <texto>` | `--limit <n>` | Busca texto en ofertas **ya guardadas** (por defecto: 20); no hace una nueva búsqueda web. |
| `jobpilot score` | `--family <familia>` | Puntúa solo una familia. |
| | `--limit <n>` | Limita el número de ofertas evaluadas. |
| | `--show <n>` | Filas mostradas por categoría de triage (por defecto: 5). |
| | `--details` | Muestra el desglose de las dimensiones de puntuación. |
| `jobpilot cv <id>` | `--lang es` / `--lang en` | Fuerza idioma; sin flag usa el primer idioma de `profile.languages`. |
| | `--family <familia>` | Fuerza la familia utilizada para adaptar el CV. |
| | `--no-llm` | **No llama a IA**: usa el generador heurístico con el CV maestro. |
| | `--no-pdf` | Genera Markdown pero omite la exportación a PDF. |
| | `--model <proveedor/modelo>` | Indica el modelo de OpenCode para la generación con IA; no tiene efecto útil con `--no-llm`. |
| | `--show` | Imprime el Markdown generado en la terminal. |
| `jobpilot queue` | `--status <estado>` | Filtra la cola por estado. |
| `jobpilot queue set <id>` | `--status <estado>` | Actualiza el estado local de la oferta; obligatorio al usar `set`. |
| | `--notes <texto>` | Guarda una nota de seguimiento. |
| | `--cv-file <ruta>` | Asocia la ruta del CV a la candidatura local. **No lo sube ni lo envía.** |
| `jobpilot open <id>` | ninguno | Abre la URL de la oferta (URL de candidatura si está disponible). |
| `jobpilot report` | `--family <familia>` | Filtra los datos del dashboard por familia. |
| | `--out <ruta>` | Cambia la ruta del HTML (por defecto `output/report.html`). |
| | `--open` | Abre el dashboard generado en el navegador. |

Para la ayuda local y actualizada del código que tengas instalado:

```bash
jobpilot --help
jobpilot cv --help
jobpilot sync --help
jobpilot queue --help
```
## Privacidad

- `.env` (claves), `data/` (ofertas personales), `output/` (CVs generados),
  `config/profile.yaml` y `config/master_cv.yaml` están en `.gitignore`:
  **no se suben**.
- Mantén el repositorio privado si tu base de datos local o tus CVs llegaron a
  estar versionados antes de que existiera esta regla: quitar un archivo del
  índice no lo borra del historial de Git. Rota cualquier clave que se haya
  subido alguna vez.
- Todo lo que la herramienta necesita vive en tu directorio de trabajo, así que
  publicar un fork es seguro.

## Notas de seguridad
Las descripciones de oferta que lee esta herramienta son texto de terceros,
controlado por quien publica, así que se tratan como datos y nunca como
instrucciones:

- **Credenciales**: Adzuna se autentica con cabecera `Authorization: Basic` en
  lugar de parámetros de query, y todo mensaje de error, estadística de run y
  línea de log pasa por un redactor, de modo que una clave no puede acabar en
  `runs.stats` ni en el manifiesto del run. El subproceso del LLM recibe además
  un entorno mínimo: no hereda las claves de las bolsas de empleo.
- **Prompt injection**: la oferta se envuelve entre delimitadores explícitos
  `UNTRUSTED ... DATA` y —la parte que de verdad lo aplica— el CV devuelto se
  contrasta con tu CV maestro. Un nombre, email, empresa o titulación que no
  aparezca en el maestro aborta el CV tailorizado y cae al renderizador
  heurístico, así que una oferta hostil no puede reescribir tu identidad.
- **Report HTML**: todo el texto va escapado y cada enlace pasa una lista blanca
  de esquemas (`http`, `https`, `mailto`, `file`), así que una URL `javascript:`
  guardada desde una oferta se muestra como texto plano y no como enlace vivo.
- **Red**: se reintenta `429` y `5xx` con backoff exponencial respetando
  `Retry-After`; el resto de `4xx` no se reintenta, porque reintentarlo solo
  gasta cuota. Las fuentes con tope diario gratis (Adzuna) se detienen limpiamente
  al agotar el presupuesto.
