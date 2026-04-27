from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Callable


MESSAGE_CAPTURE_PLACEHOLDER = "__capture_id__"
MESSAGE_CAPTURE_REVERSE_SEED = "00000000-0000-0000-0000-000000000000"


@dataclass(frozen=True)
class HomeAgentServiceDefinition:
    key: str
    label: str
    service_key: str
    renderer_key: str
    adapter_key: str
    preview_strategy: str
    selector_hint: str
    tool_key: str
    aliases: tuple[str, ...] = ()
    icon_class: str = "fa-regular fa-circle"
    action_kind: str = ""
    copy: dict = field(default_factory=dict)
    ui: dict = field(default_factory=dict)
    messenger_flow_key: str = "one-shot"
    messenger_capabilities: dict = field(default_factory=dict)
    messenger_ui: dict = field(default_factory=dict)
    links: dict = field(default_factory=dict)
    capabilities: dict = field(default_factory=dict)
    runtime_spec: dict = field(default_factory=dict)
    starter_items: tuple[dict, ...] = ()
    starter_provider_key: str = ""
    conversation_actions: tuple[dict, ...] = ()


def _starter_items(*items):
    return tuple(dict(item) for item in items)


HOME_AGENT_SERVICE_DEFINITIONS = (
    HomeAgentServiceDefinition(
        key="notice",
        label="알림장",
        service_key="noticegen",
        renderer_key="notice",
        adapter_key="notice",
        preview_strategy="service",
        selector_hint="안내 문장",
        tool_key="notice",
        aliases=("알림장", "알림", "가정통신문"),
        icon_class="fa-solid fa-note-sticky",
        messenger_flow_key="one-shot",
        messenger_capabilities={
            "starter_chips": True,
            "copy_result": True,
            "open_link": True,
            "refine": True,
        },
        messenger_ui={
            "flow_variant": "notice",
            "assistant_title": "알림장 초안",
            "reset_label": "새로 쓰기",
        },
        copy={
            "service_label": "알림장 열기",
            "submit_label": "알림 문구 생성",
            "confirm_label": "알림장 열기",
            "helper": "알림장 초안",
            "usage_hint": "보낼 내용을 적으면 학부모용 알림 문구를 바로 정리합니다.",
            "placeholder": "보낼 내용을 적으세요.",
        },
        ui={
            "empty_prompt": "무엇을 보낼까요?",
            "preview_line_limit": 6,
            "refinement_actions": (
                {"label": "짧게", "instruction": "위 내용을 더 짧게 다시 써 주세요."},
                {"label": "부드럽게", "instruction": "위 내용을 더 부드럽게 다시 써 주세요."},
            ),
        },
        links={
            "service_href": {"source": "tool", "key": "notice", "field": "href"},
            "continue_query_fields": (
                {"param": "keywords", "source": "workspace_input"},
            ),
        },
        capabilities={
            "preview": True,
            "notice_refinement": True,
        },
        runtime_spec={
            "badge": "알림장",
            "default_title": "알림장 초안",
            "default_note": "보내기 전 말투만 한 번 더 보면 됩니다.",
            "section_titles": ("핵심", "확인"),
            "instruction": (
                "교사가 학부모와 학생에게 바로 보낼 알림장 초안을 정리합니다. "
                "시간 변경, 준비물, 회신 필요 내용을 먼저 드러내고 문장은 짧게 유지하세요. "
                "첫 번째 sections.items에는 바로 보낼 알림장 문장만 넣고, 설명이나 검토 문구는 넣지 마세요."
            ),
        },
        starter_provider_key="notice",
        conversation_actions=(
            {
                "room_kind": "notice",
                "label": "알림장",
                "order": 10,
            },
        ),
    ),
    HomeAgentServiceDefinition(
        key="schedule",
        label="일정",
        service_key="classcalendar",
        renderer_key="schedule",
        adapter_key="schedule",
        preview_strategy="service",
        selector_hint="메시지 일정 읽기",
        tool_key="schedule",
        aliases=("일정", "캘린더", "시간표"),
        icon_class="fa-regular fa-calendar",
        messenger_flow_key="guided",
        messenger_capabilities={
            "starter_chips": True,
            "multi_step": True,
            "inline_edit": True,
            "copy_result": True,
            "open_link": True,
            "execute": True,
        },
        messenger_ui={
            "flow_variant": "schedule",
            "execution_variant": "schedule",
            "assistant_title": "일정 후보",
            "reset_label": "새로 쓰기",
        },
        copy={
            "service_label": "캘린더 열기",
            "submit_label": "일정 찾기",
            "confirm_label": "캘린더 열기",
            "secondary_link_label": "받은 메시지",
            "helper": "추출 후보",
            "usage_hint": "메시지를 붙여 넣으면 날짜와 시간을 일정 후보로 뽑습니다.",
            "placeholder": "메시지를 붙여 넣으세요.",
        },
        ui={
            "empty_prompt": "어떤 메시지에서 일정을 찾을까요?",
            "preview_line_limit": 8,
        },
        links={
            "service_href": {"source": "tool", "key": "schedule", "field": "href"},
            "secondary_link_href": {"source": "route", "name": "messagebox:main"},
            "continue_query_fields": (
                {"param": "date", "source": "execution_field", "field": "start_time", "transform": "date"},
            ),
        },
        capabilities={
            "preview": True,
            "execute": True,
            "schedule_editor": True,
        },
        runtime_spec={
            "badge": "일정",
            "default_title": "캘린더 등록 후보",
            "default_note": "캘린더 저장 전 날짜와 시간을 한 번 더 확인하면 됩니다.",
            "section_titles": ("후보", "확인"),
            "instruction": (
                "붙여넣은 문장에서 날짜, 시간, 교시, 장소를 뽑아 일정 후보를 정리합니다. "
                "첫 번째 sections.items에는 일정 후보나 입력 필요 값만 넣고 설명 문장은 쓰지 마세요."
            ),
        },
        starter_provider_key="schedule",
        conversation_actions=(
            {
                "room_kind": "dm",
                "label": "일정",
                "order": 10,
            },
            {
                "room_kind": "group_dm",
                "label": "일정",
                "order": 10,
            },
        ),
    ),
    HomeAgentServiceDefinition(
        key="teacher-law",
        label="교사 법률",
        service_key="teacher_law",
        renderer_key="teacher-law",
        adapter_key="teacher-law",
        preview_strategy="service",
        selector_hint="상황 정리",
        tool_key="teacher-law",
        aliases=("교사 법률", "법률", "교권", "민원"),
        icon_class="fa-solid fa-scale-balanced",
        messenger_flow_key="guided",
        messenger_capabilities={
            "starter_chips": True,
            "multi_step": True,
            "copy_result": True,
            "open_link": True,
            "execute": True,
        },
        messenger_ui={
            "flow_variant": "teacher-law",
            "execution_variant": "teacher-law",
            "assistant_title": "법률 검토 메모",
            "reset_label": "새로 쓰기",
        },
        copy={
            "service_label": "법률 가이드 열기",
            "submit_label": "답변 보기",
            "confirm_label": "법률 가이드",
            "helper": "대응 메모",
            "usage_hint": "상황을 적으면 먼저 확인할 대응 순서를 짚어줍니다.",
            "placeholder": "상황을 적으세요.",
        },
        ui={
            "empty_prompt": "어떤 상황인가요?",
            "preview_line_limit": 10,
        },
        links={
            "service_href": {"source": "tool", "key": "teacher-law", "field": "href"},
        },
        capabilities={
            "preview": True,
            "execute": True,
        },
        runtime_spec={
            "badge": "교사 법률",
            "default_title": "법률 검토 메모",
            "default_note": "일반 정보 정리이며 최종 법률 자문은 아닙니다.",
            "section_titles": ("먼저", "대응"),
            "instruction": (
                "교사가 상황을 정리하고 다음 대응 순서를 잡을 수 있게 도와주세요. "
                "사실관계, 기록 보존, 관리자 공유 지점을 먼저 제시하고 단정적인 법률 판단은 피하세요. "
                "첫 번째 sections.items에는 요약, 판단 기준, 대응, 법령 근거, 판례 참고를 교사가 바로 확인할 수 있게 넣으세요."
            ),
        },
        starter_provider_key="teacher-law",
        conversation_actions=(
            {
                "room_kind": "dm",
                "label": "교사법률",
                "order": 20,
            },
            {
                "room_kind": "group_dm",
                "label": "교사법률",
                "order": 20,
            },
        ),
    ),
    HomeAgentServiceDefinition(
        key="reservation",
        label="특별실 예약",
        service_key="reservations",
        renderer_key="reservation",
        adapter_key="reservation",
        preview_strategy="service",
        selector_hint="예약 값 정리",
        tool_key="reservation",
        aliases=("특별실 예약", "특별실", "예약"),
        icon_class="fa-regular fa-clock",
        messenger_flow_key="guided",
        messenger_capabilities={
            "starter_chips": True,
            "multi_step": True,
            "inline_edit": True,
            "copy_result": True,
            "open_link": True,
            "execute": True,
        },
        messenger_ui={
            "flow_variant": "reservation",
            "execution_variant": "reservation",
            "assistant_title": "예약 요청 후보",
            "reset_label": "새로 쓰기",
        },
        copy={
            "service_label": "예약 화면 열기",
            "submit_label": "예약 확인",
            "confirm_label": "예약 화면",
            "helper": "예약 후보",
            "usage_hint": "예약할 내용을 적으면 날짜와 시간, 장소를 정리합니다.",
            "placeholder": "예약할 내용을 적으세요.",
        },
        ui={
            "empty_prompt": "어디를 예약할까요?",
            "preview_line_limit": 8,
        },
        links={
            "service_href": {"source": "tool", "key": "reservation", "field": "href"},
            "continue_query_fields": (
                {"param": "date", "source": "execution_field", "field": "date"},
            ),
        },
        capabilities={
            "preview": True,
            "execute": True,
        },
        runtime_spec={
            "badge": "특별실 예약",
            "default_title": "예약 요청 후보",
            "default_note": "예약 저장 전 장소와 시간을 한 번 더 확인하면 됩니다.",
            "section_titles": ("예약 값", "확인"),
            "instruction": (
                "특별실 예약에 필요한 날짜, 시간 또는 교시, 장소를 정리합니다. "
                "첫 번째 sections.items에는 예약 값과 입력 필요 값만 짧게 넣고 설명 문장은 쓰지 마세요."
            ),
        },
        starter_provider_key="reservation",
        conversation_actions=(
            {
                "room_kind": "dm",
                "label": "특별실 예약",
                "order": 30,
            },
            {
                "room_kind": "group_dm",
                "label": "특별실 예약",
                "order": 30,
            },
        ),
    ),
    HomeAgentServiceDefinition(
        key="quickdrop",
        label="바로 전송",
        service_key="quickdrop",
        renderer_key="quickdrop",
        adapter_key="quickdrop",
        preview_strategy="direct",
        selector_hint="텍스트 보내기",
        tool_key="quickdrop",
        aliases=("바로 전송", "바로전송", "전송", "링크 보내기"),
        icon_class="fa-solid fa-paper-plane",
        action_kind="quickdrop-send",
        messenger_flow_key="direct-send",
        messenger_capabilities={
            "starter_chips": True,
            "file_attach": True,
            "copy_result": False,
            "open_link": True,
        },
        messenger_ui={
            "flow_variant": "quickdrop",
            "assistant_title": "바로전송 준비",
            "reset_label": "새로 쓰기",
        },
        copy={
            "service_label": "전송함 열기",
            "submit_label": "내용 보기",
            "confirm_label": "전송함 열기",
            "after_action_label": "전송함 보기",
            "secondary_link_label": "오늘 보낸 내용",
            "action_label": "바로 전송",
            "helper": "텍스트 전송",
            "usage_hint": "보낼 글이나 파일을 넣고 연결된 기기로 바로 보냅니다.",
            "placeholder": "보낼 내용을 적으세요.",
        },
        ui={
            "empty_prompt": "무엇을 보낼까요?",
            "preview_line_limit": 8,
        },
        links={
            "service_href": (
                {"source": "quickdrop_card", "field": "manage_url"},
                {"source": "tool", "key": "quickdrop", "field": "href"},
            ),
            "after_action_href": (
                {"source": "quickdrop_card", "field": "history_url"},
                {"source": "quickdrop_card", "field": "open_url"},
            ),
            "secondary_link_href": (
                {"source": "quickdrop_card", "field": "history_url"},
                {"source": "quickdrop_card", "field": "open_url"},
            ),
            "snapshot_url": {"source": "quickdrop_card", "field": "snapshot_url"},
            "direct_url": {"source": "quickdrop_card", "field": "send_text_url"},
            "send_file_url": {"source": "quickdrop_card", "field": "send_file_url"},
        },
        capabilities={
            "preview": True,
            "file_attach": True,
        },
        runtime_spec={
            "badge": "바로전송",
            "default_title": "바로전송 준비 완료",
            "default_note": "바로 전송을 누르면 연결된 기기로 즉시 보냅니다.",
            "section_titles": ("보낼 내용", "전송 후"),
            "instruction": (
                "교사가 다른 기기로 바로 보내기 전에 내용을 점검할 수 있게 정리합니다. "
                "첫 번째 sections.items에는 실제로 보낼 내용만 넣고 설명은 쓰지 마세요."
            ),
        },
        starter_provider_key="quickdrop",
        conversation_actions=(
            {
                "room_kind": "notice",
                "label": "바로전송",
                "order": 20,
            },
            {
                "room_kind": "shared",
                "label": "바로전송",
                "order": 40,
            },
            {
                "room_kind": "dm",
                "label": "바로전송",
                "order": 40,
            },
            {
                "room_kind": "group_dm",
                "label": "바로전송",
                "order": 40,
            },
        ),
    ),
    HomeAgentServiceDefinition(
        key="tts",
        label="TTS",
        service_key="tts_announce",
        renderer_key="tts",
        adapter_key="tts",
        preview_strategy="direct",
        selector_hint="읽을 문장",
        tool_key="tts",
        aliases=("TTS", "읽어주기", "방송", "음성"),
        icon_class="fa-solid fa-volume-high",
        action_kind="tts-read",
        messenger_flow_key="one-shot",
        messenger_capabilities={
            "starter_chips": True,
            "copy_result": True,
            "open_link": True,
            "read_result": True,
        },
        messenger_ui={
            "flow_variant": "tts",
            "assistant_title": "읽기 문구",
            "reset_label": "새로 쓰기",
        },
        copy={
            "service_label": "TTS 열기",
            "submit_label": "문구 보기",
            "confirm_label": "TTS 열기",
            "action_label": "바로 읽기",
            "helper": "방송 문구",
            "usage_hint": "읽을 문장을 적으면 방송용 문구로 다듬고 바로 읽습니다.",
            "placeholder": "읽을 문장을 적으세요.",
        },
        ui={
            "empty_prompt": "무엇을 읽을까요?",
            "preview_line_limit": 8,
        },
        links={
            "service_href": {"source": "tool", "key": "tts", "field": "href"},
        },
        capabilities={
            "preview": True,
            "tts_read": True,
        },
        runtime_spec={
            "badge": "TTS",
            "default_title": "읽을 문장을 정리했습니다.",
            "default_note": "짧게 끊어 읽기 좋은 문장 순서로 정리합니다.",
            "section_titles": ("읽기 내용", "실행"),
            "instruction": (
                "교실 방송이나 읽어주기 문장을 짧고 또렷하게 정리합니다. "
                "불필요한 설명을 줄이고 첫 번째 sections.items에는 바로 읽을 문장만 넣으세요."
            ),
        },
        starter_provider_key="tts",
        conversation_actions=(
            {
                "room_kind": "shared",
                "label": "TTS",
                "order": 20,
            },
        ),
    ),
    HomeAgentServiceDefinition(
        key="message-save",
        label="메시지 저장",
        service_key="messagebox",
        renderer_key="message-save",
        adapter_key="message-save",
        preview_strategy="direct",
        selector_hint="메시지 보관",
        tool_key="messagebox",
        aliases=("메시지 저장", "메시지 보관", "보관함", "받은 메시지"),
        icon_class="fa-regular fa-folder-open",
        action_kind="message-capture-save",
        messenger_flow_key="pipeline",
        messenger_capabilities={
            "starter_chips": False,
            "multi_step": True,
            "copy_result": True,
            "open_link": True,
        },
        messenger_ui={
            "flow_variant": "message-save",
            "assistant_title": "메시지 보관",
            "reset_label": "새로 쓰기",
        },
        copy={
            "service_label": "보관함 열기",
            "submit_label": "내용 보기",
            "confirm_label": "보관함 열기",
            "after_action_label": "보관함 보기",
            "secondary_link_label": "보관함 보기",
            "action_label": "메시지 저장",
            "helper": "메시지 보관",
            "usage_hint": "메시지를 붙여 넣으면 보관하고 다음 일정 확인까지 이어갑니다.",
            "placeholder": "저장할 메시지를 붙여넣으세요.",
        },
        ui={
            "empty_prompt": "메시지를 바로 붙여넣으세요.",
            "preview_line_limit": 8,
        },
        links={
            "service_href": {"source": "tool", "key": "messagebox", "field": "href"},
            "after_action_href": {"source": "tool", "key": "messagebox", "field": "href"},
            "secondary_link_href": {"source": "tool", "key": "messagebox", "field": "href"},
            "direct_url": {"source": "route", "name": "classcalendar:api_message_capture_save"},
            "parse_saved_template": {"source": "message_capture", "field": "parse_saved_template"},
            "commit_template": {"source": "message_capture", "field": "commit_template"},
        },
        capabilities={
            "preview": True,
            "message_pipeline": True,
        },
        runtime_spec={
            "badge": "메시지 저장",
            "default_title": "메시지 보관",
            "default_note": "저장 후 일정 후보를 바로 확인합니다.",
            "section_titles": ("보관", "다음"),
            "instruction": (
                "메시지를 저장하고 일정 후보를 다시 확인할 수 있게 정리합니다. "
                "첫 번째 sections.items에는 저장 대상 메시지 핵심만 넣고 설명 문장은 쓰지 마세요."
            ),
        },
        starter_provider_key="message-save",
        conversation_actions=(
            {
                "room_kind": "notice",
                "label": "메시지 저장",
                "order": 30,
            },
            {
                "room_kind": "shared",
                "label": "메시지 저장",
                "order": 30,
            },
        ),
    ),
)


