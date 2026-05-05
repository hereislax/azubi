#!/bin/bash
# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
#
# Legt die Paperless-NGX-Datenbank im gemeinsamen Postgres-Cluster an.
# Wird beim erstmaligen Start des Postgres-Containers automatisch ausgeführt.
# Bei bereits initialisierten Clustern manuell ausführen:
#   docker compose exec db psql -U $DB_USER -c 'CREATE DATABASE paperless;'
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE paperless;
    GRANT ALL PRIVILEGES ON DATABASE paperless TO $POSTGRES_USER;
EOSQL
