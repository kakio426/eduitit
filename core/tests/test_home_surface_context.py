from django.test import SimpleTestCase

from core.home_surface_context import (
    HomeSurfaceProviderCards,
    HomeSurfaceTemplateParts,
    build_home_surface_legacy_aliases,
    build_home_surface_slots,
    build_home_surface_template_context,
)


class _ProductStub:
    def __init__(self, product_id):
        self.id = product_id


class HomeSurfaceContextTests(SimpleTestCase):
    def test_build_home_surface_legacy_aliases_keeps_legacy_contract(self):
        nav_sections = [{'title': '오늘'}]
        workbench_items = [{'title': '업무'}]
        frontend_config = {'toggleFavoriteUrl': '/favorite/'}
        aliases = build_home_surface_legacy_aliases(
            home_nav_sections=nav_sections,
            home_mobile_calendar_first_enabled=True,
            home_mobile_quick_items=[{'title': '빠른 실행'}],
            home_mobile_workbench_items=workbench_items,
            home_mobile_recommend_items=[{'title': '추천'}],
            home_frontend_config=frontend_config,
            home_v5_mobile_section_order=('workbench', 'calendar'),
        )

        self.assertEqual(aliases['home_v4_nav_sections'], nav_sections)
        self.assertEqual(aliases['home_v5_mobile_workbench_items'], workbench_items)
        self.assertEqual(aliases['home_v2_frontend_config'], frontend_config)
        self.assertEqual(aliases['home_v5_mobile_section_order'], ('workbench', 'calendar'))

    def test_build_home_surface_template_context_uses_typed_provider_cards(self):
        provider_cards = HomeSurfaceProviderCards(
            quickdrop_home_card={'title': '퀵드롭'},
            reservation_home_card={'title': '예약'},
            developer_chat_home_card={'title': '개발자야 도와줘'},
            teacher_buddy={'teacher_buddy_panel': None},
            calendar={'title': '학급 캘린더'},
        )
        slots = build_home_surface_slots(
            home_nav_sections=[{'title': '오늘'}],
            home_mobile_section_order=('workbench', 'calendar'),
            favorite_items=[{'title': '즐겨찾기'}],
            favorite_products=[_ProductStub(1)],
            recent_items=[{'title': '최근'}],
            home_mobile_workbench_items=[{'title': '업무'}],
            representative_slots=[{'title': '대표'}],
            representative_recommendations=[{'title': '추천'}],
            home_mobile_recommend_items=[{'title': '모바일 추천'}],
            discovery_items=[{'title': '탐색'}],
            schoolcomm_home_card={'title': '가정통신문'},
            provider_cards=provider_cards,
            community_summary={'title': '실시간 소통'},
            sns_preview_posts=[{'id': 1}],
        )

        context = build_home_surface_template_context(
            HomeSurfaceTemplateParts(
                products=[],
                sections=[],
                aux_sections=[],
                primary_display_sections=[],
                secondary_display_sections=[],
                games=[],
                favorite_items=[{'title': '즐겨찾기'}],
                recent_items=[{'title': '최근'}],
                discovery_items=[{'title': '탐색'}],
                provider_cards=provider_cards,
                schoolcomm_home_card={'title': '가정통신문'},
                representative_slots=[{'title': '대표'}],
                representative_recommendations=[{'title': '추천'}],
                home_nav_sections=[{'title': '오늘'}],
                home_mobile_section_order=('workbench', 'calendar'),
                home_mobile_workbench_items=[{'title': '업무'}],
                home_mobile_recommend_items=[{'title': '모바일 추천'}],
                home_frontend_config={'toggleFavoriteUrl': '/favorite/'},
                home_design_version='v6',
                community_summary={'title': '실시간 소통'},
                sns_preview_posts=[{'id': 1}],
                home_entry_panel={'title': '첫 진입'},
                page_obj=[],
                pinned_notice_posts=[],
                feed_scope='all',
                home_surface_slots=slots,
                home_user_mode='authenticated',
                home_primary_action={'title': '주요 액션'},
                home_support_actions=[{'title': '보조 액션'}],
                home_empty_action_board={'title': '비어 있음'},
                home_locked_sections=[{'title': '로그인 필요'}],
                sns_compose_prefill='안녕하세요',
            )
        )

        self.assertEqual(context['favorite_product_ids'], [1])
        self.assertEqual(context['developer_chat_home_card']['title'], '개발자야 도와줘')
        self.assertEqual(context['home_calendar_surface']['title'], '학급 캘린더')
        self.assertEqual(
            context['home_surface_slots']['cards']['schoolcomm_home_card']['title'],
            '가정통신문',
        )
