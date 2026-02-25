"""
Generate LLM-ready training data for the Eduitit monorepo.

Outputs (under docs/llm_dataset):
  - eduitit_llm_bundle.json
  - eduitit_service_catalog.json
  - eduitit_code_structure.json
  - eduitit_chat_training.jsonl
"""

from __future__ import annotations

import ast
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "docs" / "llm_dataset"
SETTINGS_PATH = REPO_ROOT / "config" / "settings.py"
ROOT_URLS_PATH = REPO_ROOT / "config" / "urls.py"
DB_PATH = REPO_ROOT / "db.sqlite3"


@dataclass
class PySymbols:
    classes: list[str]
    functions: list[str]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_installed_apps(settings_text: str) -> list[str]:
    pattern = re.compile(r"'([a-zA-Z0-9_]+)\.apps\.[^']+'")
    return sorted(set(pattern.findall(settings_text)))


def parse_root_route_prefixes(root_urls_text: str) -> dict[str, list[str]]:
    """
    Parse mappings from app name -> route prefixes from config/urls.py.
    """
    app_prefixes: dict[str, list[str]] = {}
    # Example: path('collect/', include('collect.urls', namespace='collect'))
    pattern = re.compile(
        r"path\(\s*'([^']*)'\s*,\s*include\(\s*'([a-zA-Z0-9_]+)\.urls'",
        re.MULTILINE,
    )
    for prefix, app_name in pattern.findall(root_urls_text):
        app_prefixes.setdefault(app_name, [])
        if prefix not in app_prefixes[app_name]:
            app_prefixes[app_name].append(prefix)
    return app_prefixes


def parse_python_symbols(py_path: Path) -> PySymbols:
    if not py_path.exists():
        return PySymbols(classes=[], functions=[])
    try:
        tree = ast.parse(read_text(py_path))
    except SyntaxError:
        return PySymbols(classes=[], functions=[])
    classes: list[str] = []
    functions: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.FunctionDef):
            functions.append(node.name)
    return PySymbols(classes=classes, functions=functions)


def parse_model_class_names(models_path: Path) -> list[str]:
    if not models_path.exists():
        return []
    try:
        tree = ast.parse(read_text(models_path))
    except SyntaxError:
        return []

    model_names: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        is_model = False
        for base in node.bases:
            if isinstance(base, ast.Attribute) and base.attr == "Model":
                is_model = True
            elif isinstance(base, ast.Name) and base.id == "Model":
                is_model = True
        if is_model:
            model_names.append(node.name)
    return model_names


def parse_urlpatterns(urls_path: Path) -> list[dict[str, Any]]:
    if not urls_path.exists():
        return []
    try:
        tree = ast.parse(read_text(urls_path))
    except SyntaxError:
        return []

    patterns: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        if node.func.id not in {"path", "re_path"}:
            continue
        route = ""
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            route = node.args[0].value
        name = None
        for kw in node.keywords:
            if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                name = kw.value.value
        patterns.append({"route": route, "name": name})

    # Deduplicate but keep order
    seen: set[tuple[str, str | None]] = set()
    unique: list[dict[str, Any]] = []
    for item in patterns:
        key = (item["route"], item["name"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def safe_count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.rglob("*") if _.is_file())


def sample_paths(path: Path, limit: int = 8) -> list[str]:
    if not path.exists():
        return []
    files = sorted([p for p in path.rglob("*") if p.is_file()])
    return [str(p.relative_to(REPO_ROOT)).replace("\\", "/") for p in files[:limit]]


def parse_apps_py_name(app_dir: Path) -> str | None:
    apps_path = app_dir / "apps.py"
    if not apps_path.exists():
        return None
    try:
        tree = ast.parse(read_text(apps_path))
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "name":
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
    return None


def get_product_rows_from_db() -> list[dict[str, Any]]:
    if not DB_PATH.exists():
        return []
    try:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            """
            SELECT
                id, title, lead_text, description, service_type, launch_route_name, external_url,
                is_active, is_featured, display_order, solve_text, result_text, time_text
            FROM products_product
            ORDER BY display_order ASC, id ASC
            """
        )
        rows = [dict(row) for row in cur.fetchall()]
        con.close()
        return rows
    except sqlite3.Error:
        return []


