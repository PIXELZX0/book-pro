import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.provider_models as provider_models
from app.main import app
from app.summarizer import (
    _PROVIDER_ALIASES,
    _PROVIDER_BASE_URL,
    _PROVIDER_DEFAULT_MODEL,
    normalize_provider,
    resolve_default_model,
)

client = TestClient(app)

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
ZEN_ALIASES = ["opencode-zen", "opencode_zen", "opencode zen", "opencodezen", "zen"]


def _panel_providers() -> list[str]:
    source = (WEB_DIR / "static" / "common.js").read_text(encoding="utf-8")
    match = re.search(r"const PROVIDERS = \[(.*?)\];", source, re.DOTALL)
    assert match, "web/static/common.js에서 PROVIDERS 배열을 찾을 수 없습니다."
    return re.findall(r'"([^"]+)"', match.group(1))


@pytest.mark.parametrize("value", ZEN_ALIASES)
def test_normalize_provider_accepts_zen_aliases(value: str) -> None:
    assert normalize_provider(value) == "opencode-zen"


def test_zen_provider_configuration() -> None:
    assert _PROVIDER_BASE_URL["opencode-zen"] == "https://opencode.ai/zen/v1"
    assert _PROVIDER_DEFAULT_MODEL["opencode-zen"] == "grok-4.6"
    assert resolve_default_model("opencode-zen") == "grok-4.6"


def test_zen_does_not_shadow_go_provider() -> None:
    assert normalize_provider("opencode-go") == "opencode-go"
    assert _PROVIDER_BASE_URL["opencode-go"] == "https://opencode.ai/zen/go/v1"


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_provider("not-a-provider")


def test_provider_tables_are_in_sync() -> None:
    assert set(_PROVIDER_BASE_URL) == set(_PROVIDER_DEFAULT_MODEL)
    assert set(_PROVIDER_BASE_URL) == set(_PROVIDER_ALIASES.values())


def test_fetch_zen_models_uses_zen_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_request_json(url: str, *, headers: dict[str, str] | None = None) -> dict:
        captured["url"] = url
        captured["headers"] = headers or {}
        return {"data": [{"id": "grok-4.6"}, {"id": "claude-sonnet-4-5"}, {"id": "grok-4.6"}]}

    monkeypatch.setattr(provider_models, "_request_json", fake_request_json)

    models = provider_models.fetch_provider_models("opencode-zen", api_key="zen-key")

    assert models == ["claude-sonnet-4-5", "grok-4.6"]
    assert captured["url"] == "https://opencode.ai/zen/v1/models"
    assert captured["headers"] == {"Authorization": "Bearer zen-key"}


def test_request_json_sends_browser_like_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[object] = []

    class _FakeResponse:
        def read(self) -> bytes:
            return b'{"data": []}'

        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, *args: object) -> bool:
            return False

    def fake_urlopen(request: object, *, timeout: float) -> _FakeResponse:
        captured.append(request)
        return _FakeResponse()

    monkeypatch.setattr(provider_models.urllib.request, "urlopen", fake_urlopen)

    provider_models._request_json("https://example.com/models", headers={"x-api-key": "k"})

    request = captured[0]
    user_agent = request.get_header("User-agent")  # type: ignore[attr-defined]
    assert user_agent and not user_agent.lower().startswith("python-urllib")
    assert request.get_header("X-api-key") == "k"  # type: ignore[attr-defined]


def test_provider_models_endpoint_returns_zen_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        provider_models,
        "_request_json",
        lambda url, *, headers=None: {"data": [{"id": "grok-4.6"}]},
    )

    response = client.post("/providers/models", data={"provider": "zen"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "opencode-zen"
    assert payload["models"] == ["grok-4.6"]


def test_provider_models_endpoint_rejects_unknown_provider() -> None:
    response = client.post("/providers/models", data={"provider": "not-a-provider"})
    assert response.status_code == 400


def test_panel_provider_list_matches_backend() -> None:
    panel = {normalize_provider(provider) for provider in _panel_providers()}
    assert panel == set(_PROVIDER_ALIASES.values())


def test_panel_renders_controls_for_every_provider() -> None:
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    for provider in _panel_providers():
        assert f'value="{provider}"' in html
        assert f'id="api-key-{provider}"' in html


def test_studio_page_shares_common_settings_and_controls() -> None:
    studio_html = (WEB_DIR / "studio.html").read_text(encoding="utf-8")
    assert '<script src="/static/common.js"></script>' in studio_html
    assert 'id="studio-settings-provider-select"' in studio_html
    assert 'id="studio-settings-api-key-input"' in studio_html
    assert 'id="studio-agent-toggle"' in studio_html

    studio_js = (WEB_DIR / "static" / "studio.js").read_text(encoding="utf-8")
    common_js = (WEB_DIR / "static" / "common.js").read_text(encoding="utf-8")
    for provider in _panel_providers():
        assert provider in common_js
    assert "agent/stream" in studio_js
    assert "registerI18nMessages" in studio_js

    app_js = (WEB_DIR / "static" / "app.js").read_text(encoding="utf-8")
    assert "registerI18nMessages" in app_js
    assert "const PROVIDERS = [" not in app_js
