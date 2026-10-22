# SeleccionGruas

Selección de grúa y configuración para maniobras de izaje a partir de las
**tablas de carga oficiales** de los fabricantes.

Flujo: **PDF → extracción validada → SQLite → export CSV/SQL → Supabase**, y un
motor determinista que responde *«¿qué grúa/configuración levanta X toneladas a
Y metros de radio y Z metros de altura?»*.

> Herramienta de **pre-selección**: no sustituye el plan de izaje ni la validación
> del gruista y del manual oficial.

## Stack

| Capa | Tecnología |
|---|---|
| Frontend (previsto) | HTML5, CSS3, JavaScript vanilla en Vercel |
| Datos | Supabase (PostgreSQL + Auth + RLS) |
| Ingesta | Python + `poppler` (`pdftotext`, `pdftocairo`), offline |

## Estructura

```
PRD.md                 Product Requirements Document
SRS.md                 Software Requirements Specification
ANALISIS.md            análisis técnico y alternativas de ingesta
crane_tables/
  README.md            uso del pipeline
  SUPABASE.md          carga de datos en Supabase (CSV o SQL)
  tools/               extracción, validación, export y consulta
  supabase/
    schema.sql         DDL + vista + staging
    load_from_csv.sql  transformación staging → normalizado
```

## Estado de los datos

| Grúa | Capacidad | Tablas | Celdas |
|---|---|---|---|
| Liebherr LTM 1300-6.3 | 300 t | 30 | 16 474 |
| Liebherr LTM 1450-8.1 | 450 t | 61 | 36 378 |
| **Total** | | **91** | **52 852** |

## Qué NO está versionado

Por tamaño, licencia o porque es regenerable:

- `LTM-*.pdf` — manuales del fabricante. **Deben colocarse en la raíz** del repo.
- `crane_tables/db/` — base SQLite generada.
- `crane_tables/out/` — exportaciones intermedias.
- `crane_tables/supabase/data/` y `seed.sql` — artefactos de carga generados.

Todo ello se reconstruye con el pipeline (ver abajo).

## Reproducir la base de datos

```bash
cd crane_tables

# 1) PDFs -> SQLite (con validación estructural)
python3 -m tools.build_fleet db/fleet.db

# 2) SQLite -> artefactos Supabase (CSV + SQL)
python3 -m tools.export_supabase db/fleet.db supabase

# 3) consulta local de prueba
python3 -m tools.query db/fleet.db --load 50 --radius 15 --height 23
```

Requisitos: `poppler-utils` y Python 3.11+.

## Documentación

- [`PRD.md`](PRD.md) — producto, roles, alcance y criterios de aceptación.
- [`SRS.md`](SRS.md) — modelo de datos real, requisitos y contrato de la RPC.
- [`ANALISIS.md`](ANALISIS.md) — alternativas de ingesta y validación.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — convenciones de commits, ramas y PRs.
- [`docs/ENTORNOS.md`](docs/ENTORNOS.md) — entornos local, preview y producción.
- [`crane_tables/README.md`](crane_tables/README.md) — pipeline paso a paso.
- [`crane_tables/SUPABASE.md`](crane_tables/SUPABASE.md) — carga en Supabase.