def make_app_structure(app_name: str, prefixes: list[str]) -> dict[str, Any]:
    app_dir = REPO_ROOT / app_name
    models_path = app_dir / "models.py"
    views_path = app_dir / "views.py"
    forms_path = app_dir / "forms.py"
    urls_path = app_dir / "urls.py"
    tests_path = app_dir / "tests.py"
    templates_path = app_dir / "templates"
    static_path = app_dir / "static"
    migrations_path = app_dir / "migrations"
    mgmt_cmd_path = app_dir / "management" / "commands"

    view_symbols = parse_python_symbols(views_path)
    form_symbols = parse_python_symbols(forms_path)

    return {
        "app_name": app_name,
        "module_name": parse_apps_py_name(app_dir) or app_name,
        "route_prefixes": prefixes,
        "key_files": {
            "models": str(models_path.relative_to(REPO_ROOT)).replace("\\", "/") if models_path.exists() else None,
            "views": str(views_path.relative_to(REPO_ROOT)).replace("\\", "/") if views_path.exists() else None,
            "urls": str(urls_path.relative_to(REPO_ROOT)).replace("\\", "/") if urls_path.exists() else None,
            "forms": str(forms_path.relative_to(REPO_ROOT)).replace("\\", "/") if forms_path.exists() else None,
            "tests": str(tests_path.relative_to(REPO_ROOT)).replace("\\", "/") if tests_path.exists() else None,
        },
        "models": parse_model_class_names(models_path),
        "view_functions": view_symbols.functions,
        "view_classes": view_symbols.classes,
        "form_classes": form_symbols.classes,
        "urlpatterns": parse_urlpatterns(urls_path),
        "file_counts": {
            "templates": safe_count_files(templates_path),
            "static": safe_count_files(static_path),
            "migrations": safe_count_files(migrations_path),
            "management_commands": safe_count_files(mgmt_cmd_path),
        },
        "sample_files": {
            "templates": sample_paths(templates_path),
            "static": sample_paths(static_path),
        },
    }


