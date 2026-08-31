import base64

import pytest

from app.audiobook import AudiobookGenerator, _decode_audio_data, _resolve_qwen_customization_endpoint


def test_audiobook_generator_allows_script_only_construction() -> None:
    generator = AudiobookGenerator(llm_client=object(), llm_model="gpt-4.1-mini")
    assert generator.tts_client is None
    assert generator.tts_model == ""


def test_resolve_qwen_customization_endpoint_for_dashscope() -> None:
    endpoint = _resolve_qwen_customization_endpoint(
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    assert endpoint == "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"


def test_resolve_qwen_customization_endpoint_keeps_prefix_path() -> None:
    endpoint = _resolve_qwen_customization_endpoint(
        "https://example.com/proxy/compatible-mode/v1"
    )
    assert endpoint == "https://example.com/proxy/api/v1/services/audio/tts/customization"


def test_resolve_qwen_customization_endpoint_for_local_v1() -> None:
    endpoint = _resolve_qwen_customization_endpoint("http://127.0.0.1:8091/v1")
    assert endpoint == "http://127.0.0.1:8091/api/v1/services/audio/tts/customization"


def test_resolve_qwen_customization_endpoint_requires_valid_url() -> None:
    with pytest.raises(ValueError):
        _resolve_qwen_customization_endpoint("not-a-valid-url")


def test_decode_audio_data_accepts_plain_base64() -> None:
    expected = b"sample-audio"
    encoded = base64.b64encode(expected).decode("ascii")
    assert _decode_audio_data(encoded) == expected


def test_decode_audio_data_accepts_data_uri() -> None:
    expected = b"sample-audio"
    encoded = base64.b64encode(expected).decode("ascii")
    data_uri = f"data:audio/wav;base64,{encoded}"
    assert _decode_audio_data(data_uri) == expected


def test_decode_audio_data_rejects_invalid_payload() -> None:
    with pytest.raises(ValueError):
        _decode_audio_data("not-base64")
