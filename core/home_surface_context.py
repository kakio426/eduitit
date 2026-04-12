from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence


HOME_SURFACE_LEGACY_ALIAS_KEY_MAP = {
    'home_v4_nav_sections': 'home_nav_sections',
    'home_v4_mobile_calendar_first_enabled': 'home_mobile_calendar_first_enabled',
    'home_v4_mobile_quick_items': 'home_mobile_quick_items',
    'home_v5_mobile_workbench_items': 'home_mobile_workbench_items',
    'home_v5_mobile_recommend_items': 'home_mobile_recommend_items',
    'home_v2_frontend_config': 'home_frontend_config',
}


@dataclass(frozen=True)
class HomeSurfaceProviderSpec:
    key: str
    label: str
    fallback_factory: Callable[[], Any]
    builder: Callable[[], Any]


@dataclass(frozen=True)
class HomeSurfaceProviderCards:
    reservation_home_card: Any = None
    developer_chat_home_card: Any = None
    teacher_buddy: Mapping[str, Any] = field(default_factory=dict)
    quickdrop_home_card: Any = None
    calendar: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> 'HomeSurfaceProviderCards':
        return cls(
            reservation_home_card=values.get('reservation_home_card'),
            developer_chat_home_card=values.get('developer_chat_home_card'),
            teacher_buddy=dict(values.get('teacher_buddy') or {}),
            quickdrop_home_card=values.get('quickdrop_home_card'),
            calendar=dict(values.get('calendar') or {}),
        )


@dataclass(frozen=True)
class HomeSurfaceSlots:
    navigation: Mapping[str, Any]
    workbench: Mapping[str, Any]
    recommendations: Mapping[str, Any]
    cards: Mapping[str, Any]
    community: Mapping[str, Any]
    calendar: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            'navigation': dict(self.navigation),
            'workbench': dict(self.workbench),
            'recommendations': dict(self.recommendations),
            'cards': dict(self.cards),
            'community': dict(self.community),
            'calendar': dict(self.calendar),
        }


@dataclass(frozen=True)
class HomeSurfaceTemplateParts:
    products: Sequence[Any]
    sections: Sequence[Any]
    aux_sections: Sequence[Any]
    primary_display_sections: Sequence[Any]
    secondary_display_sections: Sequence[Any]
    games: Sequence[Any]
    favorite_items: Sequence[Mapping[str, Any]]
    recent_items: Sequence[Mapping[str, Any]]
    discovery_items: Sequence[Mapping[str, Any]]
    provider_cards: HomeSurfaceProviderCards
    schoolcomm_home_card: Any
    representative_slots: Sequence[Mapping[str, Any]]
    representative_recommendations: Sequence[Mapping[str, Any]]
    home_nav_sections: Sequence[Mapping[str, Any]]
    home_mobile_section_order: Sequence[str]
    home_mobile_workbench_items: Sequence[Mapping[str, Any]]
    home_mobile_recommend_items: Sequence[Mapping[str, Any]]
    home_frontend_config: Mapping[str, Any]
    home_design_version: str
    community_summary: Mapping[str, Any]
    sns_preview_posts: Sequence[Any]
    home_entry_panel: Any
    page_obj: Any
    pinned_notice_posts: Sequence[Any]
    feed_scope: str
    home_surface_slots: HomeSurfaceSlots
    home_user_mode: str
    home_primary_action: Mapping[str, Any] | None
    home_support_actions: Sequence[Mapping[str, Any]]
    home_empty_action_board: Mapping[str, Any] | None
    home_locked_sections: Sequence[Mapping[str, Any]]
    sns_compose_prefill: str


def build_home_surface_legacy_aliases(
    *,
    home_nav_sections,
    home_mobile_calendar_first_enabled,
    home_mobile_quick_items,
    home_mobile_workbench_items,
    home_mobile_recommend_items,
    home_frontend_config,
    home_v5_mobile_section_order,
):
    neutral_values = {
        'home_nav_sections': home_nav_sections,
        'home_mobile_calendar_first_enabled': home_mobile_calendar_first_enabled,
        'home_mobile_quick_items': home_mobile_quick_items,
        'home_mobile_workbench_items': home_mobile_workbench_items,
        'home_mobile_recommend_items': home_mobile_recommend_items,
        'home_frontend_config': home_frontend_config,
    }
    legacy_values = {
        legacy_key: neutral_values[neutral_key]
        for legacy_key, neutral_key in HOME_SURFACE_LEGACY_ALIAS_KEY_MAP.items()
    }
    legacy_values['home_v5_mobile_section_order'] = home_v5_mobile_section_order
    return legacy_values


