"""
WSGI config for wcl26 project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wcl26.settings')

application = get_wsgi_application()

# ── Auto-migrate and configure database AT RUNTIME on Vercel ──
from django.core.management import call_command

try:
    # Safely apply migrations to the production Postgres database
    call_command('migrate', interactive=False)
    
    # Auto-create superuser if env vars are present
    if os.environ.get('DJANGO_SUPERUSER_USERNAME') and os.environ.get('DJANGO_SUPERUSER_PASSWORD'):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        
        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username, email, password)
            print(f"Superuser '{username}' created successfully.")
except Exception as e:
    print(f"Startup DB Error: {e}")
