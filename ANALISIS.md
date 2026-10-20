# Análisis y alternativas — Carga de tablas de carga (LTM 1300-6.3)

Documento de decisión sobre **cómo cargar las tablas de carga de la grúa** en una
base de datos y **cómo usarlas para seleccionar la configuración** ante unos
requerimientos (carga, radio, altura).

Al final se incluye un **prototipo funcional** que ya hace el ciclo completo:
PDF → base de datos SQLite → consulta de selección, con validación automática.

---

## 1. Resumen ejecutivo

- El PDF **no es un escaneo**: es texto vectorial. Eso permite extraer las tablas
  de forma **determinista** (coordenadas + líneas de la tabla), no por OCR.
- El `.md` sí es una conversión con pérdidas (celdas fundidas, columnas
  desordenadas, encabezados reordenados). Sirve como referencia, **no** como
  fuente para un programa de seguridad.
- Recomendación: **extracción automática por coordenadas desde el PDF + validación
  estructural + revisión puntual** (ruta A + D). Es la única que combina fiabilidad,
  trazabilidad y escalabilidad a otras grúas.
- Prototipo ya construido y validado:
  - **30 tablas** de carga extraídas (sistemas T, TK/TNZK, TVK/TVNZK, TS, TNZF).
  - **16 474 celdas** de capacidad en SQLite.
  - Validación por monotonía: de 534 columnas, solo **9 celdas** marcadas para
    revisión (y todas resultaron ser ondulaciones reales del propio manual, no
    errores de extracción — ver §7).
  - Selector funcionando: `carga + radio → configuraciones factibles ordenadas`.

---

## 2. Revisión de los archivos

| | `LTM-1300-6.3.pdf` | `LTM-1300-6.3.md` |
|---|---|---|
| Tamaño | 4,96 MB | 264 KB |
| Páginas / líneas | 60 | 3 592 |
| Naturaleza | **Texto vectorial** (fuentes Liebherr embebidas; `pdffonts` lo confirma) | Conversión a Markdown del PDF |
| Cifrado | Sí (`copy:no`) pero el texto se puede leer | — |
| Calidad de tabla | Perfecta (posiciones exactas) | **Degradada**: filas fusionadas, celdas desplazadas, encabezados de columna perdidos, celdas de notas mezcladas con datos |

Ejemplo del problema del `.md` (página 16, fila radio 3): aparece como
`| 3 300 | 155,7 116,6 |` sin distinguir que hay una **sub-columna marcada con `*`**
(columna «sobre la parte trasera»). Con el PDF vectorial y las líneas de la tabla,
esa distinción se recupera sin ambigüedad.

**Conclusión:** descartar el `.md` como fuente de datos; usar el PDF.

---

## 3. Estructura real de las tablas (lo que hay que modelar)

Cada página de carga (30 en total, entre las páginas 16 y 51) es una tabla:

- **Filas** = radio de trabajo en metros (columna doble, izquierda y derecha; de
  3 a 94 m según la tabla).
- **Columnas** = combinación de grúa. Hay 5 familias:

  | Sistema | Significado | Páginas | Estructura de columnas |
  |---|---|---|---|
  | `T` | pluma telescópica | 16–20 | longitud de pluma |
  | `TK/TNZK` | pluma + plumín abatible (K/NZK) 11,5 / 20 m | 22–25 | longitud × **ángulo 0/20/40°** |
  | `TVK/TVNZK` | pluma + extensión telescópica V 7/14 m + K/NZK | 27–35 | `boom + V` × ángulo |
  | `TS` | pluma + «strong jib» S 4…39 m | 37–43 | longitud de pluma |
  | `TNZF` | pluma + plumín de celosía fijo NZF 8…43 m | 45–51 | longitud × **ángulo 0/22,5/45°** |

- **Metadatos de cada tabla:** contrapeso (88/77/68/42/22 t), rango de pluma
  (p. ej. `14,7 – 90 m`), **radio de contrapeso VarioBallast** (4,94 / 5,94 m),
  y el marcador de rango de giro (360°, `EN`) y la nota `*` (trabajo sobre la
  parte trasera).