HOME_AGENT_SERVICE_MAP = {
    definition.key: definition
    for definition in HOME_AGENT_SERVICE_DEFINITIONS
}


def get_home_agent_service_definitions():
    return HOME_AGENT_SERVICE_DEFINITIONS


def get_home_agent_service_definition(mode_key: str):
    return HOME_AGENT_SERVICE_MAP.get(str(mode_key or "").strip())


def resolve_home_agent_conversation_actions(room_kind: str) -> list[dict]:
    normalized_room_kind = str(room_kind or "").strip().lower()
    if not normalized_room_kind:
        return []

    actions = []
    for definition in HOME_AGENT_SERVICE_DEFINITIONS:
        for spec in definition.conversation_actions or ():
            spec_room_kind = str(spec.get("room_kind") or "").strip().lower()
            if spec_room_kind != normalized_room_kind:
                continue
            actions.append(
                (
                    int(spec.get("order") or 100),
                    {
                        "key": f"{normalized_room_kind}:{definition.key}",
                        "mode_key": definition.key,
                        "label": str(spec.get("label") or definition.label).strip() or definition.label,
                    },
                )
            )
    actions.sort(key=lambda item: item[0])
    return [payload for _order, payload in actions]


def get_home_agent_runtime_spec(mode_key: str) -> dict | None:
    definition = get_home_agent_service_definition(mode_key)
    if definition is None:
        return None
    return deepcopy(definition.runtime_spec)


