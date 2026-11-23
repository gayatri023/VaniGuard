from types import SimpleNamespace

import pytest

from vani.pipeline.clients import GeminiClient, output_from, usage_from
from vani.pipeline.schema import ModelOutput
from vani.settings import ConfigError, Pricing, compute_cost, load_settings


def test_live_mode_refuses_to_start_when_misconfigured() -> None:
    with pytest.raises(ConfigError) as e:
        load_settings({})  # no dev flag => gemini backend
    msg = str(e.value)
    assert "GEMINI_API_KEY" in msg and "GEMINI_MODEL" in msg and "COST_CAP" in msg and "pricing.yaml" in msg


def test_simulator_is_dev_only() -> None:
    with pytest.raises(ConfigError, match="only allowed with VANI_DEV"):
        load_settings({"VANI_MODEL_BACKEND": "fake"})
    assert load_settings({"VANI_DEV": "1"}).backend == "fake"


def test_cost_math() -> None:
    p = Pricing("v", "m", 1.0, 4.0, 2.0)
    assert compute_cost(p, 1_000_000, 500_000) == pytest.approx(3.0)
    assert compute_cost(p, 1_000_000, 0, audio_in=500_000) == pytest.approx(1.5)


def test_gemini_client_builds_config_and_parses_offline() -> None:
    g = GeminiClient("not-a-real-key", "some-model", "PROMPT", thinking_budget=0)
    cfg = g.build_config(0.7)
    assert cfg.temperature == 0.7 and cfg.response_mime_type == "application/json"
    assert cfg.response_schema is ModelOutput and cfg.thinking_config.thinking_budget == 0
    assert GeminiClient("k", "m", "P").build_config(0.0).thinking_config is None
    from google.genai import _transformers as t

    schema = t.t_schema(g._client._api_client, ModelOutput)  # the SDK accepts our schema without a network call
    assert "amount_value" in schema.properties and "self_conf" in schema.properties

    payload = {"transcript_roman": "x", "transcript_native": None, "intent": "send_money", "payee_text": "Priya",
               "amount_text": "bees", "amount_value": 20, "note": None,
               "self_conf": {"payee": 0.9, "amount": 0.9, "intent": 0.9}, "speech_detected": True, "language_mix": "hi"}  # fmt: skip
    import json

    resp = SimpleNamespace(parsed=None, text=json.dumps(payload), usage_metadata=SimpleNamespace(
        prompt_token_count=100, candidates_token_count=20, thoughts_token_count=5,
        prompt_tokens_details=[SimpleNamespace(modality="MediaModality.AUDIO", token_count=60)]))  # fmt: skip
    assert output_from(resp).amount_value == 20
    assert usage_from(resp) == (100, 25, 60)
    with pytest.raises(Exception):  # noqa: B017 - malformed JSON must raise so the sample counts as failed
        output_from(SimpleNamespace(parsed=None, text="{oops"))