**Dos trampas reales encontradas** (y resueltas):
1. La primera columna de `T`/`TS` (14,7 m) está **partida en dos**: una
   sub-columna `*` (sobre la parte trasera) y la normal. El encabezado está
   fusionado. Por eso **no se puede** alinear columnas por la posición del texto:
   hay que usar las **líneas de la tabla** (reglas verticales) como fuente de verdad.
2. TVK lleva encabezados compuestos tipo `14,7 m + V 7 m` y varias tablas
   **apiladas verticalmente** en la misma página (TNZF). El parser segmenta la
   página en sub-tablas.

---

## 4. Alternativas para cargar los datos (ingesta)

### A. Extracción por coordenadas desde el PDF *(recomendada)*
`pdftotext -bbox-layout` da cada palabra con su caja `x0,y0,x1,y1`; con
`pdftocairo -svg` se recuperan las **líneas de la tabla** (reglas). Las reglas
definen las bandas de columna; las etiquetas de radio definen las filas.
- **Pros:** exacta, reproducible, auditable (mismo PDF → mismo resultado),
  escala a otros modelos Liebherr, no depende del `.md`.
- **Contras:** hay que escribir y mantener un parser; cada familia con
  sub-columnas necesita lógica propia; requiere validación.
- **Estado:** implementada y validada (ver §7).

### B. Parsear el `.md` ya convertido
Regex de tablas Markdown.
- **Pros:** trivial de programar.
- **Contras:** el `.md` ya perdió estructura (celdas fundidas, columnas
  desordenadas). Alto riesgo de cargar datos erróneos.
- **Veredicto:** solo para prototipos desechables.

### C. OCR / visión / LLM (imagen de la tabla → JSON)
- **Pros:** rápido de montar, tolera layouts irregulares; útil como **borrador**.
- **Contras:** **no determinista**, difícil de auditar, alucinaciones posibles.
- **Veredicto:** aceptable **solo** como generador de borradores que luego pasan
  por la validación de A/D. Nunca como fuente única para un programa de seguridad.

### D. Plantilla estructurada + carga manual/semiautomática (CSV/JSON)
Formato fijo (una fila = `sistema, contrapeso, pluma, ángulo, radio, capacidad`)
y un **validador** que verifica monotonía.
- **Pros:** 100 % exacta y trazable; la revisión humana es directa.
- **Contras:** 16 000+ celdas a mano es inviable **desde cero**.
- **Uso correcto:** **combinada con A** — A genera el CSV, un humano revisa solo
  las celdas dudosas, y el CSV revisado se vuelve a cargar. El prototipo ya
  incluye export e import a CSV.

### E. Datos digitales del fabricante / licencia
Liebherr ofrece datos de carga en su software (p. ej. LICCON). Si se puede
acceder/licenciar, es la fuente más fiable.
- **Pros:** máxima fiabilidad y soporte.
- **Contras:** coste, disponibilidad y restricciones de licencia; probablemente
  no cubre todos los modelos que se quieran.

### Comparativa

| | Exactitud | Esfuerzo | Escala a otras grúas | Auditabilidad | Uso en seguridad |
|---|---|---|---|---|---|
| A coordenadas | alta | medio | alta | alta | ✔ (con validación) |
| B desde `.md` | baja | bajo | media | baja | ✘ |
| C OCR/LLM | media | bajo | alta | baja | ✘ (solo borrador) |
| D CSV manual | máxima | alto | alta | máxima | ✔ |
| E licencia | máxima | bajo-si-existe | media | máxima | ✔ |

---

## 5. Recomendación

**A + D**: extraer automáticamente del PDF, **validar** y volcar a CSV para
revisión humana de las pocas celdas marcadas; el CSV revisado es la fuente
oficial de la base de datos. La **validación estructural** (§7) es el control de
calidad que hace viable confiar en la extracción automática.

---

## 6. Arquitectura propuesta

```
PDF ──► parser (coordenadas + reglas) ──► validador ──► SQLite ──► selector ──► API/CLI
                         │                                   │
                         └──────────► CSV/JSON (revisión) ◄──┘
```

