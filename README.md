# Job Pilot AI 
# [ENGLISH]
Personal AI-powered job application agent (CLI + SQLite). Searches for job opportunities across free sources, ranks them using a matching engine (0–100), generates a tailored CV for each position, and manages an application queue.

> Designed as a Python/CLI programming portfolio project, not as a commercial product. The job search engine relies on free APIs (keyless or with free API keys).

## Features

| Command | Description |
|---|---|
| `jobpilot init` | Initializes the project structure (configuration, data directories, SQLite schema) |
| `jobpilot plan` | Displays a summary of your configuration: job families, queries, and sources |
| `jobpilot sources` | Tests connectivity to the configured job sources |
| `jobpilot sync` | Fetches job listings based on each family's search queries |
| `jobpilot score [--family X --limit N]` | Scores stored job listings (0–100) and classifies them |
| `jobpilot offers [--family X]` | Lists saved job opportunities and their corresponding families |
| `jobpilot query <text>` | Searches through previously stored job listings |
| `jobpilot queue set <id> --status apply` | Adds a job opportunity to your application queue |
| `jobpilot open <id>` | Opens the job listing URL in your browser |

### Scoring and triage

- **apply** → Score ≥ 65 (and minimum skill relevance met) → Recommended for application.
- **review** → Score ≥ 45 → Requires manual review.
- **discard** → Score < 45 or fails hard filters (US citizenship, security clearance, excluded company).

## Requirements

- Python 3.12+ (tested on Python 3.14).
- Internet connection for job synchronization (all sources are keyless except Adzuna).

## Installation

```bash
git clone https://github.com/shoganaix/job-pilot-AI.git
cd job-pilot-AI
python -m venv .venv
.venv\Scripts\activate        # Windows (PowerShell)
pip install -e ".[dev]"       # Installs the jobpilot CLI + ruff + pytest

jobpilot init
```

The `init` command generates the `config/` and `data/` directories.

Copy `.env.example` to `.env` and add your API credentials:

```env
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
```

Adzuna remains disabled until valid credentials are provided in `.env`.

It is the only source with a rate limit of 25 requests/minute and 250 requests/day, making it particularly useful for covering the Spanish job market.

## Quick Configuration

All settings are managed through YAML files, without modifying the source code.

### `config/profile.yaml`

- **`search`** — Search locations (`adzuna_country`), `target_offers`, and per-query limits.
- **`families`** — Groups your target job roles. Each family includes:
  - `queries`: Search phrases sent to each job source.
  - `sources`: `adzuna, arbeitnow, remoteok, himalayas` (+ ATS boards).
  - `skills`: A `skill → weight (1–10)` mapping used to calculate skill relevance.
  - `interest`: Editorial interest score (0–10), used as a scoring dimension.
- **`scoring`** — `threshold` (apply), `review_threshold`, and the weights of the six scoring dimensions (`skills, experience, education, location, seniority, interest`), which must sum to 100.
- **`profile`** — `seniority_target`, `languages`, location preferences (area + weight), and `exclude_companies`.
- **`ats_companies`** — Company slugs for Greenhouse/Lever (keyless job boards), allowing direct access to their ATS listings.

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

## Development

Run linting and tests:

```bash
.\.venv\Scripts\ruff.exe check src tests
.\.venv\Scripts\python.exe -m pytest
```

### Project Structure

```text
src/jobpilot/
  cli.py            # CLI (argparse + rich)
  config.py         # YAML loader + bilingual resolver (MasterCV.in_lang)
  models.py         # Data types: Offer, SourcePage, Triage...
  storage.py        # SQLite (upsert, deduplication, offers, scores)
  sources/          # Adapters: adzuna, arbeitnow, remoteok, himalayas, ats_boards
  pipeline/         # Search (sync) and scoring (run_score)
  matching/         # Skill taxonomy (aliases), signal extraction, scoring
```

