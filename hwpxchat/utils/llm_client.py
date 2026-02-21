import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError

import requests
from google import genai


class LlmClientError(Exception):
    """Raised when LLM request fails."""


def generate_chat_response(*, provider, prompt, user=None, timeout_seconds=40):
    provider_name = (provider or "gemini").strip().lower()

    if provider_name == "claude":
        return _generate_with_claude(prompt=prompt, timeout_seconds=timeout_seconds)

    return _generate_with_gemini(
        prompt=prompt,
        user=user,
        timeout_seconds=timeout_seconds,
    )


def _generate_with_gemini(*, prompt, user=None, timeout_seconds=40):
    api_key = _get_gemini_api_key(user)
    if not api_key:
        raise LlmClientError("Gemini API key is not configured.")

    model_name = os.environ.get("MASTER_GEMINI_MODEL", "gemini-2.5-flash-lite")

    def _call():
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        text = (getattr(response, "text", None) or "").strip()
        if text:
            return text
        raise LlmClientError("Gemini returned an empty response.")

    return _call_with_retry_and_timeout(_call, timeout_seconds=timeout_seconds)


def _generate_with_claude(*, prompt, timeout_seconds=40):
    api_key = os.environ.get("MASTER_CLAUDE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise LlmClientError("Claude API key is not configured.")

    endpoint = os.environ.get("MASTER_CLAUDE_ENDPOINT", "https://api.anthropic.com/v1/messages")
    model_name = os.environ.get("MASTER_CLAUDE_MODEL", "claude-3-5-sonnet-latest")
    max_tokens = int(os.environ.get("MASTER_CLAUDE_MAX_TOKENS", "1024"))

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model_name,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }

    def _call():
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=(5, timeout_seconds),
        )
        if response.status_code >= 400:
            raise LlmClientError(f"Claude request failed with status {response.status_code}.")

        data = response.json()
        content_blocks = data.get("content") or []
        text_parts = [
            (block.get("text") or "").strip()
            for block in content_blocks
            if block.get("type") == "text"
        ]
        text = "\n".join(part for part in text_parts if part).strip()
        if text:
            return text
        raise LlmClientError("Claude returned an empty response.")

    return _call_with_retry_and_timeout(_call, timeout_seconds=timeout_seconds)


def _call_with_retry_and_timeout(callable_fn, timeout_seconds, attempts=2):
    last_error = None
    for idx in range(attempts):
        try:
            return _run_with_timeout(callable_fn, timeout_seconds=timeout_seconds)
        except Exception as exc:
            last_error = exc
            if idx < attempts - 1:
                time.sleep(1.0)

    if isinstance(last_error, LlmClientError):
        raise last_error
    raise LlmClientError("LLM API call failed.") from last_error


def _run_with_timeout(callable_fn, timeout_seconds):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(callable_fn)
        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError as exc:
            raise LlmClientError("LLM request timed out.") from exc


def _get_gemini_api_key(user):
    if user and getattr(user, "is_authenticated", False):
        try:
            profile = getattr(user, "userprofile", None)
            key = (getattr(profile, "gemini_api_key", "") or "").strip()
            if key:
                return key
        except Exception:
            pass

    return (
        os.environ.get("MASTER_GEMINI_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or ""
    ).strip()

