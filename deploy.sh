#!/bin/bash
set -e

# Install dependencies
pip install -r requirements.txt

# Run Alembic migrations
alembic upgrade head

# Start the application
exec gunicorn app:app --timeout 60