def _clone_starter_items(definition: HomeAgentServiceDefinition) -> list[dict]:
    return [dict(item) for item in definition.starter_items]


def _build_static_ui_options(*, definition: HomeAgentServiceDefinition, request=None) -> dict:
    return {}


def _build_teacher_law_starter_items(*, definition: HomeAgentServiceDefinition, request=None) -> list[dict]:
    try:
        from teacher_law.services.query_normalizer import get_quick_question_presets
    except Exception:
        return _clone_starter_items(definition)

    starter_items = []
    for preset in get_quick_question_presets():
        question = str(preset.get("question") or "").strip()
        if not question:
            continue
        label = str(preset.get("label") or question).strip()
        if len(label) > 12:
            label = f"{label[:11]}…"
        starter_items.append(
            {
                "label": label,
                "text": question,
            }
        )
    return starter_items or _clone_starter_items(definition)


def _build_notice_starter_items(*, definition: HomeAgentServiceDefinition, request=None) -> list[dict]:
    try:
        from django.urls import NoReverseMatch, reverse

        endpoint = reverse("noticegen:daily_recommendation")
    except NoReverseMatch:
        endpoint = ""

    starter_items = [
        {
            "label": "오늘 추천",
            "text": "오늘 추천",
            "action": "daily_notice_recommendation",
            "endpoint": endpoint,
        }
    ]
    seen_texts = {"오늘 추천"}
    for item in _clone_starter_items(definition):
        text = str(item.get("text") or "").strip()
        if not text or text in seen_texts:
            continue
        seen_texts.add(text)
        starter_items.append(item)
    return starter_items


