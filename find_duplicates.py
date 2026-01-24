
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import Product
from django.db.models import Count

def find_duplicates():
    duplicates = (
        Product.objects.values('title')
        .annotate(title_count=Count('id'))
        .filter(title_count__gt=1)
    )
    
    if not duplicates:
        print("No duplicates found by title.")
        return

    for entry in duplicates:
        title = entry['title']
        count = entry['title_count']
        print(f"\nDuplicate found: '{title}' ({count} times)")
        
        prods = Product.objects.filter(title=title).order_by('created_at')
        for i, p in enumerate(prods):
            status = "KEEP" if i == 0 else "DELETE"
            print(f"  ID: {p.id} | Created: {p.created_at} | Action: {status}")

if __name__ == "__main__":
    find_duplicates()
