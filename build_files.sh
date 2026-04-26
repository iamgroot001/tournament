#!/bin/bash
# Vercel build script

echo ">>> Installing dependencies..."
python3 -m pip install -r requirements.txt --break-system-packages || pip install -r requirements.txt

echo ">>> Collecting static files..."
python3 manage.py collectstatic --noinput || python manage.py collectstatic --noinput

echo ">>> Running Database Migrations..."
python3 manage.py migrate --noinput || python manage.py migrate --noinput

echo ">>> Build complete!"