def _build_teacher_law_ui_options(*, definition: HomeAgentServiceDefinition, request=None) -> dict:
    try:
        from teacher_law.services.query_normalizer import get_input_options
    except Exception:
        return {}
    return get_input_options() or {}


def _build_reservation_ui_options(*, definition: HomeAgentServiceDefinition, request=None) -> dict:
    if request is None or not getattr(getattr(request, "user", None), "is_authenticated", False):
        return {}

    try:
        from reservations.models import SpecialRoom
        from reservations.utils import list_user_accessible_schools
    except Exception:
        return {}

    schools = [
        entry
        for entry in list_user_accessible_schools(request.user)
        if entry.get("can_edit") and entry.get("school") is not None
    ]
    if not schools:
        return {}

    school_by_id = {
        entry["school"].id: entry["school"]
        for entry in schools
    }
    rooms = list(
        SpecialRoom.objects.filter(school_id__in=school_by_id.keys())
        .only("id", "name", "school_id")
        .order_by("school_id", "name", "id")
    )
    if not rooms:
        return {}

    room_names = []
    room_labels = []
    school_names = []
    seen_room_names = set()
    seen_room_labels = set()
    seen_school_names = set()

    for room in rooms:
        room_name = str(room.name or "").strip()
        school = school_by_id.get(room.school_id)
        school_name = str(getattr(school, "name", "") or "").strip()
        if not room_name:
            continue
        if room_name not in seen_room_names:
            seen_room_names.add(room_name)
            room_names.append(room_name)
        label = f"{school_name} {room_name}".strip() if school_name else room_name
        if label not in seen_room_labels:
            seen_room_labels.add(label)
            room_labels.append(label)
        if school_name and school_name not in seen_school_names:
            seen_school_names.add(school_name)
            school_names.append(school_name)

    return {
        "room_names": room_names,
        "room_labels": room_labels,
        "school_names": school_names,
    }


