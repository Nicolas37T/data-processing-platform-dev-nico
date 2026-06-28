#!/bin/bash
# Runs once on first PostgreSQL start (empty data directory).
# Creates the three business databases required by the platform.
set -e

COUNTRY="${COUNTRY:-XX}"
echo "=== Initializing business databases for country: ${COUNTRY} ==="

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE platform_db;
    CREATE DATABASE "DATA_DB_${COUNTRY}";
    CREATE DATABASE "DATA_DB_${COUNTRY}_AUX";
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "platform_db" \
    -f /docker-platform-sql/platform_db.sql

echo "=== Business databases ready ==="
