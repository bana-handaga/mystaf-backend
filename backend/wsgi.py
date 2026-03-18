"""
WSGI config for MyStaf backend.
Compatible with cPanel Python App (JagoanHosting).
"""

import os
import sys

# Tambahkan root project ke sys.path agar Django bisa menemukan module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