StarterProvider = Callable[..., list[dict]]
UiOptionsProvider = Callable[..., dict]


HOME_AGENT_STARTER_PROVIDERS: dict[str, StarterProvider] = {
    "notice": _build_notice_starter_items,
    "schedule": lambda *, definition, request=None: _clone_starter_items(definition),
    "teacher-law": _build_teacher_law_starter_items,
    "reservation": lambda *, definition, request=None: _build_reservation_starter_items(request=request),
    "quickdrop": lambda *, definition, request=None: _clone_starter_items(definition),
    "tts": lambda *, definition, request=None: _clone_starter_items(definition),
    "message-save": lambda *, definition, request=None: _clone_starter_items(definition),
}


HOME_AGENT_UI_OPTION_PROVIDERS: dict[str, UiOptionsProvider] = {
    "teacher-law": _build_teacher_law_ui_options,
    "reservation": _build_reservation_ui_options,
}


def resolve_home_agent_starter_items(definition: HomeAgentServiceDefinition, *, request=None) -> list[dict]:
    provider_key = str(definition.starter_provider_key or "").strip()
    provider = HOME_AGENT_STARTER_PROVIDERS.get(provider_key)
    if provider is None:
        return _clone_starter_items(definition)
    return provider(definition=definition, request=request)


def resolve_home_agent_ui_options(definition: HomeAgentServiceDefinition, *, request=None) -> dict:
    provider_key = str(definition.starter_provider_key or "").strip()
    provider = HOME_AGENT_UI_OPTION_PROVIDERS.get(provider_key, _build_static_ui_options)
    payload = provider(definition=definition, request=request)
    return deepcopy(payload or {})


