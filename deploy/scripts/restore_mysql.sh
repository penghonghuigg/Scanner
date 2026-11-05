#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

if (($# != 2)); then
  printf '用法: %s /absolute/path/backup.sql.gz isolated_database\n' "$0" >&2
  exit 2
fi

backup_file="$(realpath -- "$1")"
restore_database="$2"
scanner_root="${SCANNER_ROOT:-/opt/scanner}"
compose_file="${scanner_root}/app/compose.prod.yaml"
env_file="${scanner_root}/config/.env"

if [[ ! -f "${backup_file}" || "${backup_file}" != *.sql.gz ]]; then
  printf '备份文件不存在或扩展名错误\n' >&2
  exit 2
fi
if [[ ! "${restore_database}" =~ ^[A-Za-z0-9_]+$ ]]; then
  printf '隔离数据库名只允许字母、数字和下划线\n' >&2
  exit 2
fi

gzip -t "${backup_file}"

production_database="$(docker compose --env-file "${env_file}" -f "${compose_file}" exec -T scanner-mysql printenv MYSQL_DATABASE | tr -d '\r')"
if [[ "${restore_database}" == "${production_database}" ]]; then
  printf '拒绝覆盖正式数据库\n' >&2
  exit 2
fi

if docker compose --env-file "${env_file}" -f "${compose_file}" exec -T scanner-mysql \
  sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -Nse "SHOW DATABASES"' \
  | tr -d '\r' | grep -Fxq "${restore_database}"; then
  printf '隔离数据库已存在，拒绝覆盖\n' >&2
  exit 2
fi

printf 'CREATE DATABASE `%s` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;\n' "${restore_database}" \
  | docker compose --env-file "${env_file}" -f "${compose_file}" exec -T scanner-mysql \
      sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot'

gzip -cd -- "${backup_file}" \
  | docker compose --env-file "${env_file}" -f "${compose_file}" exec -T \
      -e RESTORE_DATABASE="${restore_database}" scanner-mysql \
      sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot "$RESTORE_DATABASE"'

docker compose --env-file "${env_file}" -f "${compose_file}" exec -T \
  -e RESTORE_DATABASE="${restore_database}" scanner-mysql \
  sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -Nse "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = '\''$RESTORE_DATABASE'\''"'