def map_products_to_services(products: list[dict[str, Any]], app_structures: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    route_name_to_apps: dict[str, list[str]] = {}
    for app_name, app_data in app_structures.items():
        for item in app_data.get("urlpatterns", []):
            route_name = (item.get("name") or "").strip()
            if not route_name:
                continue
            route_name_to_apps.setdefault(route_name, [])
            if app_name not in route_name_to_apps[route_name]:
                route_name_to_apps[route_name].append(app_name)

    items: list[dict[str, Any]] = []
    for row in products:
        route_name = (row.get("launch_route_name") or "").strip()
        matched_app = None
        if ":" in route_name:
            route_namespace = route_name.split(":", 1)[0]
            if route_namespace in app_structures:
                matched_app = route_namespace
        else:
            candidate_apps = route_name_to_apps.get(route_name, [])
            if len(candidate_apps) == 1:
                matched_app = candidate_apps[0]

        service = {
            "product_id": row.get("id"),
            "title": row.get("title"),
            "lead_text": row.get("lead_text") or "",
            "description": row.get("description") or "",
            "service_type": row.get("service_type"),
            "launch_route_name": route_name,
            "external_url": row.get("external_url") or "",
            "is_active": bool(row.get("is_active")),
            "is_featured": bool(row.get("is_featured")),
            "display_order": row.get("display_order"),
            "value_props": {
                "solve_text": row.get("solve_text") or "",
                "result_text": row.get("result_text") or "",
                "time_text": row.get("time_text") or "",
            },
            "mapped_app": matched_app,
            "mapped_route_prefixes": app_structures.get(matched_app, {}).get("route_prefixes", []) if matched_app else [],
        }
        items.append(service)
    return items


def build_chat_answer(service: dict[str, Any], app_data: dict[str, Any] | None) -> str:
    title = service.get("title") or service.get("mapped_app") or "서비스"
    lead = service.get("lead_text") or service.get("description") or ""
    launch_route = service.get("launch_route_name") or "-"
    service_type = service.get("service_type") or "-"

    lines = [
        f"{title}는 Eduitit의 `{service_type}` 카테고리 서비스입니다.",
        f"핵심 설명: {lead}".strip(),
        f"진입 라우트: `{launch_route}`",
    ]
    if app_data:
        lines.append(f"코드 앱: `{app_data['app_name']}`")
        if app_data.get("route_prefixes"):
            prefixes = ", ".join(f"`/{p}`" for p in app_data["route_prefixes"])
            lines.append(f"URL prefix: {prefixes}")
        if app_data.get("models"):
            lines.append("주요 모델: " + ", ".join(f"`{m}`" for m in app_data["models"][:8]))
        if app_data.get("view_functions"):
            lines.append("주요 뷰 함수: " + ", ".join(f"`{v}`" for v in app_data["view_functions"][:8]))
    return "\n".join(lines)


def build_structure_answer(service: dict[str, Any], app_data: dict[str, Any] | None) -> str:
    if not app_data:
        return "이 서비스는 현재 코드 앱 매핑 정보가 없습니다. `launch_route_name` 또는 외부 URL 기준으로 확인이 필요합니다."

    key_files = app_data.get("key_files", {})
    counts = app_data.get("file_counts", {})
    urlpatterns = app_data.get("urlpatterns", [])

    lines = [
        f"`{app_data['app_name']}` 앱 구조 기준으로 설명합니다.",
        f"- models: {key_files.get('models')}",
        f"- views: {key_files.get('views')}",
        f"- urls: {key_files.get('urls')}",
        f"- forms: {key_files.get('forms')}",
        f"- templates 파일 수: {counts.get('templates', 0)}",
        f"- static 파일 수: {counts.get('static', 0)}",
        f"- migration 파일 수: {counts.get('migrations', 0)}",
    ]
    if urlpatterns:
        samples = []
        for p in urlpatterns[:8]:
            route = p.get("route") or ""
            name = p.get("name") or "-"
            samples.append(f"`{route}` (name: `{name}`)")
        lines.append("- 대표 URL 패턴: " + ", ".join(samples))
    return "\n".join(lines)


def build_chat_training_data(service_catalog: list[dict[str, Any]], app_structures: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    system_prompt = (
        "너는 Eduitit 서비스 안내 도우미다. 서비스 설명, 코드 위치, URL 구조를 정확한 파일 기준으로 답변한다."
    )

    for service in service_catalog:
        app_name = service.get("mapped_app")
        app_data = app_structures.get(app_name) if app_name else None
        title = service.get("title") or app_name or "서비스"

        records.append(
            {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{title} 서비스가 뭐야?"},
                    {"role": "assistant", "content": build_chat_answer(service, app_data)},
                ],
                "metadata": {"service_title": title, "task": "service_overview"},
            }
        )
        records.append(
            {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{title} 코드 구조 알려줘"},
                    {"role": "assistant", "content": build_structure_answer(service, app_data)},
                ],
                "metadata": {"service_title": title, "task": "code_structure"},
            }
        )

    return records


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    lines = [json.dumps(item, ensure_ascii=False) for item in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main() -> None:
    ensure_output_dir()

    settings_text = read_text(SETTINGS_PATH)
    root_urls_text = read_text(ROOT_URLS_PATH)

    installed_apps = parse_installed_apps(settings_text)
    route_prefixes = parse_root_route_prefixes(root_urls_text)

    app_structures: dict[str, dict[str, Any]] = {}
    for app in installed_apps:
        app_structures[app] = make_app_structure(app, route_prefixes.get(app, []))

    products = get_product_rows_from_db()
    service_catalog = map_products_to_services(products, app_structures)
    chat_training = build_chat_training_data(service_catalog, app_structures)

    catalog_payload = {
        "project": "eduitit",
        "generated_from": {
            "settings": str(SETTINGS_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "root_urls": str(ROOT_URLS_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "db": str(DB_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        },
        "service_count": len(service_catalog),
        "services": service_catalog,
    }
    structure_payload = {
        "project": "eduitit",
        "app_count": len(app_structures),
        "apps": list(app_structures.values()),
    }
    bundle_payload = {
        "project": "eduitit",
        "generated_from": {
            "settings": str(SETTINGS_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "root_urls": str(ROOT_URLS_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "db": str(DB_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "generator": str(Path(__file__).relative_to(REPO_ROOT)).replace("\\", "/"),
        },
        "summary": {
            "service_count": len(service_catalog),
            "app_count": len(app_structures),
            "chat_record_count": len(chat_training),
        },
        "service_catalog": catalog_payload,
        "code_structure": structure_payload,
        "chat_training_records": chat_training,
    }

    write_json(OUTPUT_DIR / "eduitit_llm_bundle.json", bundle_payload)
    write_json(OUTPUT_DIR / "eduitit_service_catalog.json", catalog_payload)
    write_json(OUTPUT_DIR / "eduitit_code_structure.json", structure_payload)
    write_jsonl(OUTPUT_DIR / "eduitit_chat_training.jsonl", chat_training)

    print(f"[OK] Generated files in {OUTPUT_DIR}")
    print(f"- services: {len(service_catalog)}")
    print(f"- apps: {len(app_structures)}")
    print(f"- chat records: {len(chat_training)}")


if __name__ == "__main__":
    main()
