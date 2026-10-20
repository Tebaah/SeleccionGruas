# crane_tables — ingesta y consulta de tablas de carga

Pipeline: **PDF de la grúa → SQLite → selector de configuración**, con validación.

## Requisitos
- `poppler-utils` (`pdftotext`, `pdftocairo`)
- Python 3.11+ (solo biblioteca estándar para el pipeline)

## Uso

```bash
# 1) Extraer todas las tablas de carga del PDF a SQLite (con validación)
python3 -m tools.build_db  ../LTM-1300-6.3.pdf db/cranes.db

# 1b) O construir la base de toda la flota (varios PDFs en una sola BD)
python3 -m tools.build_fleet db/fleet.db

# 2) Consultar: qué configuraciones levantan una carga a un radio (y altura) dado
python3 -m tools.query     db/fleet.db --load 50 --radius 15 --height 23
python3 -m tools.query     db/cranes.db --load 18 --radius 30 --system T --cw 88

# 3) Exportar a CSV/JSON (para revisión / uso externo)
python3 -m tools.export    db/cranes.db out/ltm1300-6.3.csv
python3 -m tools.export    db/cranes.db out/ltm1300-6.3.json

# 4) Re-importar un CSV revisado (misma validación)
python3 -m tools.import_csv db/reviewed.db out/ltm1300-6.3.csv
```

## Cómo funciona (y por qué así)

1. **`pdf_words.py`** — `pdftotext -bbox-layout` da cada palabra con su caja.
   El PDF es vectorial, no un escaneo, así que esto es exacto.
2. **`svg_grid.py`** — `pdftocairo -svg` da las líneas de la tabla. Se usan como
   fuente de verdad para las columnas, porque hay **encabezados fusionados**
   (p. ej. «14,7 m» ocupa dos columnas de datos) y **sub-columnas con nota `*`**;
   alinear por la posición del texto daría resultados erróneos.
3. **`parse_charts.py`** — reconstruye filas (etiquetas de radio), columnas
   (reglas + encabezados de pluma/ángulo) y asigna cada número a su celda.
   Segmenta la página en sub-tablas apiladas (TNZF/TVK).
4. **`build_db.py`** — valida y carga. La validación es **estructural**:
   la capacidad no debe crecer al crecer el radio; las celdas que lo hacen se
   reportan para revisión humana.
5. **`query.py`** — interpola capacidad en el radio pedido y devuelve las
   configuraciones factibles ordenadas por margen.

## Formatos de datos

Esquema SQLite:

- `crane(id, manufacturer, model, max_capacity_t, source_pdf)`
- `chart(id, crane_id, page, system, counterweight_t, boom_min, boom_max, jib_m, ballast_options)`
- `capacity(chart_id, radius_m, boom_m, angle_deg, footnote, capacity_t)`

CSV: una fila por celda, columnas `model, page, system, counterweight_t,
boom_min, boom_max, jib_m, ballast_options, boom_m, angle_deg, footnote,
radius_m, capacity_t`.

## Cargar en Supabase

Genera los artefactos (esquema + CSV + SQL) y cárgalos en Supabase:

```bash
python3 -m tools.export_supabase db/fleet.db supabase
# Ruta SQL : ejecuta supabase/seed.sql en el SQL Editor de Supabase
# Ruta CSV : carga supabase/data/flat.csv en staging_capacity y ejecuta
#            supabase/load_from_csv.sql
```

Detalle completo en [`SUPABASE.md`](SUPABASE.md).

## Añadir otra grúa

El pipeline es paramétrico respecto al PDF: en la práctica solo hay que añadir el
PDF a la lista de `tools/build_fleet.py`.

```bash
python3 -m tools.build_fleet db/fleet.db
```

El sistema/plumín se lee de la etiqueta de la página (`T`, `TS 4 m`, `TK 7`,
`TF 17,5`, `TN 84`…) y los ángulos se agrupan solos (0/20/40, 0/10/20/40,
ángulos de pluma 83/75/67…). Puede requerir un ajuste si el nuevo manual usa una
estructura de columnas distinta (nuevas familias de plumín). La validación por
monotonía señala de inmediato lo que no cuadre —aunque en modelos con muchas
plumas cortas conviene interpretarla con criterio, porque la capacidad puede
subir con el radio de forma legítima.
