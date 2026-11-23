"""The JSON the model must return. No defaults on purpose: keeps the Gemini schema simple."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SelfConf(BaseModel):
    payee: float | None
    amount: float | None
    intent: float | None


class ModelOutput(BaseModel):
    transcript_roman: str
    transcript_native: str | None
    intent: Literal["send_money", "other", "unclear"]
    payee_text: str | None
    amount_text: str | None
    amount_value: int | None
    note: str | None
    self_conf: SelfConf
    speech_detected: bool
    language_mix: Literal["hi", "en", "mixed"]
