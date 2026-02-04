import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import RequestFactory
from products.views import product_preview
from products.models import Product

def test_all_products_preview():
    factory = RequestFactory()
    products = Product.objects.filter(is_active=True)
    
    print(f"Found {products.count()} active products.")
    
    for product in products:
        print(f"Testing preview for: {product.title} (ID: {product.id})")
        request = factory.get(f'/products/preview/{product.id}/')
        try:
            response = product_preview(request, pk=product.id)
            if response.status_code == 200:
                print(f"  [SUCCESS] Status 200")
            else:
                print(f"  [FAILURE] Status {response.status_code}")
                print(response.content.decode('utf-8')[:200])
        except Exception as e:
            print(f"  [ERROR] Exception: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_all_products_preview()
