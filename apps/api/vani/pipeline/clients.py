"""Model clients. GeminiClient is the real one; FakeClient is the dev simulator that lets
the whole product run (and be tested) without an API key or a microphone."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..domain.numbers import parse_amounts
from .schema import ModelOutput, SelfConf


@dataclass
class DevInput:
    transcript: str
    amount_value: int | None = None  # what the "model" returns for the amount (default: best parse)
    self_conf: float = 0.9
    intent: str = "send_money"
    sample_amounts: list[int | None] | None = None  # per-sample amounts, to simulate disagreement
    fail_samples: list[int] = field(default_factory=list)


@dataclass
class ModelInput:
    wav: bytes | None = None
    dev: DevInput | None = None


@dataclass
class ModelCall:
    output: ModelOutput
    tokens_in: int = 0
    tokens_out: int = 0
    audio_tokens_in: int | None = None
    latency_ms: int = 0


class ModelClient(Protocol):
    name: str

    async def extract(self, inp: ModelInput, temperature: float, sample_idx: int) -> ModelCall: ...


class FakeClient:
    name = "dev-simulator"

    def __init__(self, delay_s: float = 0.0) -> None:
        self.delay_s = delay_s

    async def extract(self, inp: ModelInput, temperature: float, sample_idx: int) -> ModelCall:
        await asyncio.sleep(self.delay_s)
        d = inp.dev
        if d is None:  # real audio but no real model: nothing intelligible
            out = ModelOutput(
                transcript_roman="", transcript_native=None, intent="unclear", payee_text=None,
                amount_text=None, amount_value=None, note=None,
                self_conf=SelfConf(payee=0.0, amount=0.0, intent=0.0),
                speech_detected=False, language_mix="mixed",
            )  # fmt: skip
            return ModelCall(out)
        if sample_idx in d.fail_samples:
            raise RuntimeError("simulated model failure")
        text = d.transcript
        payee = text.split(" ko ")[0].strip() if " ko " in text else None
        cands = parse_amounts(text, ignore=payee or "")
        if d.sample_amounts is not None and sample_idx < len(d.sample_amounts):
            amount = d.sample_amounts[sample_idx]
        else:
            amount = d.amount_value if d.amount_value is not None else (cands[0].value if cands else None)
        c = d.self_conf
        out = ModelOutput(
            transcript_roman=text, transcript_native=None,
            intent=d.intent if d.intent in ("send_money", "other", "unclear") else "unclear",  # type: ignore[arg-type]
            payee_text=payee, amount_text=cands[0].text if cands else None, amount_value=amount,
            note=None, self_conf=SelfConf(payee=c, amount=c, intent=c),
            speech_detected=bool(text.strip()), language_mix="mixed",
        )  # fmt: skip
        return ModelCall(out)


class GeminiClient:
    """Real client (google-genai). Needs GEMINI_API_KEY and GEMINI_MODEL; untested against the live API here."""

    def __init__(
        self, api_key: str, model: str, system_prompt: str,
        timeout_s: float = 8.0, thinking_budget: int | None = None,
    ) -> None:  # fmt: skip
        from google import genai
        from google.genai import types

        self.name = model
        self._types = types
        self._model = model
        self._thinking_budget = thinking_budget
        self._system_prompt = system_prompt
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000))
        )

    def build_config(self, temperature: float) -> Any:
        t = self._types
        kwargs: dict[str, Any] = {
            "system_instruction": self._system_prompt,
            "temperature": temperature,
            "response_mime_type": "application/json",
            "response_schema": ModelOutput,
        }
        if self._thinking_budget is not None:  # only sent if you set GEMINI_THINKING_BUDGET
            kwargs["thinking_config"] = t.ThinkingConfig(thinking_budget=self._thinking_budget)
        return t.GenerateContentConfig(**kwargs)

    async def extract(self, inp: ModelInput, temperature: float, sample_idx: int) -> ModelCall:
        if inp.wav is None:
            raise ValueError("GeminiClient needs audio")
        t = self._types
        started = time.perf_counter()
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=[
                "Extract the payment command from this audio.",
                t.Part.from_bytes(data=inp.wav, mime_type="audio/wav"),
            ],
            config=self.build_config(temperature),
        )
        tin, tout, audio = usage_from(resp)
        return ModelCall(
            output_from(resp), tin, tout, audio, int((time.perf_counter() - started) * 1000)
        )


def output_from(resp: Any) -> ModelOutput:
    parsed = getattr(resp, "parsed", None)
    if isinstance(parsed, ModelOutput):
        return parsed
    return ModelOutput.model_validate_json(resp.text)


def usage_from(resp: Any) -> tuple[int, int, int | None]:
    u = getattr(resp, "usage_metadata", None)
    if u is None:
        return 0, 0, None
    tin = int(getattr(u, "prompt_token_count", 0) or 0)
    tout = int(getattr(u, "candidates_token_count", 0) or 0) + int(getattr(u, "thoughts_token_count", 0) or 0)
    audio = None
    for d in getattr(u, "prompt_tokens_details", None) or []:
        if str(getattr(d, "modality", "")).upper().endswith("AUDIO"):
            audio = int(getattr(d, "token_count", 0) or 0)
    return tin, tout, audio