## Privacy
- `.env (API keys)`` and ``data/`` (personal job listings) are included in .gitignore: they are **not** committed to the repository.
- The only personal data tracked by Git is ``config/master_cv.yaml``.
  
# [ESPAÑOL]

Agente personal de aplicación de empleo (CLI + SQLite). Busca ofertas en fuentes
gratuitas, las puntúa con un motor de matching (0-100), genera un CV tailorizado
por oferta y mantiene una cola de aplicaciones.

> Diseñado como portafolio de programación (Python/CLI), no como un producto
> comercial. El motor de búsqueda usa APIs sin coste (keyless o con clave gratuita).

## Qué hace

| Comando | Qué hace |
|---|---|
| `jobpilot init` | Crea el esqueleto (config, datos, esquema SQLite) |
| `jobpilot plan` | Resumen de tu configuración: familias, queries, fuentes |
| `jobpilot sources` | Test de conectividad de las fuentes configuradas |
| `jobpilot sync` | Descarga ofertas según las queries de cada familia |
| `jobpilot score [--family X --limit N]` | Puntúa las ofertas almacenadas (0-100) y las clasifica |
| `jobpilot offers [--family X]` | Lista ofertas guardadas con su familia |
| `jobpilot query <text>` | Busca ofertas ya guardadas |
| `jobpilot queue set <id> --status apply` | Añade una oferta a tu cola de aplicaciones |
| `jobpilot open <id>` | Abre la URL de la oferta en el navegador |

Triage del scoring:
- **apply** → score ≥ 65 (y relevancia de skills mínima) → aplicar.
- **review** → score ≥ 45 → revisar manualmente.
- **discard** → score < 45 o incumple filtros duros (ciudadanía US, clearance, empresa excluida).

## Requisitos

- Python 3.12+ (probado en 3.14).
- Conexión a internet para el sync (excepto Adzuna, todas las fuentes son keyless).

## Instalación

```bash
git clone https://github.com/shoganaix/job-pilot-AI.git
cd job-pilot-AI
python -m venv .venv
.venv\Scripts\activate        # Windows (PowerShell)
pip install -e ".[dev]"       # instala el CLI jobpilot + ruff + pytest

jobpilot init
```

`init` genera `config/` y `data/`. Copia `.env.example` a `.env` y añade tus claves:

```
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
```

Adzuna está deshabilitada hasta que completes el `.env` (es la única fuente con
techo de 25 llamadas/min y 250/día, ideal para cubrir España).

## Configuración rápida

Todo se edita en YAML, sin tocar código:

### `config/profile.yaml`

- **`search`** — ubicaciones (`adzuna_country`), `target_offers`, límites por query.
- **`families`** — agrupa tus roles objetivo. Cada familia tiene:
  - `queries`: frases que se envían a cada fuente.
  - `sources`: `adzuna, arbeitnow, remoteok, himalayas` (+ boards ATS).
  - `skills`: mapa `skill → peso (1-10)` usado para medir la relevancia.
  - `interest`: interés editorial (0-10) como dimensión del scoring.
- **`scoring`** — `threshold` (apply), `review_threshold`, `weights` de las 6 dimensiones
  (`skills, experience, education, location, seniority, interest`; suma 100).
- **`profile`** — `seniority_target`, `languages`, preferencias de ubicación
  (área + peso), `exclude_companies`.
- **`ats_companies`** — slugs de empresas en Greenhouse/Lever (boards keyless) para
  consultar directamente sus ATS.

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

## Desarrollo

```bash
.\.venv\Scripts\ruff.exe check src tests
.\.venv\Scripts\python.exe -m pytest
```

Estructura:

```
src/jobpilot/
  cli.py            # CLI (argparse + rich)
  config.py         # carga YAML + resolver bilingüe (MasterCV.in_lang)
  models.py         # tipos Offer, SourcePage, Triage...
  storage.py        # SQLite (upsert, dedupe, ofertas, scores)
  sources/          # adaptadores: adzuna, arbeitnow, remoteok, himalayas, ats_boards
  pipeline/         # search (sync) y score (run_score)
  matching/         # taxonomy (variantes de skills), extract (señales), scoring
```

## Privacidad

- `.env` (claves) y `data/` (ofertas personales) están en `.gitignore`: **no se suben**.
- El único dato personal que se versiona es `config/master_cv.yaml`.
