from django.test import TestCase
from django.contrib.auth.models import User
from products.models import Product, UserOwnedProduct

class OwnershipTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer', password='password123')
        self.product = Product.objects.create(title="Pro Tool", description="Desc", price=100)

    def test_ownership_creation(self):
        ownership = UserOwnedProduct.objects.create(user=self.user, product=self.product)
        self.assertEqual(ownership.user.username, 'buyer')
        self.assertEqual(ownership.product.title, 'Pro Tool')

    def test_user_products_query(self):
        UserOwnedProduct.objects.create(user=self.user, product=self.product)
        self.assertEqual(self.user.owned_products.count(), 1)
        self.assertEqual(self.user.owned_products.first().product, self.product)
