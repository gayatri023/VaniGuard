"""Environment settings. Misconfiguration fails at startup with a clear message."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import Settings as RouterSettings
from .config import load_settings as load_router_settings

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Pricing:
    version: str
    model: str
    usd_per_m_input: float
    usd_per_m_output: float
    usd_per_m_audio_input: float | None = None


def load_pricing(path: Path) -> Pricing | None:
    raw = yaml.safe_load(path.read_text()) or {}
    need = ("pricing_version", "model", "usd_per_million_input_tokens", "usd_per_million_output_tokens")
    if any(raw.get(k) is None for k in need):
        return None
    audio = raw.get("usd_per_million_audio_input_tokens")
    return Pricing(
        str(raw["pricing_version"]), str(raw["model"]),
        float(raw["usd_per_million_input_tokens"]), float(raw["usd_per_million_output_tokens"]),
        float(audio) if audio is not None else None,
    )  # fmt: skip


def compute_cost(p: Pricing, tokens_in: int, tokens_out: int, audio_in: int | None = None) -> float:
    audio = min(audio_in or 0, tokens_in)
    audio_rate = p.usd_per_m_audio_input if p.usd_per_m_audio_input is not None else p.usd_per_m_input
    return ((tokens_in - audio) * p.usd_per_m_input + audio * audio_rate
            + tokens_out * p.usd_per_m_output) / 1_000_000  # fmt: skip


@dataclass(frozen=True)
class Settings:
    dev: bool
    backend: str  # "fake" (dev simulator) or "gemini"
    database_url: str
    allowed_origins: tuple[str, ...]
    app_version: str
    gemini_api_key: str | None
    gemini_model: str | None
    gemini_thinking_budget: int | None
    daily_cost_cap_usd: float
    session_cost_cap_usd: float
    study_paused: bool
    arms_enabled: bool
    probes_enabled: bool
    probe_rate: float
    max_probes_per_session: int
    admin_token: str | None
    trust_proxy: bool
    rate_per_ip_per_min: int
    rate_per_session_per_min: int
    max_commands_per_session: int
    pricing: Pricing | None
    prompt_version: str
    prompt_text: str
    router: RouterSettings


def _parse_dotenv(text: str) -> dict[str, str]:
    """Minimal .env parser: KEY=value, optional `export`, quotes, comments, CRLF."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        line = line.removeprefix("export ")
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if val[:1] in ("'", '"'):
            end = val.find(val[0], 1)
            val = val[1:end] if end != -1 else val[1:]
        else:
            val = val.split(" #")[0].strip()
        if key.isidentifier():
            out[key] = val
    return out


def load_dotenv_files(paths: list[Path] | None = None, environ: dict[str, str] | None = None) -> list[Path]:
    """Fill the environment from .env files WITHOUT overriding variables that are already set.
    Precedence: real environment, then apps/api/.env, then the repo-root .env. Files are never committed."""
    target: Any = os.environ if environ is None else environ
    loaded: list[Path] = []
    for path in paths if paths is not None else [REPO_ROOT / "apps" / "api" / ".env", REPO_ROOT / ".env"]:
        if path.is_file():
            for k, v in _parse_dotenv(path.read_text(encoding="utf-8-sig")).items():  # utf-8-sig: Notepad adds a BOM
                target.setdefault(k, v)
            loaded.append(path)
    return loaded


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "on"}


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    if env is None:
        load_dotenv_files()
    e = os.environ if env is None else env
    dev = _truthy(e.get("VANI_DEV"))
    backend = (e.get("VANI_MODEL_BACKEND") or ("fake" if dev else "gemini")).strip().lower()
    problems: list[str] = []
    if backend not in ("fake", "gemini"):
        problems.append("VANI_MODEL_BACKEND must be 'fake' or 'gemini'")
    if backend == "fake" and not dev:
        problems.append("VANI_MODEL_BACKEND=fake is only allowed with VANI_DEV=1 (never run the study on the simulator)")

    pricing = load_pricing(CONFIG_DIR / "pricing.yaml")
    daily = float(e.get("DAILY_COST_CAP_USD") or (1e9 if dev else 0))
    session = float(e.get("SESSION_COST_CAP_USD") or (1e9 if dev else 0))
    key, model = e.get("GEMINI_API_KEY") or None, e.get("GEMINI_MODEL") or None
    if backend == "gemini":
        for name, val in (("GEMINI_API_KEY", key), ("GEMINI_MODEL", model)):
            if not val:
                problems.append(f"{name} is required (pin the exact model string from AI Studio)")
        if len(e.get("ADMIN_TOKEN") or "") < 16:
            problems.append("ADMIN_TOKEN is required in live mode (at least 16 characters)")
        if daily <= 0 or session <= 0:
            problems.append("DAILY_COST_CAP_USD and SESSION_COST_CAP_USD must be set above 0")
        if pricing is None:
            problems.append("config/pricing.yaml has null values: copy current prices from the AI Studio pricing page")
        elif model and pricing.model != model:
            problems.append(f"config/pricing.yaml model '{pricing.model}' does not match GEMINI_MODEL '{model}'")
    if problems:
        raise ConfigError("Vani-Guard cannot start:\n  - " + "\n  - ".join(problems))

    prompt_path = CONFIG_DIR / "prompts" / "extract_v1.txt"
    budget = e.get("GEMINI_THINKING_BUDGET")
    origins = tuple(o.strip() for o in (e.get("ALLOWED_ORIGINS") or "http://localhost:3000").split(",") if o.strip())
    return Settings(
        dev=dev, backend=backend,
        database_url=e.get("DATABASE_URL") or "sqlite:///./vani.db",
        allowed_origins=origins, app_version=e.get("APP_VERSION") or "0.1.0",
        gemini_api_key=key, gemini_model=model,
        gemini_thinking_budget=int(budget) if budget not in (None, "") else None,
        daily_cost_cap_usd=daily, session_cost_cap_usd=session,
        study_paused=_truthy(e.get("STUDY_PAUSED")),
        arms_enabled=_truthy(e.get("ARMS_ENABLED")),
        probes_enabled=_truthy(e.get("PROBES_ENABLED")),
        probe_rate=float(e.get("PROBE_RATE") or 0.10),
        max_probes_per_session=int(e.get("MAX_PROBES_PER_SESSION") or 2),
        admin_token=e.get("ADMIN_TOKEN") or ("dev-admin-token" if dev else None),
        trust_proxy=_truthy(e.get("TRUST_PROXY")),
        rate_per_ip_per_min=int(e.get("RATE_PER_IP_PER_MIN") or 120),
        rate_per_session_per_min=int(e.get("RATE_PER_SESSION_PER_MIN") or 20),
        max_commands_per_session=int(e.get("MAX_COMMANDS_PER_SESSION") or 40),
        pricing=pricing, prompt_version=prompt_path.stem, prompt_text=prompt_path.read_text(),
        router=load_router_settings(CONFIG_DIR / "router.yaml"),
    )  # fmt: skip
