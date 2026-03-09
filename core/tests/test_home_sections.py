from django.test import SimpleTestCase

from core.views import _resolve_home_section_key
from products.models import Product


class HomeSectionRoutingTests(SimpleTestCase):
    def test_split_textbook_services_map_to_class_ops(self):
        textbook_product = Product(
            title="교과서 라이브 수업",
            description="desc",
            price=0,
            service_type="classroom",
            launch_route_name="textbooks:main",
        )
        material_product = Product(
            title="교육 자료실",
            description="desc",
            price=0,
            service_type="classroom",
            launch_route_name="edu_materials:main",
        )

        self.assertEqual(_resolve_home_section_key(textbook_product), "class_ops")
        self.assertEqual(_resolve_home_section_key(material_product), "class_ops")
