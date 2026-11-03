#!/usr/bin/env bash
set -e

if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

POSTGRES_USER=${POSTGRES_USER:-p1}
POSTGRES_DB=${POSTGRES_DB:-albergues}
MONGO_USER=${MONGO_USER:-p1}
MONGO_PASSWORD=${MONGO_PASSWORD:-cambiame}
MONGO_DB=${MONGO_DB:-albergues}

if [ "$1" == "--restaurar" ]; then
    PASTA_COPIA="$2"
    if [ -z "$PASTA_COPIA" ] || [ ! -d "$PASTA_COPIA" ]; then
        echo "Uso: $0 --restaurar copias/YYYYMMDD_HHMMSS"
        exit 1
    fi

    echo "============================================="
    echo "INICIANDO RESTAURACIÓN DENDE: $PASTA_COPIA"
    echo "============================================="

    FICHEIRO_PG=$(ls $PASTA_COPIA/postgres_*.sql 2>/dev/null | head -n 1)
    if [ -f "$FICHEIRO_PG" ]; then
        echo "Restaurando PostgreSQL desde $FICHEIRO_PG..."
        cat "$FICHEIRO_PG" | docker exec -i ca_postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null
        echo "[OK] PostgreSQL restaurado."
    fi

    FICHEIRO_MONGO=$(ls $PASTA_COPIA/mongo_*.archive 2>/dev/null | head -n 1)
    if [ -f "$FICHEIRO_MONGO" ]; then
        echo "Restaurando MongoDB desde $FICHEIRO_MONGO..."
        docker exec -i ca_mongo mongorestore \
            -u "$MONGO_USER" -p "$MONGO_PASSWORD" \
            --authenticationDatabase admin \
            --nsInclude="${MONGO_DB}.*" \
            --drop \
            --archive < "$FICHEIRO_MONGO" > /dev/null
        echo "[OK] MongoDB restaurado."
    fi

    echo "Restauración finalizada con éxito."
    exit 0
fi

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DESTINO="copias/${TIMESTAMP}"
mkdir -p "$DESTINO"

echo "============================================="
echo "FACENDO COPIA DE SEGURIDADE [${TIMESTAMP}]"
echo "============================================="

echo "Gravando PostgreSQL (pg_dump)..."
docker exec ca_postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "${DESTINO}/postgres_${TIMESTAMP}.sql"

echo "Gravando MongoDB (mongodump)..."
docker exec ca_mongo mongodump \
    -u "$MONGO_USER" -p "$MONGO_PASSWORD" \
    --authenticationDatabase admin \
    --db "$MONGO_DB" \
    --archive > "${DESTINO}/mongo_${TIMESTAMP}.archive"

echo "Copias gardadas correctamente en: ${DESTINO}"