**Esquema de base de datos (SQLite):**

- `crane(id, manufacturer, model, max_capacity_t, source_pdf)`
- `chart(id, crane_id, page, system, counterweight_t, boom_min, boom_max,
   jib_m, ballast_options)`
- `capacity(chart_id, radius_m, boom_m, angle_deg, footnote, capacity_t)`

**Lógica de selección** (lo que pide «qué grúa/configuración usar»):

1. Entrada: **carga** (t), **radio de trabajo** (m) y opcionalmente **altura** o
   **pluma fija**, más restricciones (contrapeso, sistema, rango de giro).
2. Para cada columna (sistema × pluma × ángulo), **interpolar** la capacidad en el
   radio pedido (interpolación lineal entre los dos radios tabulados; fuera de
   rango ⇒ esa columna no llega).
3. Quedarse con las que cumplen `capacidad ≥ carga` (con margen).
4. Ordenar por mejor margen / menor contrapeso / pluma más corta.
5. Devolver las configuraciones factibles con su % de utilización.

**Consideraciones que hay que añadir antes de producción:**

- **Bloque de gancho:** el propio manual indica deducir el peso del aparejo de la
  capacidad (p. ej. 1,90 t para la pasteca de 170 t).
- **VarioBallast:** dos radios de contrapeso (4,94 / 5,94 m) → dos juegos de
  capacidades; hay que capturarlos por separado.
- **Rango de giro:** 360° vs `*` (sobre la parte trasera) son columnas distintas.
- **Viento (WindSpeed):** el manual usa tablas con distintas velocidades de viento.
- **Configuración de pluma:** en TK/TVK/TS/TNZF hay que decidir además la longitud
  del plumín, la extensión V y el ángulo; y comprobar **altura de elevación**
  (que necesita geometría pluma/radio/altura, no solo la carga).

---

## 7. Prototipo desarrollado (resultado)

Carpeta `crane_tables/`:

```
tools/pdf_words.py     extrae palabras + coordenadas (pdftotext -bbox-layout)
tools/svg_grid.py      recupera las líneas/reglas de la tabla (pdftocairo -svg)
tools/parse_charts.py  reconstruye filas/columnas y asigna cada valor a su celda
tools/build_db.py      orquesta: extrae, valida y carga SQLite
tools/query.py         selector: (carga, radio, ...) → configuraciones factibles
tools/export.py        exporta CSV/JSON (ruta manual/semiautomática)
tools/import_csv.py    re-importa un CSV revisado con la misma validación
```

**Resultados de la extracción de `LTM-1300-6.3.pdf`:**

- 30 tablas, 16 474 celdas, 55 radios distintos, 17 longitudes de pluma.
- Contrapesos: 88 / 77 / 68 / 42 / 22 t.
- **Validación por monotonía** (la capacidad no debe subir al aumentar el radio):
  de **534 columnas**, solo **9 celdas** superaron la tolerancia. Se verificaron
  contra las páginas renderizadas: **todas son ondulaciones reales del manual**
  (la tabla no es estrictamente monótona en el arranque de alguna columna), salvo
  2 celdas duplicadas en la página 47 que sí son un artefacto del apilado de
  sub-tablas y quedan marcadas para revisión.

Esto demuestra que **la extracción automática es viable y verificable**: el
validador aísla exactamente las pocas celdas que un humano debe mirar.

**Ejemplo de uso del selector:**

```
$ python3 -m tools.query db/cranes.db --load 18 --radius 30
load 18.0 t @ radius 30.0 m -> 23 feasible setups
system       p  cw t  jib m  boom m angle fn   cap t util %
T           16    88      -    39.5     -      22.60   79.6
TS          37    88    4.0    29.6     -      22.30   80.7
T           16    88      -    44.5     -      22.00   81.8
...
```

---

## 8. Riesgos y controles

