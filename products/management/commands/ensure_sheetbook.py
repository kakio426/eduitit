from django.core.management.base import BaseCommand
from django.db.models import Q

from products.models import Product, ServiceManual


class Command(BaseCommand):
    help = "Retire legacy sheetbook product surfaces from the catalog."

    RETIRED_ROUTE_PREFIX = "sheetbook:"
    RETIRED_PUBLIC_TITLE = "학급 기록 보드"

    def handle(self, *args, **options):
        products = list(
            Product.objects.filter(
                Q(launch_route_name__istartswith=self.RETIRED_ROUTE_PREFIX)
                | (
                    Q(title=self.RETIRED_PUBLIC_TITLE)
                    & (Q(launch_route_name__isnull=True) | Q(launch_route_name__exact=""))
                )
            ).order_by("id")
        )

        if not products:
            self.stdout.write(self.style.SUCCESS("No sheetbook products to retire."))
            return

        retired_count = 0
        unpublished_manual_count = 0
        for product in products:
            update_fields = []
            if bool(getattr(product, "is_active", False)):
                product.is_active = False
                update_fields.append("is_active")
            if bool(getattr(product, "is_featured", False)):
                product.is_featured = False
                update_fields.append("is_featured")
            if (getattr(product, "external_url", "") or "").strip():
                product.external_url = ""
                update_fields.append("external_url")
            if update_fields:
                product.save(update_fields=update_fields)
            retired_count += 1

            manual = ServiceManual.objects.filter(product=product).first()
            if manual is not None and manual.is_published:
                manual.is_published = False
                manual.save(update_fields=["is_published"])
                unpublished_manual_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Retired sheetbook products: {retired_count}, unpublished manuals: {unpublished_manual_count}"
            )
        )
