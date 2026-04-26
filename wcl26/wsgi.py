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

# Run database migrations automatically when Vercel spins up the WSGI container
try:
    from django.core.management import call_command
    call_command('migrate', interactive=False)
except Exception as e:
    print("Migration failed during WSGI init:", str(e))
