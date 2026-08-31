import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.summarizer import normalize_provider

_HTTP_TIMEOUT_SEC = 20


def _request_json(url: str, *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SEC) as response:
        body = response.read().decode("utf-8", errors="replace")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("모델 목록 응답을 JSON으로 파싱할 수 없습니다.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("모델 목록 응답 형식이 올바르지 않습니다.")

    return payload


def _sort_model_ids(items: list[str]) -> list[str]:
    return sorted(items, key=lambda value: value.casefold())


def _unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _extract_model_ids(payload: dict[str, Any]) -> list[str]:
    rows = payload.get("data")
    if not isinstance(rows, list):
        return []

    model_ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        model_id = row.get("id")
        if isinstance(model_id, str) and model_id.strip():
            model_ids.append(model_id.strip())

    return _unique_preserve_order(model_ids)


def _fetch_openai_models(api_key: str) -> list[str]:
    if not api_key:
        raise ValueError("OPEN-AI 모델 목록 조회에는 API Key가 필요합니다.")

    payload = _request_json(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return _extract_model_ids(payload)


def _fetch_anthropic_models(api_key: str) -> list[str]:
    if not api_key:
        raise ValueError("ANTHROPIC 모델 목록 조회에는 API Key가 필요합니다.")

    model_ids: list[str] = []
    after_id = ""

    while True:
        query = {"limit": "100"}
        if after_id:
            query["after_id"] = after_id

        url = f"https://api.anthropic.com/v1/models?{urllib.parse.urlencode(query)}"
        payload = _request_json(
            url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        model_ids.extend(_extract_model_ids(payload))

        has_more = bool(payload.get("has_more"))
        last_id = payload.get("last_id")
        if not has_more or not isinstance(last_id, str) or not last_id:
            break
        after_id = last_id

    return _unique_preserve_order(model_ids)


def _fetch_openrouter_models(api_key: str) -> list[str]:
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        url = "https://openrouter.ai/api/v1/models/user"
    else:
        url = "https://openrouter.ai/api/v1/models"

    payload = _request_json(url, headers=headers)
    return _extract_model_ids(payload)


def _fetch_venice_models(api_key: str) -> list[str]:
    if not api_key:
        raise ValueError("Venice 모델 목록 조회에는 API Key가 필요합니다.")

    payload = _request_json(
        "https://api.venice.ai/api/v1/models?type=text",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return _extract_model_ids(payload)


def _fetch_kilo_models(_api_key: str) -> list[str]:
    payload = _request_json("https://api.kilo.ai/api/gateway/models")
    return _extract_model_ids(payload)


def _fetch_opencode_go_models(api_key: str) -> list[str]:
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = _request_json("https://opencode.ai/zen/go/v1/models", headers=headers)
    return _extract_model_ids(payload)


def fetch_provider_models(provider: str, *, api_key: str = "") -> list[str]:
    normalized = normalize_provider(provider)
    key = (api_key or "").strip()

    try:
        if normalized == "openai":
            models = _fetch_openai_models(key)
        elif normalized == "anthropic":
            models = _fetch_anthropic_models(key)
        elif normalized == "openrouter":
            models = _fetch_openrouter_models(key)
        elif normalized == "venice":
            models = _fetch_venice_models(key)
        elif normalized == "kilo-code":
            models = _fetch_kilo_models(key)
        elif normalized == "opencode-go":
            models = _fetch_opencode_go_models(key)
        else:
            raise ValueError(f"지원하지 않는 provider 입니다: {provider}")
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"{provider} 모델 목록 조회 실패 (HTTP {exc.code}): {message[:300]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{provider} 모델 목록 조회 네트워크 오류: {exc.reason}") from exc

    if not models:
        raise RuntimeError(f"{provider} 모델 목록이 비어 있습니다.")

    return _sort_model_ids(models)
