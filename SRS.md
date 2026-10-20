# SRS — Software Requirements Specification

**Proyecto:** SeleccionGruas (Crane Selector) · **Versión:** 2.0
**Relacionados:** `PRD.md`, `ANALISIS.md`, `crane_tables/SUPABASE.md`.

---

## 1. Stack tecnológico

| Capa | Tecnología | Notas |
|---|---|---|
| Frontend | HTML5, CSS3, **JavaScript vanilla** | Sin framework ni build step; `supabase-js` por CDN |
| Backend / DB | **Supabase (PostgreSQL 15/16)** | PostgREST + funciones RPC |
| Autenticación | Supabase Auth | Email + contraseña; sin registro público |
| Seguridad | RLS + `REVOKE` + RPC `SECURITY DEFINER` | El frontend solo usa la `anon key` |
| Despliegue | Vercel | Sitio estático + variables de entorno |
| Ingesta | **Offline**: Python + `poppler` | `build_fleet` → `export_supabase` → CSV/SQL |

> La extracción de PDF **no** corre en Vercel ni en Supabase (requiere binarios
> nativos). Es un proceso local/CI; ver §6.

---

## 2. Modelo de datos (implementado)

### 2.1 Esquema relacional

```
crane 1 ──── * chart 1 ──── * capacity
```

Un `crane` tiene varias **tablas de carga** (`chart`), una por página/configuración.
Cada `chart` contiene las celdas de capacidad (`capacity`), indexadas por radio,
pluma, ángulo y nota.

### 2.2 Tablas

**`crane`** — equipo
| Columna | Tipo | Descripción |
|---|---|---|
| `id` | bigint identity | PK |
| `manufacturer` | text | Fabricante (p. ej. Liebherr) |
| `model` | text | Modelo (p. ej. LTM 1450-8.1) |
| `max_capacity_t` | numeric | Capacidad máxima nominal (300 / 450 t) |
| `source_pdf` | text | PDF de origen (trazabilidad) |

`unique (manufacturer, model)`

**`chart`** — una tabla de carga = **una configuración**
| Columna | Tipo | Descripción |
|---|---|---|
| `id` | bigint identity | PK |
| `crane_id` | bigint FK → `crane` | Equipo |
| `page` | int | Página del manual |
| `system` | text | Familia + plumín: `T`, `TK 21`, `TF 17,5`, `TN 84`, `TS 18 m`, `TNZF 22 m`, `TK/TNZK`, `TVK/TVNZK`… |
| `counterweight_t` | numeric | Contrapeso de esa tabla |
| `boom_min`, `boom_max` | numeric | Rango de pluma de la tabla |
| `jib_m` | numeric | Longitud de plumín (si aplica) |
| `ballast_options` | text | Radios de contrapeso VarioBallast disponibles (p. ej. `4.94;5.94`) |

`unique (crane_id, page)`

**`capacity`** — celda de la matriz
| Columna | Tipo | Descripción |
|---|---|---|
| `id` | bigint identity | PK |
| `chart_id` | bigint FK → `chart` | Tabla a la que pertenece |
| `radius_m` | numeric | Radio de trabajo (fila) |
| `boom_m` | numeric | Longitud de pluma (columna) |
| `angle_deg` | numeric | Ángulo del plumín/pluma (sub-columna) |
| `footnote` | text | `''` = 360°; `*` = sobre la parte trasera |
| `capacity_t` | numeric | **Capacidad del manual, sin factores añadidos** |

Índices: `(chart_id)` y `(chart_id, radius_m, boom_m, angle_deg)`.

**`v_capacity`** — vista plana (grúa + tabla + celda) para consultas de apoyo.
**`staging_capacity`** — tabla de texto para la carga por CSV (§6).

### 2.3 Por qué faltaban dimensiones en la propuesta original

La propuesta inicial era `tablas_carga(equipo_id, contrapeso_t)` y
`matriz_carga(tabla_carga_id, radio_m, pluma_m, capacidad_t)`. Es insuficiente:

- **`system`**: la capacidad depende de la configuración (pluma vs plumín TK/TF/TN,
  strong jib, celosía). Sin esto no se puede distinguir una tabla de otra.
- **`angle_deg`**: en los plumines la capacidad depende del **ángulo** (0/10/20/40°
  o ángulos de pluma 83/75/67°). Omitirlo mezcla columnas distintas.
- **`footnote`**: existe una sub-columna `*` (trabajo **sobre la parte trasera**)
  con capacidades distintas de la de 360°. Sin la nota se asignarían mal los valores.
- **`jib_m`** y **`ballast_options`**: el plumín y el radio de contrapeso
  (VarioBallast) forman parte de la configuración.

### 2.4 Mapeo con la propuesta original

