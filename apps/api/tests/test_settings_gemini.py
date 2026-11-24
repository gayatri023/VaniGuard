from types import SimpleNamespace

import pytest

from vani.pipeline.clients import GeminiClient, output_from, usage_from
from vani.pipeline.schema import ModelOutput
from vani.settings import (
    ConfigError,
    Pricing,
    _parse_dotenv,
    compute_cost,
    load_dotenv_files,
    load_settings,
)


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


def test_dotenv_parser_handles_what_windows_editors_produce() -> None:
    text = "\ufeff# a comment\r\nGEMINI_API_KEY=abc123\r\nexport GEMINI_MODEL='some-model'\r\nDAILY_COST_CAP_USD=2   # inline comment\r\nQUOTED=\"has # hash\"\r\n\r\nnot a line\r\n"
    parsed = _parse_dotenv(text.lstrip("\ufeff"))
    assert parsed == {"GEMINI_API_KEY": "abc123", "GEMINI_MODEL": "some-model", "DAILY_COST_CAP_USD": "2", "QUOTED": "has # hash"}


def test_dotenv_files_never_override_real_environment_variables(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "api.env").write_bytes("\ufeffGEMINI_MODEL=from-api-env\r\nONLY_API=1\r\n".encode())  # BOM + CRLF, like Notepad
    (tmp_path / "root.env").write_text("GEMINI_MODEL=from-root-env\nGEMINI_API_KEY=k\nONLY_ROOT=1\n")
    env = {"GEMINI_API_KEY": "real-env-wins"}
    loaded = load_dotenv_files([tmp_path / "api.env", tmp_path / "root.env", tmp_path / "missing.env"], env)
    assert [p.name for p in loaded] == ["api.env", "root.env"]
    assert env == {"GEMINI_API_KEY": "real-env-wins", "GEMINI_MODEL": "from-api-env", "ONLY_API": "1", "ONLY_ROOT": "1"}


def test_live_settings_can_come_entirely_from_a_dotenv_file(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    f = tmp_path / ".env"
    f.write_text("VANI_DEV=1\nDATABASE_URL=sqlite:///x.db\n")
    env: dict[str, str] = {}
    load_dotenv_files([f], env)
    s = load_settings(env)
    assert s.dev and s.database_url == "sqlite:///x.db" and s.backend == "fake"
