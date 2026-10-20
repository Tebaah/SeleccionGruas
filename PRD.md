# PRD — SeleccionGruas (Crane Selector)

**Versión:** 2.0 · alineada con la base de datos y los datos ya extraídos.
**Documentos relacionados:** `SRS.md`, `ANALISIS.md`, `crane_tables/SUPABASE.md`.

---

## 1. Visión del producto

Aplicación web interna para **pre-seleccionar la grúa y la configuración** adecuadas
en maniobras de izaje. Hoy el operador debe abrir manuales PDF, localizar la tabla
de carga y cruzar a mano peso, radio, altura, pluma, plumín, ángulo y contrapeso.
El sistema automatiza esa búsqueda sobre las tablas oficiales ya digitalizadas y
devuelve las configuraciones factibles, ordenadas por la **grúa más pequeña capaz**
de realizar el trabajo.

> **Límite de responsabilidad:** el sistema es una ayuda de **pre-selección**. No
> sustituye el plan de izaje, el estudio de viento/terreno/rigging ni la validación
> final del gruista y del manual oficial del fabricante.

## 2. Problema y propuesta de valor

| Hoy | Con el sistema |
|---|---|
| Buscar en PDFs de cientos de páginas | Un formulario y una tabla de resultados |
| Comparar varias configuraciones a mano | El motor evalúa todas las configuraciones |
| Riesgo de leer la columna/ángulo equivocado | Dato extraído de la celda exacta y trazable |
| No hay registro del criterio usado | Cada resultado cita grúa, tabla y página |

## 3. Usuarios y roles

| Rol | Permisos | Cómo opera |
|---|---|---|
| **Administrador / Data steward** | Cargar y actualizar equipos y tablas de carga | Pipeline **offline**: PDF → extracción → CSV/SQL → Supabase. En el MVP **no** hay CRUD web. |
| **Operador / Lector** | Iniciar sesión y realizar búsquedas | Web; solo lectura. |

## 4. Alcance del MVP

### 4.1 Autenticación
- Login con email y contraseña (Supabase Auth).
- Sesión con expiración configurable (valor inicial propuesto: 8 h de inactividad).
- Sin registro público: los usuarios los crea el administrador.

### 4.2 Formulario de búsqueda

**Obligatorios**
- Peso de la carga (t).
- Radio de trabajo (m, desde el centro de giro).
- Altura de elevación requerida (m, al gancho).

**Opcionales (recomendados)**
- Factor de utilización (p. ej. 75 %). Por defecto, el que defina la empresa.
- Peso del bloque de gancho / aparejo (t), para descontarlo.
- Permitir plumín (sí/no). Por defecto: sí.
- Contrapeso máximo disponible (t).
- Rango de giro admitido (360° / sobre la parte trasera).

### 4.3 Motor de búsqueda
- Evalúa **configuraciones**, no solo modelos: una grúa tiene varias tablas
  (pluma telescópica, plumines TK/TF/TN, strong jib, etc.), cada una con longitudes,
  ángulos y contrapesos.
- Para cada configuración:
  1. interpola la capacidad al radio pedido;
  2. verifica que la **geometría** alcance la altura requerida;
  3. comprueba `capacidad ≥ carga` aplicando el factor de utilización y
     descontando el aparejo.
- Descarta configuraciones fuera de rango o con contrapeso no disponible.

### 4.4 Resultados (hasta 5 opciones)
Columnas mínimas:

| Columna | Contenido |
|---|---|
| Grúa | Modelo y capacidad máxima nominal (p. ej. LTM 1450-8.1, 450 t) |
| Configuración | Sistema + plumín + ángulo (p. ej. `T`, `TK 21`, `TN 84`, `TF 39,5`) |
| Pluma | Longitud de pluma (m) |
| Contrapeso | Contrapeso requerido (t) |
| Capacidad a ese radio | Capacidad tabulada/interpolada (t) |
| Utilización | `carga / capacidad` (%) |
| Altura de gancho | Altura alcanzable a ese radio (m) |
| Fuente | Página/tabla del manual de origen |

