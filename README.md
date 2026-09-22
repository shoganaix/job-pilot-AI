# Job Pilot AI

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
- El único dato personal que se versiona es `config/master_cv.yaml`. Si vas a hacer
  el repositorio público, valora usar un CV de ejemplo o mantenerlo privado.