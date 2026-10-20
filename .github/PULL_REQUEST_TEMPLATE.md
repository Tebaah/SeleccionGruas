<!--
Plantilla de pull request de SeleccionGruas.
Borra las secciones que no apliquen; no dejes texto de relleno.
El título del PR debe seguir Conventional Commits, en español:
  feat(motor): añadir filtro por contrapeso máximo
-->

## Descripción

<!-- Qué cambia y por qué. Contexto del problema y enfoque elegido. -->



## Issue relacionado

<!-- Closes #123 / Refs: #123 -->

Closes #

## Tipo de cambio

- [ ] `feat` — nueva funcionalidad
- [ ] `fix` — corrección de bug
- [ ] `docs` — documentación
- [ ] `refactor` — cambio sin cambio de comportamiento
- [ ] `perf` — mejora de rendimiento
- [ ] `test` — pruebas
- [ ] `build` — build o dependencias
- [ ] `ci` — integración continua
- [ ] `chore` — mantenimiento

## ¿Cómo se probó?

<!-- Pasos reproducibles, comandos y resultados. -->

- [ ] `python3 -m compileall -q tools`
- [ ] `python3 -m tools.build_fleet db/fleet.db`
- [ ] `python3 -m tools.export_supabase db/fleet.db supabase`
- [ ] `python3 -m tools.query db/fleet.db --load 50 --radius 15 --height 23`
- [ ] Validación del SQL en PostgreSQL (si aplica)
- [ ] Prueba manual:

## Capturas / evidencia

<!-- Antes/después, GIF, enlace al preview. Si no aplica, escribe "N/A". -->



## Datos / migraciones

<!-- ¿Cambia el esquema? ¿Hay que regenerar seed.sql o recargar Supabase? -->

- [ ] No cambia el esquema.
- [ ] Actualicé `supabase/schema.sql` y regeneré los artefactos.

## Trade-offs / notas

<!-- Impactos conocidos, deuda técnica, alternativas descartadas, plan de rollback. -->



## Checklist

- [ ] El PR tiene un solo propósito.
- [ ] El título sigue Conventional Commits y está en español.
- [ ] Los commits siguen Conventional Commits y están en español.
- [ ] La verificación pasa sin errores.
- [ ] Se actualizó la documentación si aplica.
- [ ] No hay secretos ni datos personales.
- [ ] No incluí PDFs ni artefactos generados (`db/`, `out/`, `supabase/data/`, `seed.sql`).
- [ ] Se respetaron las convenciones del proyecto (idioma, formato).
