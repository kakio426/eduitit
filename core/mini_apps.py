from __future__ import annotations

from dataclasses import dataclass

from django.urls import NoReverseMatch, reverse

from noticegen.models import TARGET_CHOICES, TOPIC_CHOICES

from .prompt_lab_data import get_prompt_lab_catalog, get_prompt_lab_home_categories


MINI_APP_SUPPORTED_STATES_V1 = (
    "idle",
    "loading",
    "success",
    "empty",
    "error",
    "auth-needed",
)
MINI_APP_ACTIONS_V1 = (
    "run",
    "copy",
    "reset",
    "open_full",
)
HOME_SURFACE_WORKBENCH = "workbench"
HOME_SURFACE_ACTION = "action"
HOME_SURFACE_SERVICE_BOARD = "service-board"
HOME_SURFACE_CONTENT = "content"
HOME_LAYOUT_QUICK = "quick"
HOME_LAYOUT_STARTER = "starter"
HOME_LAYOUT_EXCLUDED = "excluded"
HOME_OVERFLOW_PROMOTE = "promote"
HOME_OVERFLOW_EXCLUDE = "exclude"
HOME_PREVIEW_KIND_TEXT = "text"
HOME_PREVIEW_KIND_QR = "qr"


@dataclass(frozen=True)
class MiniAppField:
    name: str
    type: str
    label: str
    required: bool = False
    choices: tuple[tuple[str, str], ...] = ()
    mobile_priority: int = 1
    placeholder: str = ""
    rows: int = 0


@dataclass(frozen=True)
class MiniAppState:
    status: str = "idle"
    message: str = ""
    preview_text: str = ""
    copy_value: str = ""
    meta: tuple[str, ...] = ()
    available_actions: tuple[str, ...] = MINI_APP_ACTIONS_V1


@dataclass(frozen=True)
class MiniAppDefinition:
    key: str
    source_type: str
    match_key: str
    title: str
    summary: str
    full_url_name: str
    mode: str
    fields: tuple[MiniAppField, ...]
    primary_action_label: str
    preview_kind: str
    requires_auth: bool
    supported_states: tuple[str, ...] = MINI_APP_SUPPORTED_STATES_V1
    body_template: str = ""
    icon: str = "fa-solid fa-sparkles"
    full_label: str = "전체 보기"
    idle_message: str = ""
    home_surface: str = HOME_SURFACE_ACTION
    layout_kind: str = HOME_LAYOUT_QUICK
    home_priority: int = 100
    overflow_behavior: str = HOME_OVERFLOW_PROMOTE


@dataclass(frozen=True)
class HomePlacementEntry:
    key: str
    surface: str
    layout_kind: str
    span: int
    render_variant: str
    full_url: str


@dataclass(frozen=True)
class ActionCardContract:
    layout_kind: str
    max_fields: int
    allowed_preview_kinds: tuple[str, ...]


HOME_ACTION_CARD_CONTRACTS = {
    HOME_LAYOUT_QUICK: ActionCardContract(
        layout_kind=HOME_LAYOUT_QUICK,
        max_fields=2,
        allowed_preview_kinds=(HOME_PREVIEW_KIND_TEXT, HOME_PREVIEW_KIND_QR),
    ),
    HOME_LAYOUT_STARTER: ActionCardContract(
        layout_kind=HOME_LAYOUT_STARTER,
        max_fields=3,
        allowed_preview_kinds=(HOME_PREVIEW_KIND_TEXT, HOME_PREVIEW_KIND_QR),
    ),
}


