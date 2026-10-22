#!/usr/bin/env bash
# Levanta un PostgreSQL local en Docker y carga el esquema (y el seed si existe).
# Uso:  ./scripts/local-db.sh
#       PG_PORT=5434 ./scripts/local-db.sh
set -euo pipefail

NAME="${PG_NAME:-selecciongruas-pg}"
PORT="${PG_PORT:-5433}"
DB="${PG_DB:-selecciongruas}"
PW="${PG_PASSWORD:-localdev}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "El contenedor '$NAME' ya existe."
  echo "Para recrearlo: docker rm -f $NAME && ./scripts/local-db.sh"
else
  echo "Levantando PostgreSQL 16 en el puerto $PORT..."
  docker run -d --name "$NAME" \
    -e POSTGRES_PASSWORD="$PW" \
    -e POSTGRES_DB="$DB" \
    -p "$PORT:5432" \
    postgres:16-alpine >/dev/null
fi

echo -n "Esperando a que PostgreSQL esté listo"
for _ in $(seq 1 30); do
  if docker exec "$NAME" pg_isready -U postgres >/dev/null 2>&1; then
    echo " OK"
    break
  fi
  echo -n "."
  sleep 1
done

echo "Cargando esquema..."
docker cp "$ROOT/crane_tables/supabase/schema.sql" "$NAME:/schema.sql"
docker exec "$NAME" psql -U postgres -d "$DB" -q -f /schema.sql

SEED="$ROOT/crane_tables/supabase/seed.sql"
if [ -f "$SEED" ]; then
  echo "Cargando datos (seed.sql)..."
  docker cp "$SEED" "$NAME:/seed.sql"
  docker exec "$NAME" psql -U postgres -d "$DB" -q -f /seed.sql
else
  echo "Aviso: no existe supabase/seed.sql."
  echo "Genera los datos con: cd crane_tables && python3 -m tools.build_fleet db/fleet.db && python3 -m tools.export_supabase db/fleet.db supabase"
fi

cat <<EOF

PostgreSQL local listo:
  host: localhost
  port: $PORT
  db:   $DB
  user: postgres
  pass: $PW

Conexión:  postgresql://postgres:$PW@localhost:$PORT/$DB
Parar:     docker rm -f $NAME
EOF
