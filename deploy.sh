#!/bin/bash
set -e

# Ensure data directory is writable
DATA_DIR=/opt/render/project/src/data
mkdir -p "$DATA_DIR"
chmod 775 "$DATA_DIR"
echo "Ensured data directory at $DATA_DIR"

# Install dependencies (in case build command changes)
pip install -r requirements.txt

# Run Alembic migrations
echo "Running Alembic migrations..."
alembic upgrade head

# Start the application
echo "Starting application..."
exec gunicorn app:app --timeout 60