HOME_MINI_APP_DEFINITIONS = (
    MiniAppDefinition(
        key="noticegen",
        source_type="product",
        match_key="noticegen:main",
        title="알림장 & 주간학습 멘트 생성기",
        summary="대상과 주제만 고르면 바로 복사해 쓸 문장을 만듭니다.",
        full_url_name="noticegen:main",
        mode="htmx",
        fields=(
            MiniAppField(
                name="target",
                type="choice",
                label="대상",
                required=True,
                choices=tuple(TARGET_CHOICES),
                mobile_priority=1,
            ),
            MiniAppField(
                name="topic",
                type="choice",
                label="주제",
                required=True,
                choices=tuple(TOPIC_CHOICES),
                mobile_priority=1,
            ),
            MiniAppField(
                name="keywords",
                type="textarea",
                label="전달 사항",
                required=True,
                mobile_priority=2,
                placeholder="예: 수학 3단원 평가, 실내화 지참",
                rows=3,
            ),
        ),
        primary_action_label="문장 만들기",
        preview_kind=HOME_PREVIEW_KIND_TEXT,
        requires_auth=False,
        body_template="core/includes/mini_apps/noticegen_body.html",
        icon="fa-solid fa-pen-nib",
        idle_message="대상과 전달 사항을 적으면 바로 복사할 문장이 나옵니다.",
        layout_kind=HOME_LAYOUT_STARTER,
        home_priority=10,
    ),
    MiniAppDefinition(
        key="qrgen",
        source_type="product",
        match_key="qrgen:landing",
        title="수업 QR 생성기",
        summary="수업 링크 하나만 넣고 QR을 바로 띄웁니다.",
        full_url_name="qrgen:landing",
        mode="alpine",
        fields=(
            MiniAppField(
                name="url",
                type="url",
                label="링크",
                required=True,
                mobile_priority=1,
                placeholder="예: forms.gle/abcd1234",
            ),
        ),
        primary_action_label="QR 만들기",
        preview_kind=HOME_PREVIEW_KIND_QR,
        requires_auth=False,
        body_template="core/includes/mini_apps/qrgen_body.html",
        icon="fa-solid fa-qrcode",
        idle_message="수업 링크를 하나 넣으면 QR 미리보기가 바로 나옵니다.",
        layout_kind=HOME_LAYOUT_QUICK,
        home_priority=20,
    ),
    MiniAppDefinition(
        key="prompt_lab",
        source_type="core",
        match_key="prompt_lab",
        title="AI 프롬프트 레시피",
        summary="카테고리를 고르면 바로 붙여넣을 프롬프트를 추천합니다.",
        full_url_name="prompt_lab",
        mode="static",
        fields=(
            MiniAppField(
                name="category",
                type="choice",
                label="카테고리",
                required=True,
                mobile_priority=1,
            ),
        ),
        primary_action_label="추천 복사",
        preview_kind=HOME_PREVIEW_KIND_TEXT,
        requires_auth=False,
        body_template="core/includes/mini_apps/prompt_lab_body.html",
        icon="fa-solid fa-wand-magic-sparkles",
        idle_message="카테고리를 고르면 추천 프롬프트 1~2개를 바로 볼 수 있습니다.",
        layout_kind=HOME_LAYOUT_QUICK,
        home_priority=30,
    ),
)


def _safe_reverse(route_name):
    try:
        return reverse(route_name)
    except NoReverseMatch:
        return ""


def _sort_home_entries(entries):
    return sorted(
        entries,
        key=lambda entry: (
            entry["home_priority"],
            entry["title"],
        ),
    )


def _resolve_home_action_layout_kind(entry):
    layout_kind = entry.get("layout_kind", HOME_LAYOUT_EXCLUDED)
    if entry.get("home_surface") != HOME_SURFACE_ACTION:
        return layout_kind
    if layout_kind == HOME_LAYOUT_EXCLUDED:
        return HOME_LAYOUT_EXCLUDED

    contract = HOME_ACTION_CARD_CONTRACTS.get(layout_kind)
    if contract is None:
        return HOME_LAYOUT_EXCLUDED

    fields = entry.get("fields") or ()
    preview_kind = entry.get("preview_kind", "")
    if len(fields) > contract.max_fields:
        return HOME_LAYOUT_EXCLUDED
    if preview_kind not in contract.allowed_preview_kinds:
        return HOME_LAYOUT_EXCLUDED
    return layout_kind


