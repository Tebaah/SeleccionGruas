# Ingesta offline → Supabase (CSV o SQL)

Sistema para **obtener la información de los PDF de las grúas** y **cargarla en
Supabase** por CSV o SQL, sin infraestructura extra.

```
 PDFs ──► build_fleet ──► SQLite ──► export_supabase ──► CSV / SQL ──► Supabase
 (manuales)   (extrae)     (local)     (genera)          (2 rutas)     (Postgres)
```

Todo el pipeline es local; Supabase solo recibe datos ya extraídos y validados.

## 1. Extraer (local)

```bash
cd crane_tables
python3 -m tools.build_fleet db/fleet.db          # lee tools/build_fleet.py
```
- Recorre los PDFs del manifiesto (`tools/build_fleet.py`) y construye
  `db/fleet.db` (SQLite) con la validación de monotonía.
- Añadir una grúa nueva = añadir una línea al manifiesto.

## 2. Generar los artefactos para Supabase

```bash
python3 -m tools.export_supabase db/fleet.db supabase
```
Produce:

| Archivo | Para qué |
|---|---|
| `supabase/schema.sql` | DDL: tablas, índices, vista `v_capacity`, tabla `staging_capacity`, RLS |
| `supabase/data/cranes.csv` | 1 fila por grúa |
| `supabase/data/charts.csv` | 1 fila por tabla/página |
| `supabase/data/capacities.csv` | 1 fila por celda (normalizado) |
| `supabase/data/flat.csv` | todo denormalizado (para la ruta CSV) |
| `supabase/seed.sql` | **schema + INSERTs**, se ejecuta de una vez |
| `supabase/load_from_csv.sql` | transformación `staging_capacity` → normalizado |

## Ruta A — SQL (la más simple)

`seed.sql` crea el esquema (idempotente) y carga todo:

1. Supabase → **SQL Editor** → pegar y ejecutar `supabase/seed.sql`.
   (o `psql "$DATABASE_URL" -f supabase/seed.sql` con la *connection string*).
2. Listo. Para re‑ingerir, vuelve a generarlo y ejecútalo: hace
   `delete` + `insert`, así que es **idempotente** (no duplica).

## Ruta B — CSV

Útil si prefieres revisar/editar en hoja de cálculo antes de cargar.

1. Ejecuta `supabase/schema.sql` (crea las tablas y `staging_capacity`).
2. Carga `supabase/data/flat.csv` en `staging_capacity`:
   - **Table Editor**: Import data → CSV → tabla `staging_capacity`.
   - o por CLI/psql:
     `\copy staging_capacity from 'flat.csv' with (format csv, header true)`
3. Ejecuta `supabase/load_from_csv.sql`: normaliza, hace *upsert* de grúa/tabla y
   **reemplaza** las celdas de las grúas presentes, y vacía el staging.

## Verificar

```sql
select crane, count(*) celdas, min(radius_m), max(radius_m)
from v_capacity group by crane;

select crane, system, boom_m, radius_m, capacity_t
from v_capacity where radius_m=15 order by crane, capacity_t desc limit 20;
```

Prueba realizada (Postgres 16 en Docker): ambas rutas cargan
**2 grúas / 91 tablas / 52 852 celdas** y son idempotentes.

## Seguridad (Supabase)

- RLS activado en las 3 tablas; política de **solo lectura** para usuarios
  autenticados. La escritura se hace por SQL Editor / service role / carga CSV.
- La ingesta **no** se expone a la web: es local. Así no hay endpoint que atacar.

## Qué aporta al frontend (fase siguiente)

`v_capacity` es una vista “plana” que el cliente puede consultar directamente
con `supabase-js` para filtrar. Para el motor de selección (interpolar en el
radio + geometría de altura + ranking) se añadirá después una función RPC en
Postgres, de modo que el cálculo sea determinista y auditable y el cliente haga
una sola llamada — sin cambiar nada de la ingesta.

## Re‑ingesta y trazabilidad

Cada carga queda identificada por `(manufacturer, model)` y `(crane_id, page)`,
con `source_pdf` como origen. Volver a ejecutar el pipeline y recargar deja la
base consistente (idempotente) y conserva la referencia al PDF de la grúa.