def build_home_surface_slots(
    *,
    home_nav_sections,
    home_mobile_section_order,
    favorite_items,
    favorite_products,
    recent_items,
    home_mobile_workbench_items,
    representative_slots,
    representative_recommendations,
    home_mobile_recommend_items,
    discovery_items,
    schoolcomm_home_card,
    provider_cards,
    community_summary,
    sns_preview_posts,
) -> HomeSurfaceSlots:
    return HomeSurfaceSlots(
        navigation={
            'sections': home_nav_sections,
            'mobile_section_order': home_mobile_section_order,
        },
        workbench={
            'favorite_items': favorite_items,
            'favorite_product_ids': [product.id for product in favorite_products],
            'recent_items': recent_items,
            'mobile_items': home_mobile_workbench_items,
        },
        recommendations={
            'representative_slots': representative_slots,
            'representative_recommendations': representative_recommendations,
            'mobile_recommend_items': home_mobile_recommend_items,
            'discovery_items': discovery_items,
        },
        cards={
            'schoolcomm_home_card': schoolcomm_home_card,
            'quickdrop_home_card': provider_cards.quickdrop_home_card,
            'reservation_home_card': provider_cards.reservation_home_card,
            'developer_chat_home_card': provider_cards.developer_chat_home_card,
        },
        community={
            'community_summary': community_summary,
            'sns_preview_posts': sns_preview_posts,
        },
        calendar=dict(provider_cards.calendar),
    )


def build_home_surface_template_context(parts: HomeSurfaceTemplateParts) -> dict[str, Any]:
    return {
        'products': parts.products,
        'sections': parts.sections,
        'aux_sections': parts.aux_sections,
        'primary_display_sections': parts.primary_display_sections,
        'secondary_display_sections': parts.secondary_display_sections,
        'games': parts.games,
        'favorite_items': parts.favorite_items,
        'favorite_product_ids': parts.home_surface_slots.workbench['favorite_product_ids'],
        'recent_items': parts.recent_items,
        'discovery_items': parts.discovery_items,
        'quickdrop_home_card': parts.provider_cards.quickdrop_home_card,
        'schoolcomm_home_card': parts.schoolcomm_home_card,
        'representative_slots': parts.representative_slots,
        'representative_recommendations': parts.representative_recommendations,
        'home_nav_sections': parts.home_nav_sections,
        'home_mobile_section_order': parts.home_mobile_section_order,
        'home_mobile_workbench_items': parts.home_mobile_workbench_items,
        'home_mobile_recommend_items': parts.home_mobile_recommend_items,
        'developer_chat_home_card': parts.provider_cards.developer_chat_home_card,
        'reservation_home_card': parts.provider_cards.reservation_home_card,
        'home_calendar_surface': parts.provider_cards.calendar,
        'home_frontend_config': parts.home_frontend_config,
        'home_design_version': parts.home_design_version,
        'community_summary': parts.community_summary,
        'sns_preview_posts': parts.sns_preview_posts,
        'home_entry_panel': parts.home_entry_panel,
        'posts': parts.page_obj,
        'page_obj': parts.page_obj,
        'pinned_notice_posts': parts.pinned_notice_posts,
        'feed_scope': parts.feed_scope,
        'sns_compose_prefill': parts.sns_compose_prefill,
        'home_surface_slots': parts.home_surface_slots.as_dict(),
        'home_user_mode': parts.home_user_mode,
        'home_primary_action': parts.home_primary_action,
        'home_support_actions': parts.home_support_actions,
        'home_empty_action_board': parts.home_empty_action_board,
        'home_locked_sections': parts.home_locked_sections,
    }
