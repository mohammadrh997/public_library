#!/bin/sh
set -e
alembic upgrade head
exec fastapi run app/main.py --host 0.0.0.0 --port "${PORT:-8000}"
