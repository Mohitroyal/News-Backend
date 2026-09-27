import os
import sys
from pathlib import Path

# Add the Django project to the Python path
django_path = Path(__file__).resolve().parent.parent / "Spotnewsv2" / "backend" / "spotnews_django"
sys.path.append(str(django_path))

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Import and get the ASGI application
from django.core.asgi import get_asgi_application

app = get_asgi_application()
