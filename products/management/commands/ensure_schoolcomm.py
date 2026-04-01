from django.core.management.base import BaseCommand

from schoolcomm.services import ensure_service_product


class Command(BaseCommand):
    help = "Ensure schoolcomm product and manual exist in database"

    def handle(self, *args, **options):
        product = ensure_service_product()
        self.stdout.write(self.style.SUCCESS(f"ensure_schoolcomm completed: {product.title}"))
