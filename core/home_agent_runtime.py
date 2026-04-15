from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass

from openai import OpenAI

from .home_agent_service_bridge import (
    HomeAgentServiceUnavailable,
    generate_service_preview,
)


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL_NAME = "deepseek-chat"
OPENCLAW_DEFAULT_API_KEY = "openclaw-local"

HOME_AGENT_MODE_SPECS = {
    "notice": {
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
    "schedule": {
        "badge": "일정",
        "default_title": "캘린더 등록 후보",
        "default_note": "캘린더 저장 전 날짜와 시간을 한 번 더 확인하면 됩니다.",
        "section_titles": ("후보", "확인"),
        "instruction": (
            "붙여넣은 문장에서 날짜, 시간, 교시, 장소를 뽑아 일정 후보를 정리합니다. "
            "첫 번째 sections.items에는 일정 후보나 입력 필요 값만 넣고 설명 문장은 쓰지 마세요."
        ),
    },
    "teacher-law": {
        "badge": "교사 법률",
        "default_title": "법률 검토 메모",
        "default_note": "일반 정보 정리이며 최종 법률 자문은 아닙니다.",
        "section_titles": ("먼저", "대응"),
        "instruction": (
            "교사가 상황을 정리하고 다음 대응 순서를 잡을 수 있게 도와주세요. "
            "사실관계, 기록 보존, 관리자 공유 지점을 먼저 제시하고 단정적인 법률 판단은 피하세요. "
            "첫 번째 sections.items에는 바로 체크할 행동만 짧게 넣고 해설은 쓰지 마세요."
        ),
    },
    "reservation": {
        "badge": "특별실 예약",
        "default_title": "예약 요청 후보",
        "default_note": "예약 저장 전 장소와 시간을 한 번 더 확인하면 됩니다.",
        "section_titles": ("예약 값", "확인"),
        "instruction": (
            "특별실 예약에 필요한 날짜, 시간 또는 교시, 장소를 정리합니다. "
            "첫 번째 sections.items에는 예약 값과 입력 필요 값만 짧게 넣고 설명 문장은 쓰지 마세요."
        ),
    },
    "quickdrop": {
        "badge": "바로전송",
        "default_title": "바로전송 준비 완료",
        "default_note": "바로 전송을 누르면 연결된 기기로 즉시 보냅니다.",
        "section_titles": ("보낼 내용", "전송 후"),
        "instruction": (
            "교사가 다른 기기로 바로 보내기 전에 내용을 점검할 수 있게 정리합니다. "
            "첫 번째 sections.items에는 실제로 보낼 내용만 넣고 설명은 쓰지 마세요."
        ),
    },
    "pdf": {
        "badge": "PDF",
        "default_title": "문서 정리 초안",
        "default_note": "원문을 다시 볼 때 필요한 키워드만 먼저 남겨주세요.",
        "section_titles": ("핵심", "다음"),
        "instruction": (
            "문서나 공문 내용을 교사가 바로 실행할 수 있게 요약합니다. "
            "첫 번째 sections.items에는 바로 필요한 핵심만 짧게 넣고 설명 문장은 쓰지 마세요."
        ),
    },
    "tts": {
        "badge": "TTS",
        "default_title": "읽을 문장을 정리했습니다.",
        "default_note": "짧게 끊어 읽기 좋은 문장 순서로 정리합니다.",
        "section_titles": ("읽기 내용", "실행"),
        "instruction": (
            "교실 방송이나 읽어주기 문장을 짧고 또렷하게 정리합니다. "
            "불필요한 설명을 줄이고 첫 번째 sections.items에는 바로 읽을 문장만 넣으세요."
        ),
    },
}


class HomeAgentError(Exception):
    """Base error for home agent runtime."""


class HomeAgentConfigError(HomeAgentError):
    """Raised when no usable provider is configured."""


class HomeAgentProviderError(HomeAgentError):
    """Raised when provider request fails."""


@dataclass(frozen=True)
class HomeAgentProviderConfig:
    provider: str
    model: str
    base_url: str
    api_key: str


def generate_home_agent_preview(
    *,
    mode_key: str,
    text: str,
    selected_date_label: str = "",
    preferred_provider: str = "",
    context: dict | None = None,
    request=None,
) -> dict:
    mode_spec = HOME_AGENT_MODE_SPECS.get(str(mode_key or "").strip())
    if mode_spec is None:
        raise HomeAgentProviderError("지원하지 않는 agent 모드입니다.")

    trimmed_text = str(text or "").strip()
    if not trimmed_text:
        raise HomeAgentProviderError("내용을 먼저 입력해 주세요.")

    try:
        service_payload = generate_service_preview(
            request=request,
            mode_key=mode_key,
            mode_spec=mode_spec,
            text=trimmed_text,
            selected_date_label=selected_date_label,
            context=context or {},
        )
    except HomeAgentServiceUnavailable as exc:
        raise HomeAgentProviderError(str(exc)) from exc
    if service_payload is not None:
        return service_payload

    messages = _build_preview_messages(
        mode_key=mode_key,
        mode_spec=mode_spec,
        text=trimmed_text,
        selected_date_label=selected_date_label,
        context=context or {},
    )
    last_error = None
    for config in resolve_home_agent_provider_configs(preferred_provider=preferred_provider):
        try:
            payload = _call_json_response(
                config=config,
                messages=messages,
                timeout_seconds=18,
            )
            return {
                "preview": _normalize_preview_payload(
                    mode_spec=mode_spec,
                    payload=payload,
                    original_text=trimmed_text,
                ),
                "provider": config.provider,
                "model": config.model,
            }
        except HomeAgentProviderError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    raise HomeAgentConfigError("사용 가능한 홈 agent LLM provider가 설정되지 않았습니다.")


def resolve_home_agent_provider_configs(*, preferred_provider: str = "") -> list[HomeAgentProviderConfig]:
    requested = str(
        preferred_provider
        or os.environ.get("HOME_AGENT_LLM_PROVIDER")
        or "deepseek"
    ).strip().lower()
    fallback = str(os.environ.get("HOME_AGENT_LLM_FALLBACK_PROVIDER") or "openclaw").strip().lower()
    configs = []
    tried = []
    for provider_name in [requested, fallback]:
        if not provider_name or provider_name in tried:
            continue
        tried.append(provider_name)
        try:
            configs.append(_build_provider_config(provider_name))
        except HomeAgentConfigError:
            continue
    if not configs:
        raise HomeAgentConfigError("사용 가능한 홈 agent LLM provider가 설정되지 않았습니다.")
    return configs


def resolve_home_agent_provider(*, preferred_provider: str = "") -> HomeAgentProviderConfig:
    return resolve_home_agent_provider_configs(preferred_provider=preferred_provider)[0]


def _build_provider_config(provider_name: str) -> HomeAgentProviderConfig:
    normalized = str(provider_name or "").strip().lower()
    if normalized == "deepseek":
        api_key = str(
            os.environ.get("HOME_AGENT_LLM_API_KEY")
            or os.environ.get("MASTER_DEEPSEEK_API_KEY")
            or os.environ.get("DEEPSEEK_API_KEY")
            or ""
        ).strip()
        if not api_key:
            raise HomeAgentConfigError("DeepSeek API 키가 없습니다.")
        base_url = str(os.environ.get("HOME_AGENT_LLM_BASE_URL") or DEEPSEEK_BASE_URL).strip() or DEEPSEEK_BASE_URL
        return HomeAgentProviderConfig(
            provider="deepseek",
            model=str(os.environ.get("HOME_AGENT_LLM_MODEL") or DEEPSEEK_MODEL_NAME).strip() or DEEPSEEK_MODEL_NAME,
            base_url=base_url,
            api_key=api_key,
        )
    if normalized in {"openclaw", "local"}:
        base_url = str(
            os.environ.get("HOME_AGENT_LLM_BASE_URL")
            or os.environ.get("OPENCLAW_BASE_URL")
            or ""
        ).strip()
        if not base_url:
            raise HomeAgentConfigError("OpenClaw base URL이 없습니다.")
        base_url = _normalize_provider_base_url(base_url, provider_name="openclaw")
        return HomeAgentProviderConfig(
            provider="openclaw",
            model=str(os.environ.get("HOME_AGENT_LLM_MODEL") or os.environ.get("OPENCLAW_MODEL") or "openclaw-agent").strip() or "openclaw-agent",
            base_url=base_url,
            api_key=str(
                os.environ.get("HOME_AGENT_LLM_API_KEY")
                or os.environ.get("OPENCLAW_API_KEY")
                or OPENCLAW_DEFAULT_API_KEY
            ).strip() or OPENCLAW_DEFAULT_API_KEY,
        )
    base_url = str(os.environ.get("HOME_AGENT_LLM_BASE_URL") or "").strip()
    api_key = str(os.environ.get("HOME_AGENT_LLM_API_KEY") or "").strip()
    model = str(os.environ.get("HOME_AGENT_LLM_MODEL") or "").strip()
    if not (base_url and api_key and model):
        raise HomeAgentConfigError("커스텀 provider 설정이 완전하지 않습니다.")
    return HomeAgentProviderConfig(
        provider=normalized or "custom",
        model=model,
        base_url=base_url,
        api_key=api_key,
    )


def _build_preview_messages(
    *,
    mode_key: str,
    mode_spec: dict,
    text: str,
    selected_date_label: str,
    context: dict,
) -> list[dict]:
    context = dict(context or {})
    service_key = str(context.get("service_key") or "").strip()
    workflow_keys = _normalize_context_list(context.get("workflow_keys"), limit=5)
    tacit_rule_keys = _normalize_context_list(context.get("tacit_rule_keys"), limit=5)
    context_questions = _normalize_context_list(context.get("context_questions"), limit=6)
    signal_sources = _normalize_context_list(context.get("signal_sources"), limit=6)
    context_lines = []
    if service_key:
        context_lines.append(f"연결 서비스: {service_key}")
    if signal_sources:
        context_lines.append(f"현재 신호: {', '.join(signal_sources)}")
    if workflow_keys:
        context_lines.append(f"참고 workflow: {', '.join(workflow_keys)}")
    if tacit_rule_keys:
        context_lines.append(f"참고 tacit rule: {', '.join(tacit_rule_keys)}")
    if context_questions:
        context_lines.append(f"추가 확인 질문: {' / '.join(context_questions)}")
    schema = {
        "title": mode_spec["default_title"],
        "summary": "",
        "sections": [
            {"title": mode_spec["section_titles"][0], "items": [""]},
            {"title": mode_spec["section_titles"][1], "items": [""]},
        ],
        "note": mode_spec["default_note"],
    }
    system_prompt = (
        "당신은 교사용 홈 실행 에이전트입니다. 반드시 JSON 객체만 반환하세요. "
        "문장은 짧고 명확하게 쓰고, 한 섹션은 최대 4개 항목만 넣으세요. "
        "설명투 대신 바로 행동 가능한 표현을 사용하세요. "
        "지원 스키마는 title, summary, sections, note 입니다. "
        "제공된 workflow, tacit rule, 신호는 참고하되 없는 사실을 만들어내지 마세요."
    )
    user_prompt = "\n\n".join(
        [
            f"모드: {mode_key}",
            f"오늘 기준: {selected_date_label or '오늘'}",
            f"지시: {mode_spec['instruction']}",
            "\n".join(context_lines).strip(),
            "",
            "사용자 입력:",
            text,
            "",
            "반환 JSON 예시:",
            json.dumps(schema, ensure_ascii=False),
        ]
    ).strip()
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _normalize_preview_payload(*, mode_spec: dict, payload: dict, original_text: str) -> dict:
    title = str(payload.get("title") or mode_spec["default_title"]).strip() or mode_spec["default_title"]
    summary = str(payload.get("summary") or "").strip() or original_text[:140]
    note = str(payload.get("note") or mode_spec["default_note"]).strip() or mode_spec["default_note"]
    sections = []
    raw_sections = payload.get("sections") or []
    if isinstance(raw_sections, list):
        for index, raw_section in enumerate(raw_sections[:3]):
            if not isinstance(raw_section, dict):
                continue
            fallback_title = mode_spec["section_titles"][min(index, len(mode_spec["section_titles"]) - 1)]
            section_title = str(raw_section.get("title") or fallback_title).strip() or fallback_title
            items = []
            for item in raw_section.get("items") or []:
                text = str(item or "").strip()
                if text:
                    items.append(text[:160])
            if items:
                sections.append({"title": section_title, "items": items[:4]})
    if not sections:
        sections = [{
            "title": mode_spec["section_titles"][0],
            "items": [summary[:160]],
        }]
    return {
        "badge": mode_spec["badge"],
        "title": title[:80],
        "summary": summary[:180],
        "sections": sections,
        "note": note[:180],
    }


def _normalize_context_list(value, *, limit: int = 5) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    normalized = []
    seen = set()
    for item in value:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text[:80])
        if len(normalized) >= limit:
            break
    return normalized


