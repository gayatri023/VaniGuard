import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vani.app import create_app
from vani.pipeline.clients import FakeClient
from vani.settings import load_settings


@pytest.fixture
def settings(tmp_path: Path):  # type: ignore[no-untyped-def]
    return load_settings({"VANI_DEV": "1", "DATABASE_URL": f"sqlite:///{tmp_path}/t.db"})


@pytest.fixture
def app(settings):  # type: ignore[no-untyped-def]
    return create_app(settings, FakeClient(0))


@pytest.fixture
def c(app) -> TestClient:  # type: ignore[no-untyped-def]
    return TestClient(app)


@pytest.fixture
def prod_client(settings, tmp_path):  # type: ignore[no-untyped-def]
    """Same app with dev switched off: no debug payload, no dev transcript path."""
    return TestClient(create_app(replace(settings, dev=False), FakeClient(0)))


def new_session(c: TestClient) -> tuple[str, str]:
    r = c.post("/api/sessions", json={"consent_version": "v1", "language_comfort": "balanced",
                                      "noise_self_report": "quiet"})  # fmt: skip
    assert r.status_code == 200, r.text
    return r.json()["session_id"], r.json()["deletion_code"]


_n = 0


def send(c: TestClient, sid: str, card: str, text: str, overrides: dict | None = None, rid: str | None = None):  # type: ignore[no-untyped-def]
    import json

    global _n
    _n += 1
    data = {"session_id": sid, "card_id": card, "client_request_id": rid or f"r{_n}", "dev_transcript": text}
    if overrides:
        data["dev_overrides"] = json.dumps(overrides)
    return c.post("/api/commands", data=data)


def make_audio(path: Path, codec_args: list[str], seconds: float = 1.0) -> bytes:
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
           "-ar", "16000", "-ac", "1", *codec_args, str(path)]  # fmt: skip
    r = subprocess.run(cmd, check=False, capture_output=True)
    if r.returncode != 0:
        pytest.skip(f"ffmpeg cannot encode {codec_args}: {r.stderr.decode()[:120]}")
    return path.read_bytes()
