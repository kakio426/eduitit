from __future__ import annotations

from copy import deepcopy


ADMIN_NAV_GROUPS = (
    {
        "key": "operations",
        "label": "운영 · 계정",
        "description": "사용자, 권한, 기본 설정처럼 가장 자주 찾는 관리 메뉴입니다.",
        "is_open_by_default": True,
        "app_labels": (
            "core",
            "auth",
            "sites",
            "account",
            "socialaccount",
            "consent",
            "signatures",
        ),
    },
    {
        "key": "services",
        "label": "서비스 구성",
        "description": "서비스 노출, 상품 구성, 운영 정책처럼 서비스 틀을 다루는 메뉴입니다.",
        "is_open_by_default": True,
        "app_labels": (
            "products",
            "classcalendar",
            "insights",
            "version_manager",
        ),
    },
    {
        "key": "classroom",
        "label": "교실 운영",
        "description": "학급 운영과 교실 업무에 바로 연결되는 서비스 메뉴입니다.",
        "is_open_by_default": True,
        "app_labels": (
            "parentcomm",
            "reservations",
            "timetable",
            "seed_quiz",
            "happy_seed",
            "handoff",
            "collect",
            "blockclass",
            "textbooks",
            "textbook_ai",
        ),
    },
    {
        "key": "content",
        "label": "자료 · 생성",
        "description": "문서, 콘텐츠, 자료 생성처럼 편집과 제작 중심 메뉴입니다.",
        "is_open_by_default": True,
        "app_labels": (
            "slidesmith",
            "docviewer",
            "hwpxchat",
            "autoarticle",
            "portfolio",
            "infoboard",
            "encyclopedia",
            "noticegen",
            "qrgen",
        ),
    },
)

LEGACY_GROUP = {
    "key": "legacy",
    "label": "기존 · 보관 서비스",
    "description": "예전 서비스나 가끔만 찾는 메뉴는 여기로 모았습니다.",
    "is_open_by_default": False,
}


def build_admin_navigation(app_list, current_path: str = ""):
    prepared_apps = [_prepare_app(app, current_path=current_path) for app in app_list]
    apps_by_label = {app["app_label"]: app for app in prepared_apps}
    grouped = []
    claimed_labels = set()

    for spec in ADMIN_NAV_GROUPS:
        apps = []
        for label in spec["app_labels"]:
            app = apps_by_label.get(label)
            if not app:
                continue
            apps.append(app)
            claimed_labels.add(label)
        if apps:
            grouped.append(_build_group(spec, apps))

    leftovers = [app for app in prepared_apps if app["app_label"] not in claimed_labels]
    if leftovers:
        leftovers.sort(key=lambda item: item["name"])
        grouped.append(_build_group(LEGACY_GROUP, leftovers))

    return grouped


def _prepare_app(app, current_path: str):
    prepared = deepcopy(app)
    app_url = prepared.get("app_url", "")
    prepared["model_count"] = len(prepared.get("models", []))
    prepared["is_current"] = bool(app_url and current_path.startswith(app_url))
    search_parts = [_text(prepared.get("name", "")), _text(prepared.get("app_label", ""))]

    for model in prepared.get("models", []):
        model_name = _text(model.get("name", ""))
        object_name = _text(model.get("object_name", ""))
        model_admin_url = model.get("admin_url", "")
        model_add_url = model.get("add_url", "")
        model["is_current"] = bool(
            (model_admin_url and current_path.startswith(model_admin_url))
            or (model_add_url and current_path.startswith(model_add_url))
        )
        model["search_text"] = " ".join((model_name, object_name)).strip().lower()
        search_parts.extend((model_name, object_name))

    prepared["search_text"] = " ".join(part for part in search_parts if part).lower()
    return prepared


def _text(value):
    return str(value or "")


def _build_group(spec, apps):
    return {
        "key": spec["key"],
        "label": spec["label"],
        "description": spec["description"],
        "apps": apps,
        "app_count": len(apps),
        "model_count": sum(app["model_count"] for app in apps),
        "has_current": any(
            app["is_current"] or any(model["is_current"] for model in app.get("models", []))
            for app in apps
        ),
        "is_open_by_default": spec.get("is_open_by_default", False),
    }
