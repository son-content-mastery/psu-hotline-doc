#!/bin/sh
set -eu

attempt=1
max_attempts="${DATABASE_WAIT_MAX_ATTEMPTS:-30}"
wait_seconds="${DATABASE_WAIT_SECONDS:-2}"

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  until python manage.py migrate --noinput; do
    if [ "$attempt" -ge "$max_attempts" ]; then
      echo "Database migration failed after ${max_attempts} attempts." >&2
      exit 1
    fi

    echo "Database is not ready; retrying migration (${attempt}/${max_attempts})..." >&2
    attempt=$((attempt + 1))
    sleep "$wait_seconds"
  done
fi

if [ "${RUN_DEMO_SEED:-true}" = "true" ]; then
  python manage.py seed_demo
fi

exec "$@"
