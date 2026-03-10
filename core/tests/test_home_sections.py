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

    def test_counsel_and_insights_services_keep_their_section_keys(self):
        refresh_product = Product(
            title="상담 리프레시",
            description="desc",
            price=0,
            service_type="counsel",
            launch_route_name="studentmbti:landing",
        )
        guide_product = Product(
            title="가이드 인사이트",
            description="desc",
            price=0,
            service_type="edutech",
            launch_route_name="insights:list",
        )

        self.assertEqual(_resolve_home_section_key(refresh_product), "refresh")
        self.assertEqual(_resolve_home_section_key(guide_product), "guide")