def plan_home_action_surface(entries):
    normalized_entries = [
        {
            **entry,
            "layout_kind": _resolve_home_action_layout_kind(entry),
        }
        for entry in entries
    ]
    eligible_entries = [
        entry
        for entry in normalized_entries
        if entry["home_surface"] == HOME_SURFACE_ACTION and entry["layout_kind"] != HOME_LAYOUT_EXCLUDED
    ]
    starters = _sort_home_entries(
        [entry for entry in eligible_entries if entry["layout_kind"] == HOME_LAYOUT_STARTER]
    )
    quick_entries = _sort_home_entries(
        [entry for entry in eligible_entries if entry["layout_kind"] == HOME_LAYOUT_QUICK]
    )
    promote_last_quick = len(quick_entries) % 2 == 1

    planned_entries = []
    for entry in starters:
        placement = HomePlacementEntry(
            key=entry["key"],
            surface=HOME_SURFACE_ACTION,
            layout_kind=HOME_LAYOUT_STARTER,
            span=2,
            render_variant=HOME_LAYOUT_STARTER,
            full_url=entry["full_url"],
        )
        planned_entries.append(
            {
                **entry,
                "placement": placement,
                "span": placement.span,
                "render_variant": placement.render_variant,
            }
        )

    quick_queue = list(quick_entries)
    while quick_queue:
        is_last_unpaired = len(quick_queue) == 1
        entry = quick_queue.pop(0)
        render_variant = (
            "quick-wide"
            if is_last_unpaired and promote_last_quick and entry["overflow_behavior"] == HOME_OVERFLOW_PROMOTE
            else HOME_LAYOUT_QUICK
        )
        span = 2 if render_variant == "quick-wide" else 1
        placement = HomePlacementEntry(
            key=entry["key"],
            surface=HOME_SURFACE_ACTION,
            layout_kind=HOME_LAYOUT_QUICK,
            span=span,
            render_variant=render_variant,
            full_url=entry["full_url"],
        )
        planned_entries.append(
            {
                **entry,
                "placement": placement,
                "span": placement.span,
                "render_variant": placement.render_variant,
            }
        )

    return planned_entries


def build_home_mini_app_entries(product_list):
    product_by_route = {}
    for product in product_list:
        route_name = str(getattr(product, "launch_route_name", "") or "").strip()
        if route_name:
            product_by_route[route_name] = product

    entries = []
    for definition in HOME_MINI_APP_DEFINITIONS:
        product = product_by_route.get(definition.match_key)
        full_url = getattr(product, "launch_href", "") or _safe_reverse(definition.full_url_name)
        icon = getattr(product, "icon", "") or definition.icon
        title = getattr(product, "public_service_name", "") or definition.title
        summary = (
            getattr(product, "home_card_summary", "")
            or getattr(product, "teacher_first_support_label", "")
            or getattr(product, "solve_text", "")
            or definition.summary
        )
        state = MiniAppState(status="idle", message=definition.idle_message)
        entry = {
            "definition": definition,
            "key": definition.key,
            "source_type": definition.source_type,
            "match_key": definition.match_key,
            "title": title,
            "summary": summary,
            "icon": icon,
            "full_url": full_url,
            "full_label": definition.full_label,
            "mode": definition.mode,
            "fields": definition.fields,
            "primary_action_label": definition.primary_action_label,
            "preview_kind": definition.preview_kind,
            "requires_auth": definition.requires_auth,
            "supported_states": definition.supported_states,
            "state": state,
            "body_template": definition.body_template,
            "product": product,
            "product_id": getattr(product, "id", None),
            "home_surface": definition.home_surface,
            "layout_kind": definition.layout_kind,
            "home_priority": definition.home_priority,
            "overflow_behavior": definition.overflow_behavior,
        }
        if definition.key == "noticegen":
            entry.update(
                {
                    "target_choices": tuple(TARGET_CHOICES),
                    "topic_choices": tuple(TOPIC_CHOICES),
                    "default_target": TARGET_CHOICES[0][0],
                    "default_topic": TOPIC_CHOICES[0][0],
                }
            )
        elif definition.key == "qrgen":
            entry["preview_dom_id"] = "home-mini-qr-preview"
        elif definition.key == "prompt_lab":
            entry["prompt_categories"] = get_prompt_lab_home_categories(limit_items=2)
            entry["prompt_catalog"] = get_prompt_lab_catalog()
            entry["catalog_script_id"] = "home-mini-prompt-lab-catalog"
        entries.append(entry)
    return plan_home_action_surface(entries)