def resolve_home_agent_mode_links(definition: HomeAgentServiceDefinition, *, sources: dict | None = None) -> dict:
    resolved = {}
    source_map = sources or {}
    for key, spec in (definition.links or {}).items():
        if key == "continue_query_fields":
            resolved[key] = [dict(item) for item in spec]
            continue
        resolved[key] = _resolve_mode_link_value(spec, sources=source_map)
    return resolved


def build_home_agent_mode_payload(
    definition: HomeAgentServiceDefinition,
    *,
    product_id=None,
    links: dict | None = None,
    starter_items: list[dict] | None = None,
    ui_options: dict | None = None,
    workflow_keys=(),
    tacit_rule_keys=(),
) -> dict:
    copy = deepcopy(definition.copy or {})
    ui = deepcopy(definition.ui or {})
    messenger_capabilities = deepcopy(definition.messenger_capabilities or {})
    messenger_ui = deepcopy(definition.messenger_ui or {})
    capabilities = deepcopy(definition.capabilities or {})
    resolved_links = deepcopy(links or {})
    items = [dict(item) for item in (starter_items or [])]
    resolved_ui_options = deepcopy(ui_options or {})

    mode = {
        "key": definition.key,
        "label": definition.label,
        "aliases": tuple(definition.aliases),
        "renderer_key": definition.renderer_key,
        "adapter_key": definition.adapter_key,
        "preview_strategy": definition.preview_strategy,
        "selector_hint": definition.selector_hint,
        "service_key": definition.service_key,
        "product_id": product_id,
        "icon_class": definition.icon_class,
        "action_kind": definition.action_kind,
        "copy": copy,
        "ui": ui,
        "messenger_flow_key": str(definition.messenger_flow_key or "one-shot"),
        "messenger_capabilities": messenger_capabilities,
        "messenger_ui": messenger_ui,
        "links": resolved_links,
        "capabilities": capabilities,
        "starter_provider_key": str(definition.starter_provider_key or ""),
        "starter_items": items,
        "ui_options": resolved_ui_options,
        "workflow_keys": tuple(workflow_keys),
        "tacit_rule_keys": tuple(tacit_rule_keys),
        "service_href": str(resolved_links.get("service_href") or ""),
        "service_label": str(copy.get("service_label") or ""),
        "submit_label": str(copy.get("submit_label") or ""),
        "confirm_label": str(copy.get("confirm_label") or ""),
        "secondary_link_label": str(copy.get("secondary_link_label") or ""),
        "secondary_link_href": str(resolved_links.get("secondary_link_href") or ""),
        "after_action_label": str(copy.get("after_action_label") or ""),
        "after_action_href": str(resolved_links.get("after_action_href") or ""),
        "action_label": str(copy.get("action_label") or ""),
        "snapshot_url": str(resolved_links.get("snapshot_url") or ""),
        "direct_url": str(resolved_links.get("direct_url") or ""),
        "send_file_url": str(resolved_links.get("send_file_url") or ""),
        "parse_saved_template": str(resolved_links.get("parse_saved_template") or ""),
        "commit_template": str(resolved_links.get("commit_template") or ""),
        "helper": str(copy.get("helper") or ""),
        "usage_hint": str(copy.get("usage_hint") or ""),
        "placeholder": str(copy.get("placeholder") or ""),
        "empty_prompt": str(ui.get("empty_prompt") or ""),
        "preview_line_limit": int(ui.get("preview_line_limit") or 8),
        "refinement_actions": [dict(item) for item in ui.get("refinement_actions", ())],
        "continue_query_fields": [dict(item) for item in resolved_links.get("continue_query_fields", ())],
    }
    return mode