| Riesgo | Control |
|---|---|
| Celda mal asignada | Validación de monotonía + revisión de las celdas marcadas |
| Cambio de formato entre modelos/manuales | El parser se apoya en reglas de la tabla, no en posiciones fijas; validación por tabla |
| Valores interpolados usados como exactos | Interpolar solo entre radios tabulados y **usar siempre el lado conservador** |
| Falta de parámetros (viento, contrapeso, gancho) | Modelarlos explícitamente antes de producción |
| Uso en campo (seguridad) | El programa **orienta**; la decisión final es del gruista y del manual oficial |

---

## 9. Siguientes pasos

1. Revisar las 9 celdas marcadas y cerrar el artefacto de sub-tablas apiladas.
2. Capturar contrapeso por radio (4,94/5,94 m) y rango de giro como atributos.
3. Añadir geometría pluma–radio–altura y verificación de altura de elevación.
4. Modelar el peso del bloque de gancho y las tablas de viento.
5. Repetir la ingesta con las demás grúas de la flota (el mismo pipeline).
6. Exponer el selector como API/servicio y añadir interfaz de revisión del CSV.

---

## 10. Cómo ejecutar el prototipo

```bash
cd crane_tables
python3 -m tools.build_db  "../LTM-1300-6.3.pdf" db/cranes.db
python3 -m tools.query     db/cranes.db --load 18 --radius 30
python3 -m tools.export    db/cranes.db out/ltm1300-6.3.csv
python3 -m tools.import_csv db/reviewed.db out/ltm1300-6.3.csv
```

Dependencias: `poppler-utils` (`pdftotext`, `pdftocairo`) y Python 3 (solo
biblioteca estándar; `numpy`/`Pillow` solo para las utilidades de verificación).

---

## 11. Prueba de integración de un segundo equipo (LTM 1450-8.1, 450 t)

Se ejecutó el mismo pipeline sobre `LTM-1450-8.1.pdf` (90 págs, ~60 tablas):

- **61 tablas**, **36 378 celdas** extraídas en ~10 s, sin reescribir el
  extractor.
- Para que fuera *plug‑and‑play* solo hicieron falta **dos generalizaciones**:
  1. **Detección genérica de sistema/plumín** desde la etiqueta de la esquina
     (`TK 7`, `TF 17,5`, `TN 84`…). Antes estaba fija para el 1300.
  2. **Agrupación genérica de ángulos**: el 1450 usa `0/10/20/40°` en los TK/TF y
     **ángulos de pluma** `83/75/67°` en los TN; el agrupador anterior solo
     entendía `0/20/40`.
- Ya funcionaban sin cambios: extracción vectorial, reglas de tabla, **sub‑tablas
  apiladas** (el 1450 mete dos por página), encabezados compuestos
  (`16,1 m + 2,3 m*`), BD, validador y selector.
- **Totalmente reutilizable:** el único ajuste por modelo que queda es un
  override de 6 líneas para el 1300 (sus páginas TK/TNZK no llevan la longitud
  del plumín en la etiqueta).

**Sobre el validador:** el 1450 reporta 1 610 alertas de monotonía, pero se
verificó contra la fuente (p. ej. p18 y p28) y **son reales del manual** —esta
grúa tiene muchas columnas de pluma corta limitadas por geometría donde la
capacidad *crece* con el radio—. Es decir, la monotonía estricta sobre‑marca en
este modelo y conviene hacerla *model‑aware* o cruzarla con una extracción
independiente.

**Resultado de flota** para el caso *50 t a 15 m y 23 m de altura*:

| Grúa | Mejor capacidad | Veredicto |
|---|---|---|
| LTM 1300‑6.3 | 49,35 t netas (pluma 29,6 m) | **no cumple** (−0,65 t) |
| LTM 1450‑8.1 | **91,55 t** (pluma 26,6 m, 134 t contrapeso) | **cumple con holgura** |

```bash
python3 -m tools.build_fleet db/fleet.db
python3 -m tools.query db/fleet.db --load 50 --radius 15 --height 23
```

Esto es exactamente «elegir el tonelaje idóneo entre muchos equipos»: una
búsqueda determinista sobre la flota, con trazabilidad a la tabla y página de
origen.