| Propuesta | Implementado | Comentario |
|---|---|---|
| `equipos` | `crane` | + `source_pdf` |
| `tablas_carga` (equipo, contrapeso) | `chart` | + `system`, `jib_m`, `ballast_options`, rango de pluma |
| `matriz_carga` (radio, pluma, capacidad) | `capacity` | + `angle_deg`, `footnote` |

### 2.5 Volumen y cobertura (datos reales)

| Grúa | Capacidad | Tablas | Celdas | Sistemas | Contrapesos (t) | Radios (m) | Plumas (m) |
|---|---|---|---|---|---|---|---|
| LTM 1300-6.3 | 300 t | 30 | 16 474 | 15 | 22 / 42 / 68 / 77 / 88 | 3–94 | 14,7–90 |
| LTM 1450-8.1 | 450 t | 61 | 36 378 | 34 | 54 / 104 / 134 | 3–108 | 16,1–85 |
| **Total** | | **91** | **52 852** | | | | |

---

## 3. Requisitos funcionales

### RF-01 — Autenticación
- Solo usuarios registrados (Supabase Auth).
- Sesión con expiración configurable (inicial: 8 h).
- El frontend usa únicamente la `anon key`.

### RF-02 — Validación de entradas
- `peso > 0` (t), `radio > 0` (m), `altura ≥ 0` (m).
- Rechazar valores no numéricos o fuera de rango operativo.
- Mostrar unidades y redondear a 1 decimal (t) / 0,1 m.

### RF-03 — Geometría de pluma y altura
No se compara `pluma ≥ altura` (son magnitudes distintas). Se calcula:

```
x            = |radio − offset_cejuela|
altura_punta = h_cejuela + √(L² − x²)
altura_gancho = altura_punta − cabeza_gancho
L_mínima     = √((altura_gancho + cabeza_gancho − h_cejuela)² + x²)
```

- Una configuración es válida en altura si `altura_gancho ≥ altura_requerida`.
- Parámetros por defecto (calibrados con el diagrama *Hubhöhen* del LTM 1300):
  `h_cejuela = 3,0 m`, `offset_cejuela = 1,5 m`, `cabeza_gancho = 2,3 m`.
- **Recomendado:** guardar estos parámetros por grúa (`crane.heel_h_m`,
  `crane.heel_offset_m`, `crane.head_len_m`) — *pendiente de implementar*.

### RF-04 — Lógica de matching
Para cada configuración candidata `(chart, boom_m, angle_deg, footnote)`:

1. **Radio:** obtener la capacidad al radio pedido.
   - Si el radio coincide con una fila → valor exacto.
   - Si está entre dos filas → **interpolar linealmente**.
   - Alternativa conservadora: usar la fila inmediatamente superior (menor capacidad).
   - Si el radio supera el máximo tabulado de esa columna → no factible.
2. **Altura:** aplicar RF-03.
3. **Capacidad:** `capacidad_util = capacity_t × factor_utilizacion`.
   Factible si `capacidad_util ≥ peso + peso_aparejo`.
4. **Filtros:** rango de giro (`footnote`), contrapeso máximo, permitir/denegar plumín.

> `factor_utilizacion` (p. ej. 0,75) y `peso_aparejo` son **parámetros de la
> consulta**, no columnas de datos.

### RF-05 — Ordenamiento
- Primario: `crane.max_capacity_t` **ascendente** (la grúa más pequeña primero).
- Desempate: menor `counterweight_t` → menor `boom_m` → mayor margen.
- Devolver hasta 5 opciones.

### RF-06 — Sugerencia cuando no hay resultados
Calcular, sobre la mejor configuración de la flota:
- radio máximo para el peso/altura pedidos;
- peso máximo a ese radio/altura;
- altura máxima;
- o la combinación de ajustes mínimos.

### RF-07 — Trazabilidad
Cada resultado devuelve `crane`, `page`, `system`, `chart_id`, `boom_m`,
`angle_deg`, `counterweight_t`, `capacity_t`.

### RF-08 — Filtros de configuración
Permitir/denegar plumín, fijar contrapeso máximo y exigir un margen mínimo.

### RF-09 — Administración de datos
La carga se hace por el pipeline offline (§6). No hay CRUD web en el MVP.
Toda recarga es **idempotente** y conserva `source_pdf`.

### RF-10 — Parámetros de seguridad
`factor_utilizacion`, `peso_aparejo` y `rango_giro` deben ser explícitos,
configurables y visibles en el resultado.

---

## 4. Requisitos no funcionales

### RNF-01 — Seguridad
- Las tablas `crane`, `chart` y `capacity` **no** se exponen al frontend.
- `REVOKE ALL` sobre las tablas a `anon` y `authenticated`.
- Exponer solo **funciones RPC** (`SECURITY DEFINER`, `SET search_path = public`),
  con `GRANT EXECUTE` a `authenticated`.
- Validar entradas dentro de la función y evitar SQL dinámico.
- **Acción pendiente:** el `schema.sql` actual crea políticas de lectura para
  `authenticated`; si se adopta el modelo RPC‑only, deben eliminarse.

