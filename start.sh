#!/usr/bin/env bash

# Run database migrations on startup
python manage.py migrate --noinput

# Start Celery worker in the background
celery -A config worker --loglevel=info --pool=solo --concurrency=1 &

# Start Daphne in the foreground (Render injects $PORT environment variable)
daphne -b 0.0.0.0 -p $PORT config.asgi:application
