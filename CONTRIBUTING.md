# Guía de contribución

Convenciones del proyecto **SeleccionGruas**. El objetivo es que el historial y
las revisiones sean fáciles de entender para el equipo.

## Idioma

- **Todo en español**: commits, pull requests, documentación, comentarios y
  mensajes de la interfaz.
- **Excepción:** los tipos de Conventional Commits (`feat`, `fix`, `docs`…) y los
  nombres de código/API se mantienen en inglés, porque son palabras clave que
  usan las herramientas (changelog, SemVer, linters).

## Commits

Formato:

```text
<tipo>[ámbito opcional]: <descripción en español>

[cuerpo opcional en español]
```

Reglas:

- Descripción en **infinitivo** (`añadir`, `corregir`, `eliminar`), minúscula y
  sin punto final.
- Máximo recomendado: 50 caracteres; máximo 72.
- Un commit = un cambio lógico.
- El cuerpo explica **por qué**, no repite el diff.
- Los issues van en pies (`Closes #123`, `Refs: #123`).

Tipos:

| Tipo | Cuándo |
|---|---|
| `feat` | Nueva funcionalidad visible |
| `fix` | Corrección de un bug |
| `docs` | Solo documentación |
| `style` | Formato sin cambio de comportamiento |
| `refactor` | Reorganización sin cambio de comportamiento |
| `perf` | Mejora de rendimiento |
| `test` | Pruebas |
| `build` | Build o dependencias |
| `ci` | Integración continua |
| `chore` | Mantenimiento |
| `revert` | Revertir un commit |

Ámbitos sugeridos (estables): `ingesta`, `db`, `motor`, `web`, `seguridad`,
`docs`.

Ejemplos:

```text
feat(motor): añadir cálculo de altura de gancho
fix(ingesta): corregir agrupación de ángulos de pluma
docs(srs): alinear el modelo de datos con el esquema real
refactor(db): separar la carga CSV del exportador SQL
chore(repo): ignorar artefactos generados
```

Cambios incompatibles:

```text
feat(db)!: cambiar la clave de las tablas de carga

BREAKING CHANGE: chart pasa a identificarse por (crane_id, page) en lugar de
por el contrapeso.
```

## Ramas

```text
feature/<descripcion-corta>
fix/<descripcion-corta>
docs/<descripcion-corta>
chore/<descripcion-corta>
```

- Una rama = un propósito.
- Slug en español, minúsculas y guiones: `feature/buscador-gruas`.
- No reescribas ramas compartidas sin coordinarlo.

## Pull requests

- **Un PR = un propósito.** No mezcles refactor, feature, fix y formateo.
- **Título** con Conventional Commits, en español:
  `feat(motor): añadir filtro por contrapeso máximo`.
- Usa la plantilla `.github/PULL_REQUEST_TEMPLATE.md`.
- Enlaza el issue (`Closes #123` / `Refs: #123`).
- Si el PR supera ~400 líneas netas, considera dividirlo.
- Abre como **Draft** si aún no está listo.
- Al mergear con **squash**, el título del PR se convierte en el commit: debe
  cumplir el formato.

Antes de pedir revisión:

- [ ] Leí mi propio diff completo.
- [ ] El alcance coincide con el título y el issue.
- [ ] No hay archivos accidentales, secretos ni artefactos generados.
- [ ] Ejecuté la verificación (ver abajo).
- [ ] Actualicé la documentación si aplica.

## Verificación

No hay suite de tests formal todavía. Como mínimo:

```bash
cd crane_tables

# Sintaxis de los módulos
python3 -m compileall -q tools

# Reconstruir la base (requiere los PDF en la raíz del repo)
python3 -m tools.build_fleet db/fleet.db

# Exportar artefactos de Supabase
python3 -m tools.export_supabase db/fleet.db supabase

# Consulta de humo
python3 -m tools.query db/fleet.db --load 50 --radius 15 --height 23
```

Si el cambio toca el esquema o la carga, valida también el SQL contra un
PostgreSQL local (Docker) antes de abrir el PR.

Para cambios solo de documentación, revisa los enlaces y la coherencia con
`PRD.md` / `SRS.md`.

## Datos y artefactos

- **No se versionan**: PDFs del fabricante, `crane_tables/db/`, `out/`,
  `supabase/data/` ni `seed.sql`. Están en `.gitignore`.
- Los PDFs deben colocarse en la raíz del repo para poder reconstruir la base.
- Si cambia el esquema, actualiza `schema.sql` y regenera los artefactos con
  `export_supabase`.
- No incluyas credenciales, `service_role` ni cadenas de conexión.

## Checklist final

- [ ] El idioma es español (salvo tipos y código).
- [ ] Los commits siguen Conventional Commits.
- [ ] El PR tiene un solo propósito y un título claro.
- [ ] La verificación pasa.
- [ ] La documentación está actualizada.
- [ ] No hay secretos ni artefactos generados.
