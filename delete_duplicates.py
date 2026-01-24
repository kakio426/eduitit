
import os
import django
from collections import defaultdict

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import Product

def find_duplicates_robust():
    all_products = Product.objects.all().order_by('created_at')
    groups = defaultdict(list)
    
    for p in all_products:
        # Normalize title: strip whitespace and lowercase
        norm_title = p.title.strip().lower()
        groups[norm_title].append(p)
    
    deleted_count = 0
    for norm_title, prods in groups.items():
        if len(prods) > 1:
            print(f"\nProcessing duplicates for: '{prods[0].title}'")
            # Keep the first one (earliest created_at because of order_by)
            keep = prods[0]
            to_delete = prods[1:]
            print(f"  KEEP: ID {keep.id} (Created: {keep.created_at})")
            for p in to_delete:
                print(f"  DELETE: ID {p.id} (Created: {p.created_at})")
                p.delete()
                deleted_count += 1
                
    print(f"\nTotal deleted: {deleted_count}")

if __name__ == "__main__":
    find_duplicates_robust()
