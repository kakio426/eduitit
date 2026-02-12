
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from products.models import Product, ProductFeature

def inspect_exact_features():
    # '간편 수합'이라는 제목이 들어간 모든 상품 조회
    products = Product.objects.filter(title__icontains="간편 수합")
    
    print(f"Found {products.count()} products matching '간편 수합'.")
    
    for p in products:
        print(f"\nProduct: {p.title} (ID: {p.id})")
        features = p.features.all().order_by('id')
        print(f"Total Features: {features.count()}")
        
        # 제목별 카운트
        title_counts = {}
        for f in features:
            title_counts[f.title] = title_counts.get(f.title, 0) + 1
            print(f" - [{f.id}] {f.title}")
            
        print("\nDuplicate Check:")
        has_dup = False
        for title, count in title_counts.items():
            if count > 1:
                has_dup = True
                print(f"!!! DUPLICATE FOUND: '{title}' appears {count} times.")
        
        if not has_dup:
            print("No duplicates found by title string.")

if __name__ == "__main__":
    inspect_exact_features()