### RNF-02 — Rendimiento
- p95 de la búsqueda **< 800 ms**.
- Índice `(chart_id, radius_m, boom_m, angle_deg)`.
- 52 852 celdas: no requiere materialización; basta la RPC con índices.

### RNF-03 — Usabilidad
- Responsive (tablet/móvil), español, mensajes claros.
- Resultado con utilización (%) y aviso si el margen es bajo.

### RNF-04 — Integridad de datos
- `capacity_t > 0`, `radius_m ≥ 0`.
- `unique (manufacturer, model)` y `unique (crane_id, page)`.
- **El margen del 75 % no se almacena**: se aplica en la consulta.
- Unidades homogéneas: t, m, °.
- Validador estructural en la ingesta; celdas dudosas marcadas para revisión.

### RNF-05 — Trazabilidad y auditoría
- Cada fila enlaza a grúa/página/tabla.
- Registrar fecha de ingesta y origen (`source_pdf`).

### RNF-06 — Mantenibilidad
- Añadir una grúa = PDF + entrada en `tools/build_fleet.py` + re‑ejecutar pipeline.

### RNF-07 — Disponibilidad
- Supabase y Vercel gestionados; sin servidores propios.

---

## 5. Contrato de la RPC (a implementar)

```sql
create or replace function public.select_cranes(
  p_load_t            numeric,
  p_radius_m          numeric,
  p_height_m          numeric,
  p_utilization       numeric default 0.75,   -- factor de utilización
  p_hook_block_t      numeric default 0,
  p_allow_jib         boolean default true,
  p_max_counterweight numeric default null,
  p_slewing           text    default '360'   -- '360' | '*'
) returns table (
  crane text, page int, system text,
  boom_m numeric, angle_deg numeric, jib_m numeric,
  counterweight_t numeric, capacity_t numeric,
  utilization_pct numeric, hook_height_m numeric, chart_id bigint
)
language sql stable security definer set search_path = public
as $$ ... $$;

grant execute on function public.select_cranes(numeric,numeric,numeric,numeric,numeric,boolean,numeric,text)
  to authenticated;
```

La implementación concreta (interpolación + geometría + orden) se desarrollará
sobre el esquema ya cargado; el contrato anterior fija la interfaz.

---

## 6. Ingesta de datos (offline)

```bash
cd crane_tables
python3 -m tools.build_fleet db/fleet.db          # PDFs -> SQLite + validación
python3 -m tools.export_supabase db/fleet.db supabase
```

Artefactos y rutas:

| Ruta | Cómo |
|---|---|
| **SQL** | Ejecutar `supabase/seed.sql` en el SQL Editor / `psql` |
| **CSV** | Cargar `supabase/data/flat.csv` en `staging_capacity` y ejecutar `supabase/load_from_csv.sql` |

Verificado contra PostgreSQL 16: **2 grúas / 91 tablas / 52 852 celdas**, idempotente.

---

## 7. Casos de prueba / aceptación

| # | Entrada | Esperado |
|---|---|---|
| T1 | 50 t, 15 m, 23 m | LTM 1450-8.1 factible (~91,6 t); LTM 1300-6.3 no (49,4 t netas) |
| T2 | 18 t, 30 m, sin altura | Devuelve configuraciones factibles ordenadas por grúa menor |
| T3 | 500 t, 10 m | 0 resultados + sugerencia cuantificada |
| T4 | Radio 200 m | 0 resultados + aviso de rango |
| T5 | Usuario sin sesión | 401 / redirección a login |
| T6 | `select * from capacity` con `anon` | Denegado |
| T7 | Factor 0,75 vs 1,00 | El resultado cambia y la utilización se muestra |

---

## 8. Decisiones abiertas

1. **Factor de utilización:** ¿política fija de 0,75 o configurable por usuario/empresa?
2. **Geometría por grúa:** ¿se añaden `heel_h_m`, `heel_offset_m`, `head_len_m` a `crane`?
3. **Plumín por defecto:** ¿se permite siempre o el operador debe habilitarlo?
4. **Viento y VarioBallast:** ¿se incorporan en la v1.1?
5. **Peso del aparejo:** ¿tabla por grúa/gancho o parámetro manual?

---

## 9. Anexo A — Estado implementado vs. pendiente

| Elemento | Estado |
|---|---|
| Esquema `crane/chart/capacity` + vista + staging | ✅ implementado |
| Extracción PDF de 2 grúas (52 852 celdas) | ✅ implementado y validado |
| Exportación CSV/SQL y carga en Supabase | ✅ probado en PostgreSQL 16 |
| Autenticación Supabase | ⬜ a implementar |
| RPC `select_cranes` | ⬜ a implementar |
| Endurecer RLS a RPC‑only | ⬜ pendiente |
| Parámetros geométricos por grúa | ⬜ pendiente |
| Tablas de viento / peso de aparejo | ⬜ pendiente |