def _normalize_provider_base_url(base_url: str, *, provider_name: str) -> str:
    normalized = str(base_url or "").strip().rstrip("/")
    if provider_name == "openclaw" and normalized and not normalized.endswith("/v1"):
        return f"{normalized}/v1"
    return normalized


def _call_json_response(*, config: HomeAgentProviderConfig, messages: list[dict], timeout_seconds: int = 18, attempts: int = 2) -> dict:
    last_error = None
    for attempt in range(attempts):
        try:
            raw_text = _call_with_timeout(
                lambda: _create_chat_completion(config=config, messages=messages),
                timeout_seconds=timeout_seconds,
            )
            payload = _extract_json_payload(raw_text)
            if isinstance(payload, dict):
                return payload
            raise HomeAgentProviderError("AI 응답이 JSON 객체가 아닙니다.")
        except Exception as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(0.8)
    if isinstance(last_error, HomeAgentError):
        raise last_error
    raise HomeAgentProviderError("AI preview 요청에 실패했습니다.") from last_error


def _create_chat_completion(*, config: HomeAgentProviderConfig, messages: list[dict]) -> str:
    client = OpenAI(api_key=config.api_key, base_url=config.base_url, timeout=35.0)
    kwargs = {
        "model": config.model,
        "messages": messages,
        "stream": False,
        "temperature": 0.2,
    }
    try:
        response = client.chat.completions.create(
            response_format={"type": "json_object"},
            **kwargs,
        )
    except Exception:
        response = client.chat.completions.create(**kwargs)
    text = str((response.choices[0].message.content or "")).strip()
    if text:
        return text
    raise HomeAgentProviderError("AI 응답이 비어 있습니다.")


def _extract_json_payload(raw_text: str) -> dict:
    text = str(raw_text or "").strip()
    if not text:
        raise HomeAgentProviderError("AI 응답이 비어 있습니다.")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise HomeAgentProviderError("AI 응답에서 JSON을 찾지 못했습니다.")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise HomeAgentProviderError("AI 응답 JSON 파싱에 실패했습니다.") from exc


def _call_with_timeout(callable_fn, timeout_seconds: int):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(callable_fn)
        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError as exc:
            raise HomeAgentProviderError("AI 요청 시간이 초과되었습니다.") from exc
