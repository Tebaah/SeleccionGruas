# Entornos: local, preview y producción

Objetivo: **desarrollar sin tocar producción**, poder probar, ver errores y
promover cambios con un procedimiento claro.

## Principios

1. **Producción es intocable desde local.** Nunca se apunta el entorno de
   desarrollo a la base de datos ni a las claves de producción.
2. **Cada entorno tiene sus propias credenciales.** Local, preview y producción
   no comparten proyecto de Supabase.
3. **Los secretos no viven en git.** Solo en `.env` local o en las variables de
   Vercel/Supabase.
4. **Todo cambio entra por PR.** `main` está protegida; el merge despliega.
5. **Las migraciones se prueban antes.** Staging primero; producción después,
   con respaldo y plan de vuelta atrás.

## Mapa de entornos

| Entorno | Frontend | Base de datos | Para qué |
|---|---|---|---|
| **Local** | `http://localhost:8000` | PostgreSQL en Docker (o Supabase local) | Desarrollo diario |
| **Preview** | URL de Vercel por PR | Proyecto Supabase de *staging* | Revisión y pruebas sin riesgo |
| **Producción** | Vercel Production | Proyecto Supabase de producción | Uso real |

```
feature/* ──PR──► Vercel Preview ──► Supabase staging
                        │
                    revisión + CI
                        │
                     merge a main
                        ▼
                 Vercel Production ──► Supabase producción
```

## Entorno local

### Requisitos

- Python 3.11+
- `poppler-utils` (`pdftotext`, `pdftocairo`)
- Docker
- (Opcional) Node/npm para el frontend y las CLIs de Vercel/Supabase

### Puesta en marcha

```bash
# 1. Variables de entorno
cp .env.example .env
# completa SUPABASE_URL / SUPABASE_ANON_KEY (pueden ser de staging o locales)

# 2. Datos: PDF -> SQLite -> artefactos
cd crane_tables
python3 -m tools.build_fleet db/fleet.db
python3 -m tools.export_supabase db/fleet.db supabase
cd ..

# 3. Base de datos local (PostgreSQL en Docker)
./scripts/local-db.sh

# 4. Frontend (cuando exista la Etapa 5)
python3 -m http.server 8000
```

### Alternativa: Supabase local

Si quieres probar **Auth y RLS** igual que en la nube:

```bash
npx supabase start      # levanta Postgres, Auth, API y Studio en Docker
npx supabase db reset   # aplica migraciones/seed
```

> El `local-db.sh` es más liviano y suficiente para probar SQL y la RPC.
> Supabase local es mejor cuando necesites Auth/RLS reales.

### Ver errores en local

- **Navegador:** consola (F12) y pestaña Network.
- **Pipeline:** salida de `python3 -m tools.*` y logs del contenedor.
- **Base de datos:** `docker exec -it selecciongruas-pg psql -U postgres -d selecciongruas`.
- **SQL:** errores de sintaxis/constraint aparecen en la consola de `psql`.

## Entorno de preview (staging)

- Vercel crea un **deployment por PR** (Preview) automáticamente.
- Ese deployment usa las variables de entorno de **Preview**, que apuntan al
  proyecto Supabase de **staging**.
- Sirve para probar el flujo completo (login, búsqueda, RLS) sin tocar datos
  reales.
- Los datos de staging se cargan con `seed.sql` o `flat.csv`; se pueden
  regenerar en cualquier momento.

### Configurar

1. Crear un proyecto Supabase `selecciongruas-staging`.
2. Cargar `supabase/seed.sql` (o el CSV) en ese proyecto.
3. En Vercel → Settings → Environment Variables → **Preview**:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`

## Entorno de producción

- Vercel Production se actualiza al hacer merge a `main`.
- Supabase producción es un proyecto **separado**; nunca se usa desde local.
- `main` protegida: PR obligatorio, CI verde y revisión.
- Los datos se cargan solo con scripts revisados y respaldo previo.

### Configurar (requiere las cuentas del proyecto)

1. Crear el proyecto Supabase `selecciongruas-prod`.
2. Ejecutar `supabase/schema.sql` y cargar los datos aprobados.
3. En Vercel → Environment Variables → **Production**:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
4. Activar la protección de la rama `main`:
   - Requerir PR y revisión.
   - Requerir el check **CI / calidad**.
   - Prohibir pushes directos.
5. Definir el dominio y probar un smoke test.

> **Estado actual:** el repositorio ya tiene la configuración y el runbook.
> La creación de los proyectos en Supabase y Vercel requiere las cuentas y
> credenciales del propietario.

## Variables de entorno

| Variable | Dónde | ¿Pública? |
|---|---|---|
| `SUPABASE_URL` | Frontend, Vercel | Sí |
| `SUPABASE_ANON_KEY` | Frontend, Vercel | Sí (protegida por RLS) |
| `SUPABASE_SERVICE_ROLE_KEY` | Solo scripts locales/administración | **No** |
| `SUPABASE_DB_URL` | Solo scripts locales/administración | **No** |
| `APP_ENV` | Local | — |

> En un frontend vanilla sin build step, la `anon key` puede publicarse en un
> `config.js`; la `service_role` **nunca** debe llegar al navegador.

## Flujo de trabajo

1. Crear/actualizar la issue en el **Project** (etapa).
2. Crear una rama (`feature/…`, `fix/…`, `chore/…`).
3. Commits en español con Conventional Commits (ver `CONTRIBUTING.md`).
4. Abrir PR → Vercel genera el **preview**.
5. Revisar, probar y esperar CI verde.
6. Merge a `main` → despliegue a **producción**.
7. Verificar el smoke test y mover la issue a **Done**.

## Migraciones y rollback

- Los cambios de esquema se versionan en `crane_tables/supabase/schema.sql`.
- **Nunca** se edita producción a mano sin un script revisado.
- Antes de una migración destructiva:
  1. respaldo,
  2. aplicar en staging,
  3. ventana de mantenimiento,
  4. aplicar en producción,
  5. verificar.
- **Rollback de frontend:** Vercel permite *Instant Rollback* a un deployment
  anterior.
- **Rollback de base de datos:** restaurar el respaldo o aplicar la migración
  inversa preparada.
- No ejecutar `seed.sql` sobre producción sin revisar antes el contenido.

## Observabilidad y errores

- **Vercel:** logs de build y de funciones.
- **Supabase:** logs de API, Postgres y Auth.
- **Navegador:** consola y estados de error de la UI.
- Opcional: **Sentry** (frontend) para agrupar errores.
- Incluir un `request_id` en los errores para poder cruzar frontend y base de
  datos.

## Checklist de promoción

- [ ] CI verde.
- [ ] Probado en local.
- [ ] Probado en el preview con datos de staging.
- [ ] Sin secretos ni artefactos en el diff.
- [ ] Respaldo hecho si hay migración.
- [ ] Smoke test en producción tras el merge.

## Pendiente para cerrar la Etapa 0

- [ ] Crear los proyectos Supabase de staging y producción.
- [ ] Crear/conectar el proyecto de Vercel.
- [ ] Cargar las variables de entorno en cada entorno.
- [ ] Proteger `main` y exigir el check de CI.
- [ ] Probar un PR de punta a punta (preview → merge → producción).
