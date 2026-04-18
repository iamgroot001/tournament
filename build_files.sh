#!/bin/bash
# Vercel build script

echo ">>> Installing dependencies..."
pip install -r requirements.txt

echo ">>> Running migrations..."
python manage.py migrate --noinput

echo ">>> Collecting static files..."
python manage.py collectstatic --noinput

echo ">>> Creating superuser (if DJANGO_SUPERUSER_* env vars are set)..."
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py createsuperuser --noinput 2>/dev/null || echo "Superuser already exists."
else
    echo "Skipped (env vars not set)."
fi

echo ">>> Build complete!"
