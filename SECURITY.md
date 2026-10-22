# Política de seguridad

## Alcance

Este repositorio contiene el **código** de SeleccionGruas. Los manuales PDF de
los fabricantes, la base de datos generada y los artefactos de carga **no se
versionan** (ver `.gitignore`).

## Reportar una vulnerabilidad

**No abras un issue público.** Usa el reporte privado de GitHub:

- https://github.com/Tebaah/SeleccionGruas/security/advisories/new
- o **Security → Report a vulnerability** en el repositorio.

Incluye, si es posible:

- descripción e impacto,
- pasos para reproducir,
- versión o commit afectado,
- propuesta de mitigación.

## Qué consideramos una vulnerabilidad

- Acceso no autorizado a datos o funciones.
- Fallos en RLS, en la autenticación o en la RPC.
- Exposición de secretos (`service_role`, cadena de conexión, tokens).
- XSS, CSRF, inyección SQL u otras inyecciones.
- Fuga de información en mensajes de error o logs.

## Reglas del proyecto

- Nunca subir al repositorio `.env`, claves, cadenas de conexión ni volcados de datos.
- `service_role` solo en scripts locales o de administración; **nunca** en el
  frontend.
- RLS activo y sin acceso directo a las tablas desde el cliente.
- Revisar dependencias y acciones de CI antes de actualizarlas.
- Los reportes de seguridad se tratan de forma privada hasta que exista un
  parche.