**Orden:** `max_capacity_t` ascendente (la grúa más pequeña primero).
**Desempate:** menor contrapeso → menor pluma → mayor margen.

### 4.5 Sin resultados
Si ninguna configuración cumple, el sistema devuelve la **opción más cercana** y la
**modificación mínima** necesaria:
- radio máximo admisible para ese peso/altura;
- peso máximo admisible a ese radio/altura;
- altura máxima admisible;
- o una combinación.

Ejemplo real de aceptación: para 50 t, 15 m de radio y 23 m de altura, el
LTM 1450-8.1 cumple con ~91,6 t de capacidad bruta, mientras que el LTM 1300-6.3
no alcanza (49,4 t netas tras descontar el aparejo).

### 4.6 Trazabilidad
Toda recomendación debe citar **grúa + tabla/página + sistema + configuración**,
para que el operador pueda verificarla contra el manual.

## 5. Datos de partida (base real)

| Grúa | Capacidad máx. | Tablas | Celdas | Sistemas | Contrapesos (t) | Radios (m) | Plumas (m) |
|---|---|---|---|---|---|---|---|
| Liebherr LTM 1300-6.3 | 300 t | 30 | 16 474 | 15 | 22 / 42 / 68 / 77 / 88 | 3 – 94 | 14,7 – 90 |
| Liebherr LTM 1450-8.1 | 450 t | 61 | 36 378 | 34 | 54 / 104 / 134 | 3 – 108 | 16,1 – 85 |
| **Total** | | **91** | **52 852** | | | | |

Sistemas cubiertos: pluma telescópica (`T`), plumines `TK`, `TF`, `TN`,
`TK/TNZK`, `TVK/TVNZK`, strong jib (`TS`) y celosía fija (`TNZF`).

## 6. Reglas de negocio y seguridad (no negociables)

1. **El dato almacenado es el del manual** (capacidad nominal según EN 13000), **sin
   factores añadidos**. Cualquier margen se aplica en la consulta.
2. El **factor de utilización** (p. ej. 0,75) es un parámetro **configurable y
   visible**; no se hornea en la base de datos.
3. **Descontar el peso del bloque de gancho/aparejo** de la capacidad.
4. La **altura se verifica con geometría**; no se compara "pluma ≥ altura".
5. La columna `*` (trabajo **sobre la parte trasera**) no se usa por defecto.
6. El **viento** y las condiciones de terreno quedan fuera del MVP; el resultado es
   orientativo y la decisión final es del gruista.

## 7. Fuera de alcance (primera versión)

- Disponibilidad real de equipos (arriendo/mantenimiento).
- Exportación a PDF/Excel y generación de cotizaciones.
- Historial de búsquedas.
- CRUD de datos desde la interfaz web.
- Plan de izaje completo (viento, terreno, rigging, permisos).
- Multi-empresa / multi-obra.

## 8. Supuestos y dependencias

- Manuales oficiales en PDF; un PDF por modelo.
- La ingesta es **offline** y se repite al añadir/actualizar una grúa.
- Supabase (Postgres + Auth) y Vercel para el frontend.
- La precisión depende de la calidad del manual y de la validación de la extracción.

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| Celda mal extraída | Validador estructural + revisión de celdas marcadas |
| Manual desactualizado | `source_pdf` versionado y fecha de ingesta |
| Uso indebido en campo | Aviso de pre-selección + trazabilidad a la página |
| Política de margen mal configurada | Factor explícito en la consulta y visible en el resultado |
| Geometría con supuestos | Parámetros por grúa y contraste con el diagrama de alturas del manual |

## 10. Criterios de aceptación del MVP

1. **Caso real:** 50 t / 15 m / 23 m → el LTM 1450-8.1 aparece como factible y el
   LTM 1300-6.3 no.
2. La búsqueda responde en **< 800 ms** (p95).
3. Ningún usuario puede leer las tablas de carga directamente (solo RPC).
4. Cada fila de resultado incluye **fuente** (grúa/página).
5. Con 0 resultados, se muestra una **sugerencia cuantificada** de ajuste.
