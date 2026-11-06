#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

scanner_root="${SCANNER_ROOT:-/opt/scanner}"
compose_file="${SCANNER_COMPOSE_FILE:-${scanner_root}/app/compose.prod.yaml}"
env_file="${SCANNER_ENV_FILE:-${scanner_root}/config/.env}"
backup_dir="${scanner_root}/backups"
timestamp="$(date -u +%Y%m%d-%H%M%S)"
target="${backup_dir}/scanner-${timestamp}.sql.gz"
temporary="${target}.tmp"

mkdir -p "${backup_dir}"
trap 'rm -f "${temporary}"' EXIT

docker compose --env-file "${env_file}" -f "${compose_file}" exec -T scanner-mysql \
  sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysqldump -uroot --single-transaction --routines --triggers --events "$MYSQL_DATABASE"' \
  | gzip -9 > "${temporary}"

test -s "${temporary}"
gzip -t "${temporary}"
mv "${temporary}" "${target}"
trap - EXIT

mapfile -t old_backups < <(find "${backup_dir}" -maxdepth 1 -type f -name 'scanner-*.sql.gz' -printf '%T@ %p\n' | sort -rn | tail -n +13 | cut -d' ' -f2-)
if ((${#old_backups[@]} > 0)); then
  rm -f -- "${old_backups[@]}"
fi

printf 'backup_created=%s\n' "${target}"
