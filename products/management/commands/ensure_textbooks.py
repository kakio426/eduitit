from django.core.management.base import BaseCommand
from products.models import ManualSection, Product, ProductFeature, ServiceManual

class Command(BaseCommand):
    help = "Ensure textbooks (Education Materials) product and manual exist in database"

    # '\uAD50\uC721 \uC790\uB8CC\uC2E4' = '교육 자료실'
    PRODUCT_TITLE = '\uAD50\uC721 \uC790\uB8CC\uC2E4'
    LAUNCH_ROUTE = "textbooks:main"

    def handle(self, *args, **options):
        # 1. Product cleaning for any corrupted entries
        Product.objects.filter(launch_route_name=self.LAUNCH_ROUTE).exclude(title=self.PRODUCT_TITLE).delete()
        Product.objects.filter(title__icontains='\u0624').delete() # Common corruption char ڷ

        product = Product.objects.filter(launch_route_name=self.LAUNCH_ROUTE).first()
        if not product:
            product = Product.objects.filter(title=self.PRODUCT_TITLE).first()

        lead_text = '\uBC14\uC774\uBE0C \uCF54\uB529\uC73C\uB8DC \uAD50\uC2E4\uB9CC\uC758 \uC778\uD130\uB799\uD2F0\uBE0C\uD55C \uC790\uB8CC\uB97C \uBC30\uD3EC\uD558\uC138\uC694.'
        description = (
            "\uAD50\uC721 \uC790\uB8CC\uC2E4\uC740 AI \uD504\uB86C\uD504\uD2B8\uB97C \uD1B5\uD574 3D \uD0DC\uC591\uACC4, \uC9C0\uAD6C\uBC38 \uB4F1 \uBCF5\uC7A1\uD55C \uC218\uC5C5 \uB304\uAD6C\uB97C "
            "\uB2E8\uC77C HTML \uCF54\uB4DC\uB8DC \uC0DD\uC131\uD558\uACE0, \uC774\uB97C \uD559\uC0DD\uB4E4\uC5D0\uACAC QR\uCF54\uB4DC\uB8DC \uC989\uC2DC \uBC30\uD3EC\uD560 \uC218 \uC748\uB294 \uC11C\uBE44\uC2A4\uC785\uB2C8\uB2E4. "
            "\uC804\uAD6D \uC120\uC11D\uB2D8\uB4E4\uACFC \uC790\uB8CC\uB97C \uAC35\uC720\uD558\uACE0 \uD559\uAE09 \uCE98\uB9B0\uB354\uC640\uB3C4 \uBC14\uB8DC \uC5F0\uACC4\uB429\uB2C8\uB2E4."
        )

        if product is None:
            product = Product.objects.create(
                title=self.PRODUCT_TITLE,
                lead_text=lead_text,
                description=description,
                price=0.00,
                is_active=True,
                is_featured=True,
                is_guest_allowed=True,
                icon='\U0001F4DA', # 📚
                color_theme="green",
                card_size="small",
                display_order=15,
                service_type="classroom",
                external_url="",
                launch_route_name=self.LAUNCH_ROUTE,
            )
            self.stdout.write(self.style.SUCCESS(f"Created product: {product.title}"))
        else:
            updated_fields = []
            if product.title != self.PRODUCT_TITLE:
                product.title = self.PRODUCT_TITLE
                updated_fields.append("title")
            if product.launch_route_name != self.LAUNCH_ROUTE:
                product.launch_route_name = self.LAUNCH_ROUTE
                updated_fields.append("launch_route_name")
            if product.icon != '\U0001F4DA':
                product.icon = '\U0001F4DA'
                updated_fields.append("icon")
            if not product.is_active:
                product.is_active = True
                updated_fields.append("is_active")
            if updated_fields:
                product.save(update_fields=updated_fields)
                self.stdout.write(
                    self.style.SUCCESS(f"Updated product essentials: {', '.join(updated_fields)}")
                )
            else:
                self.stdout.write(self.style.SUCCESS(f"Product already exists: {product.title}"))

        feature_specs = [
            {
                "icon": "\u2728", # ✨
                "title": "\uBC14\uC774\uBE0C \uCF54\uB529 & AI \uB3C4\uC6B0\uBBF8",
                "description": "\uBCF5\uC7A1\uD55C \uCF54\uB529 \uC5C6\uC774 \uD504\uB86C\uD504\uD2B8\uB9CC\uC73C\uB8DC \uC544\uC774\uB4E4\uC774 \uC88B\uC544\uD560 \uB9CC\uD55C \uC778\uD130\uB799\uD2F0\uBE0C \uC790\uB8CC\uB97C \uC0DD\uC131\uD569\uB2C8\uB2E4.",
            },
            {
                "icon": "\U0001F4C7", # 🔗
                "title": "QR \uCF54\uB4DC \uC989\uC2DC \uBC30\uD3EC",
                "description": "\uB9CC\uB4E0 \uC790\uB8CC\uB97C QR\uCF54\uB4DC\uB8DC \uD744\uC6B0\uAC70\uB098 \uD559\uC2B5\uC9C0\uC5D0 \uBD80\uCC29\uD560 \uC218 \uC748\uB294 \uC704\uC82F\uC73C\uB8DC \uBC14\uB8DC \uBCF5\uC0AC\uD569\uB2C8\uB2E4.",
            },
            {
                "icon": "\U0001F4C5", # 📅
                "title": "\uD559\uAE09 \uCE98\uB9B0\uB354 \uC608\uC57D",
                "description": "\uC218\uC5C5 \uC77C\uC815\uC744 \uC608\uC57D\uD558\uBA74 \uD559\uAE09 \uCE98\uB9B0\uB354(Sheetbook)\uC5D0 \uB9C1\uD0AC\uC640 \uD568\uAED8 \uC790\uB3D9 \uB4F1\uB85D\uB429\uB2C8\uB2E4.",
            },
            {
                "icon": "\U0001F916", # 🤖
                "title": "AI \uD615\uC131\uD3C9\uAC00 \uD034\uC988",
                "description": "\uB525\uC2DC\uD03C AI\uAC00 \uC790\uB8CC \uB0B4\uC6A9\uC744 \uBC14\uD0D5\uC73C\uB8DC \uC544\uC774\uB4E4\uC744 \uC704\uD55C O/X \uD034\uC988\uB97C \uC790\uB3D9\uC73C\uB8DC \uCD9C\uC81C\uD569\uB2C8\uB2E4.",
            },
        ]
        for item in feature_specs:
            feature, created = ProductFeature.objects.get_or_create(
                product=product,
                title=item["title"],
                defaults={
                    "icon": item["icon"],
                    "description": item["description"],
                },
            )
            if not created:
                feature.icon = item["icon"]
                feature.description = item["description"]
                feature.save()

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "\uAD50\uC721 \uC790\uB8CC\uC2E4 \uC0AC\uC6A9 \uAC00\uC774\uB4DC",
                "description": "\uC790\uB8CC \uC0DD\uC131\uBD80\uD130 \uD559\uC0DD \uBC30\uD3EC, \uCE98\uB9B0\uB354 \uC5F0\uACC4\uAE4C\uC9C0\uC758 \uD744\uB984\uC744 \uC548\uB0B4\uD569\uB2C8\uB2E4.",
                "is_published": True,
            },
        )

        section_specs = [
            ("\uC790\uB8CC \uC0DD\uC131\uD558\uAE40", "AI \uD504\uB86C\uD504\uD2B8 \uB3C4\uC6B0\uBBF8\uC758 \uB3C4\uC6C0\uC744 \uBC1B\uC544 \uC218\uC5C5 \uC8FC\uC81C\uC5D0 \uB9DE\uB294 HTML \uCF54\uB4DC\uB97C \uC0DD\uC131\uD558\uACE0 \uB4F1\uB85D\uD558\uC138\uC694.", 1),
            ("\uD559\uC0DD \uBC30\uD3EC(QR)", "\uC791\uC131\uB41C \uC790\uB8CC\uB97C \uD559\uC0DD \uAC1C\uBCC4 \uAE30\uAE30\uB8DC \uC804\uC11D\uD558\uAE30 \uC704\uD574 \uD654\uBA74\uC5D0 QR \uCF54\uB4DC\uB97C \uD744\uC6B0\uAC70\uB098 \uCD9C\uB825\uC6A9 \uC704\uC82F\uC744 \uBC1F\uC0AC\uD558\uC138\uC694.", 2),
            ("\uC218\uC5C5 \uC608\uC57D & \uAC35\uC720", "\uC218\uC5C5 \uB0A0\uC9DC\uB97C \uC9C0\uC815\uD558\uC5EC \uD559\uAE09 \uCE98\uB9B0\uB354\uC5D0 \uC5F0\uACC4\uD558\uACE0, \uB2E4\uB978 \uC120\uC11D\uB2D8\uB4E4\uACFC \uC790\uB8CC\uB97C \uAC35\uC720\uD574 \uBC34\uC138\uC694.", 3),
        ]
        for title, content, display_order in section_specs:
            ManualSection.objects.update_or_create(
                manual=manual,
                title=title,
                defaults={
                    "content": content,
                    "display_order": display_order,
                },
            )

        self.stdout.write(self.style.SUCCESS("ensure_textbooks completed"))
