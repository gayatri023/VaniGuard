import asyncio
from pathlib import Path

from tests.conftest import make_audio
from vani.livecheck import Clip, load_truth, print_report, run_livecheck
from vani.pipeline.clients import ModelCall, ModelInput
from vani.pipeline.schema import ModelOutput, SelfConf
from vani.settings import load_settings

NAMES = {"priya": "Priya", "amit": "Amit"}


class Stub:
    """Plays the model: right for 'priya'; for 'amit' it CONSISTENTLY mishears 15 as 50 (transcript, amount and all samples agree)."""

    name = "stub"

    def __init__(self) -> None:
        self.clip: Clip | None = None

    async def extract(self, inp: ModelInput, temperature: float, sample_idx: int) -> ModelCall:
        c = self.clip
        assert c is not None and inp.wav
        amount = 50 if c.payee_id == "amit" else c.amount
        out = ModelOutput(transcript_roman=f"{NAMES[c.payee_id]} ko {amount} rupaye bhej do", transcript_native=None, intent="send_money",
                          payee_text=NAMES[c.payee_id], amount_text=str(amount), amount_value=amount, note=None,
                          self_conf=SelfConf(payee=0.95, amount=0.95, intent=0.95), speech_detected=True, language_mix="mixed")  # fmt: skip
        return ModelCall(out, tokens_in=100, tokens_out=20)


def test_livecheck_reports_accuracy_tiers_latency_and_wrong_fast_path(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    make_audio(tmp_path / "priya_150.wav", [])
    make_audio(tmp_path / "amit_15.wav", [])
    (tmp_path / "truth.csv").write_text("file,payee_id,amount\npriya_150.wav,priya,150\namit_15.wav,amit,15\n")
    stub = Stub()
    st = load_settings({"VANI_DEV": "1"})
    rep = asyncio.run(run_livecheck(load_truth(tmp_path), st, stub, on_clip=lambda c: setattr(stub, "clip", c)))
    assert rep["n"] == 2 and rep["accuracy"] == 0.5
    by = {r["file"]: r for r in rep["rows"]}
    assert by["priya_150.wav"]["ok"] and by["priya_150.wav"]["tier"] == "A"
    # A consistent mishearing contradicts nothing the system can check, so at the v1 placeholder thresholds it takes the fast path.
    # That is the project's core risk, and the live check must surface it loudly rather than hide it.
    assert not by["amit_15.wav"]["ok"] and by["amit_15.wav"]["tier"] == "A" and by["amit_15.wav"]["fast_wrong"]
    assert rep["fast_wrong"] == 1 and rep["latency_ms"]["total"]["p95"] > 0 and "model" in rep["latency_ms"]
    print_report(rep)
    assert "WRONG FAST-PATH: 1" in capsys.readouterr().out
