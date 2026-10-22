# Guía: crear una base de datos de staging

Guía reutilizable para añadir un entorno de **staging** a un proyecto que hoy
solo tiene producción. Sirve para cualquiera de los proyectos con Supabase +
Vercel (CalculoHoras, CalculoValorKm, SistemaRemesa, SeleccionGruas…).

> Regla de oro: **staging es un proyecto Supabase aparte**. No es un esquema
> dentro de la base de producción.

---

## 0. Antes de empezar

- Identifica el proyecto y su archivo de esquema (`supabase-setup.sql`,
  `supabase/schema.sql`, migraciones, etc.).
- Ten a mano el proyecto de **producción** solo como referencia. **No** uses sus
  claves en local ni en staging.
- Decide el nombre: `<proyecto>-staging`.

## 1. Crear el proyecto Supabase de staging

1. Supabase → **New project**.
2. Nombre: `<proyecto>-staging`.
3. Región: la misma que producción (menos latencia y comportamiento similar).
4. Contraseña fuerte y guardada en un gestor de contraseñas.
5. Anota:
   - **Project URL** → `https://<ref>.supabase.co`
   - **anon key** (pública)
   - **service_role key** (secreta; solo scripts/administración)

> El plan Free permite normalmente 2 proyectos activos por organización:
> staging + producción. Si necesitas más, valora el plan Pro.

## 2. Aplicar el esquema

**Opción A — SQL Editor (rápida)**

1. Abre el SQL Editor del proyecto de staging.
2. Pega y ejecuta el esquema del proyecto
   (`supabase-setup.sql` / `supabase/schema.sql`).
3. Verifica que se crearon tablas, funciones, políticas RLS y buckets.

**Opción B — Supabase CLI (recomendada a medio plazo)**

```bash
npx supabase link --project-ref <ref-staging>
npx supabase db push
```

Así el esquema queda versionado y se puede replicar en producción.

## 3. Cargar datos

- **Datos de referencia** (catálogos, tablas de carga): pueden ser los mismos que
  producción.
- **Datos de usuarios, facturas, remesas, búsquedas**: **no** copies producción.
  Usa datos sintéticos o anonimizados.
- Crea un `seed` de staging separado del de producción.

## 4. Configurar Auth en staging

- Crea usuarios de prueba (administrador y operador).
- Configura las **Redirect URLs** con el dominio de preview/staging.
- No reutilices usuarios ni contraseñas de producción.
- Revisa las plantillas de email (usa un remitente de pruebas).

## 5. Configurar la aplicación

| Entorno | Dónde van las variables |
|---|---|
| Local | `.env.local` (ignorado por git) |
| Preview / staging | Vercel → Environment Variables → **Preview** |
| Producción | Vercel → Environment Variables → **Production** |

Variables típicas:

```dotenv
SUPABASE_URL=https://<ref-staging>.supabase.co
SUPABASE_ANON_KEY=<anon-staging>
# Solo scripts locales/administración:
SUPABASE_SERVICE_ROLE_KEY=<service-role-staging>
```

- **Nunca** pongas `service_role` en el frontend.
- En proyectos vanilla sin build, usa un `config.js` generado por entorno o
  carga la configuración desde variables inyectadas en el deploy.
- Si falta `SUPABASE_URL`, la app debe **fallar**, no asumir producción.

## 6. Entorno local

Dos opciones:

1. **Apuntar local a staging** (cómodo para ver datos reales de prueba, pero
   cuidado con escrituras).
2. **Supabase local** (`npx supabase start`): Postgres + Auth + API + Studio en
   Docker. Es lo mejor para probar **login y RLS** sin tocar staging.

## 7. Verificar antes de usar

- [ ] Conteo de tablas y filas coherente.
- [ ] Login con usuario de prueba.
- [ ] RLS: un usuario no ve datos de otro.
- [ ] La app muestra el entorno correcto.
- [ ] Las funciones/RPC responden.
- [ ] El frontend de preview apunta a staging (no a producción).

## 8. Flujo de trabajo

```
rama → PR → Vercel Preview (staging) → revisión + CI → merge a main → producción
```

- Migraciones: **local → staging → producción**.
- Nunca aplicar una migración primero en producción.
- Respaldar antes de cambios destructivos.

---

## ¿Cómo sé qué base de datos está activa en local?

Nunca lo dejes a la memoria. Haz que la app **lo muestre**:

1. **Lee la URL efectiva** de la variable de entorno:
   `SUPABASE_URL` / `VITE_SUPABASE_URL` / `config.js`.
   El subdominio es el *project ref*: `https://<ref>.supabase.co`.
2. **Badge visible** en la interfaz:
   - `LOCAL` (verde), `STAGING` (ámbar), `PRODUCTION` (rojo).
   - Se calcula comparando el host con una lista de refs permitidos.
3. **Log al arrancar** (solo el host/ref, nunca la clave):
   ```
   [env] SUPABASE_URL = https://abcd1234.supabase.co (staging)
   ```
4. **Health check** en la base:
   ```sql
   select current_database(), current_user;
   ```
   y, si quieres, una tabla `app_env` con el nombre del entorno.
5. **Fail-fast**: si no hay URL o no coincide con ningún entorno conocido, la app
   se detiene. No debe caer por defecto en producción.

Ejemplo mínimo en JS vanilla:

```js
const url = window.__ENV__?.SUPABASE_URL;
if (!url) throw new Error('Falta SUPABASE_URL');
const ref = new URL(url).host.split('.')[0];
const known = { '<ref-local>': 'LOCAL', '<ref-staging>': 'STAGING', '<ref-prod>': 'PRODUCTION' };
const env = known[ref] ?? 'DESCONOCIDO';
document.body.dataset.env = env;      // permite estilos por entorno
console.info(`[env] ${env} (${ref})`);
```

## ¿Debo crear dos repositorios para Vercel?

**No.** Un repositorio y **un** proyecto de Vercel con tres entornos:

| Entorno Vercel | Rama / evento | Base de datos |
|---|---|---|
| Development | local | local |
| Preview | cada PR / rama | staging |
| Production | `main` | producción |

- Vercel crea un **preview por PR** automáticamente.
- Cada entorno tiene sus propias **Environment Variables**.
- Dos repositorios duplicarían código y provocarían divergencias.
- Lo que sí son dos (o tres) son las **bases**: local, staging y producción.

## Errores comunes

- Usar el proyecto de producción como staging.
- Copiar `.env` de producción a local.
- Reutilizar la `service_role` de producción.
- Copiar datos personales de producción a staging.
- No mostrar el entorno en la UI y confundirse.
- Ejecutar migraciones primero en producción.
- Compartir usuarios de Auth entre entornos.

## Checklist final

- [ ] Proyecto Supabase `staging` creado y separado de producción.
- [ ] Esquema aplicado y verificado.
- [ ] Datos de prueba cargados (sin datos personales reales).
- [ ] Usuarios de Auth de staging creados.
- [ ] Variables de entorno configuradas en Vercel (Preview) y en local.
- [ ] La app muestra `LOCAL` / `STAGING` / `PRODUCTION`.
- [ ] RLS probado con dos usuarios.
- [ ] Flujo PR → preview → merge documentado.
