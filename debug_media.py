import os
import django
from django.conf import settings

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from portfolio.models import Achievement

def check_media_urls():
    print(f"DEBUG: {settings.DEBUG}")
    print(f"USE_CLOUDINARY: {getattr(settings, 'USE_CLOUDINARY', 'N/A')}")
    print(f"DEFAULT_FILE_STORAGE: {getattr(settings, 'DEFAULT_FILE_STORAGE', 'N/A')}")
    if hasattr(settings, 'STORAGES'):
        print(f"STORAGES: {settings.STORAGES}")
    
    achievements = Achievement.objects.all()
    if not achievements:
        print("No achievements found in database.")
        return

    for ach in achievements:
        print(f"--- {ach.title} ---")
        if ach.image:
            print(f"Image instance: {ach.image}")
            try:
                print(f"URL: {ach.image.url}")
            except Exception as e:
                print(f"URL ERROR: {e}")
        else:
            print("No image.")

if __name__ == "__main__":
    check_media_urls()