def _resolve_mode_link_value(spec, *, sources: dict) -> str:
    if isinstance(spec, (list, tuple)):
        for item in spec:
            value = _resolve_mode_link_value(item, sources=sources)
            if value:
                return value
        return ""
    if isinstance(spec, dict):
        source_name = str(spec.get("source") or "").strip()
        if source_name == "tool":
            tool_map = sources.get("tool") or {}
            tool = tool_map.get(str(spec.get("key") or "").strip()) or {}
            return str(tool.get(spec.get("field") or "href") or "")
        if source_name == "route":
            route_map = sources.get("route") or {}
            return str(route_map.get(str(spec.get("name") or "").strip()) or "")
        if source_name == "quickdrop_card":
            quickdrop_card = sources.get("quickdrop_card") or {}
            return str(quickdrop_card.get(spec.get("field") or "") or "")
        if source_name == "message_capture":
            message_capture = sources.get("message_capture") or {}
            return str(message_capture.get(spec.get("field") or "") or "")
    return str(spec or "")


def _build_reservation_starter_items(*, request=None) -> list[dict]:
    if request is None or not getattr(getattr(request, "user", None), "is_authenticated", False):
        return []

    try:
        from reservations.models import SpecialRoom
        from reservations.utils import list_user_accessible_schools
    except Exception:
        return []

    schools = [
        entry
        for entry in list_user_accessible_schools(request.user)
        if entry.get("can_edit") and entry.get("school") is not None
    ]
    if not schools:
        return []

    school_by_id = {
        entry["school"].id: entry["school"]
        for entry in schools
    }
    rooms = list(
        SpecialRoom.objects.filter(school_id__in=school_by_id.keys())
        .only("id", "name", "school_id")
        .order_by("school_id", "name", "id")
    )
    if not rooms:
        return []

    name_counts = Counter(str(room.name or "").strip() for room in rooms if str(room.name or "").strip())
    starter_items = []
    seen_labels = set()
    for room in rooms:
        room_name = str(room.name or "").strip()
        school = school_by_id.get(room.school_id)
        school_name = str(getattr(school, "name", "") or "").strip()
        if not room_name:
            continue
        label = room_name
        if name_counts.get(room_name, 0) > 1 and school_name:
            label = f"{school_name} {room_name}"
        if label in seen_labels:
            continue
        seen_labels.add(label)
        text_room_name = label if name_counts.get(room_name, 0) > 1 else room_name
        starter_items.append(
            {
                "label": label,
                "text": f"다음 주 화요일 3교시에 {text_room_name} 예약해줘.",
            }
        )
        if len(starter_items) >= 4:
            break
    return starter_items
