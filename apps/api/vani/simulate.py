"""Synthetic participants, for developing and testing the dashboard and analysis pipeline.

!! EVERYTHING PRODUCED HERE IS FAKE. Rows carry model='synthetic-sim'; the dashboard and the analysis
!! print a SYNTHETIC banner whenever such rows exist. The error rates and behaviours below are invented
!! simulation parameters, not findings. Never quote a number from synthetic data.
!! Participant behaviour is seeded, but session ids (and so card assignment) are random, so two runs differ.

    python -m vani.simulate --n 40 --db sqlite:///data/synthetic.db
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Any

from .cards import CONFIG_DIR_CARDS, Card, load_contacts, load_groups
from .domain.numbers import confusable_partner
from .pipeline.clients import ModelCall, ModelInput
from .pipeline.schema import ModelOutput, SelfConf
from .settings import load_settings

# invented per-tag base error rates (probability a command's parse is systematically wrong)
TAG_ERR = {"easy_clear": 0.03, "number_word_hard": 0.10, "confusable_amount": 0.22, "similar_payee": 0.18,
           "code_mixed_english": 0.06, "long_note": 0.07, "background_noise_prompt": 0.20, "fast_speech": 0.12}  # fmt: skip


class NoisyClient:
    """Pretends to be the model: mostly right, sometimes confidently wrong, errors correlated across samples."""

    name = "synthetic-sim"

    def __init__(self, seed: int, names: dict[str, str], groups: dict[str, str]) -> None:
        self.seed, self.names, self.groups = seed, names, groups
        self.current: Card | None = None
        self.noise_boost = 0.0
        self.n = 0
        self._inp: ModelInput | None = None
        self._lat: dict[str, Any] = {}

    def _new_command(self, card: Card) -> None:
        self.n += 1
        rng = random.Random(f"{self.seed}:{self.n}")
        p_ok = 1.0
        for t in card.condition_tags:
            p_ok *= 1 - TAG_ERR.get(t, 0.03)
        p_err = min(0.9, (1 - p_ok) + self.noise_boost)
        siblings = [p for p, g in self.groups.items() if g == self.groups[card.truth_payee_id] and p != card.truth_payee_id and g != "other"]
        alt_amount = confusable_partner(card.truth_amount) or (card.truth_amount * 10 if card.truth_amount < 1000 else card.truth_amount // 10)
        kind = rng.random()
        self._lat = {
            "amount": rng.random() < p_err and (kind < 0.7 or not siblings),
            "payee": rng.random() < p_err and kind >= 0.7 and bool(siblings),
            "alt_amount": alt_amount, "alt_payee": rng.choice(siblings) if siblings else None,
            "asr": rng.random() < 0.6,  # the transcript itself carries the error (validators cannot catch it)
            "no_speech": rng.random() < 0.015, "api_fail": rng.random() < 0.005,
        }  # fmt: skip

    async def extract(self, inp: ModelInput, temperature: float, sample_idx: int) -> ModelCall:
        card = self.current
        assert card is not None
        if self._inp is not inp:
            self._new_command(card)
            self._inp = inp
        L = self._lat
        rng = random.Random(f"{self.seed}:{self.n}:{sample_idx}")
        if L["api_fail"] and sample_idx == 2:
            raise RuntimeError("simulated API failure")
        if L["no_speech"]:
            out = ModelOutput(transcript_roman="", transcript_native=None, intent="unclear", payee_text=None, amount_text=None,
                              amount_value=None, note=None, self_conf=SelfConf(payee=0.1, amount=0.1, intent=0.1),
                              speech_detected=False, language_mix="mixed")  # fmt: skip
            return ModelCall(out)
        sys_a = L["amount"] and rng.random() < 0.75
        sys_p = L["payee"] and rng.random() < 0.75
        rnd_a = temperature > 0 and rng.random() < 0.05
        rnd_p = temperature > 0 and rng.random() < 0.03 and L["alt_payee"] is not None
        amount = L["alt_amount"] if (sys_a or rnd_a) else card.truth_amount
        payee_id = L["alt_payee"] if (sys_p or rnd_p) else card.truth_payee_id
        spoken_amount = amount if (L["asr"] or not (sys_a or rnd_a)) else card.truth_amount  # extraction slip vs mishearing
        spoken_payee = payee_id if (L["asr"] or not (sys_p or rnd_p)) else card.truth_payee_id
        name = self.names[spoken_payee]

        def conf(sys_err: bool, rnd_err: bool) -> float:
            if sys_err:
                return rng.uniform(0.82, 0.97)  # confidently wrong
            if rnd_err:
                return rng.uniform(0.50, 0.85)
            return rng.uniform(0.88, 0.99)

        intent = "other" if rng.random() < 0.01 else "send_money"
        out = ModelOutput(
            transcript_roman=f"{name} ko {spoken_amount} rupaye bhej do", transcript_native=None, intent=intent,
            payee_text=name, amount_text=str(spoken_amount), amount_value=amount, note=card.truth_note or None,
            self_conf=SelfConf(payee=conf(sys_p, rnd_p), amount=conf(sys_a, rnd_a), intent=rng.uniform(0.9, 0.99)),
            speech_detected=True, language_mix="mixed",
        )  # fmt: skip
        return ModelCall(out, tokens_in=0, tokens_out=0)


def run(db_url: str, n: int = 40, seed: int = 7, arms: bool = True, probes: bool = True) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from .app import create_app

    env = {"VANI_DEV": "1", "DATABASE_URL": db_url, "ARMS_ENABLED": "1" if arms else "0",
           "PROBES_ENABLED": "1" if probes else "0", "PROBE_RATE": "0.12",
           "RATE_PER_IP_PER_MIN": "1000000", "RATE_PER_SESSION_PER_MIN": "1000000"}  # fmt: skip
    st = load_settings(env)
    contacts = load_contacts(CONFIG_DIR_CARDS / "contacts.yaml")
    names = {c.payee_id: c.display_name for c in contacts}
    noisy = NoisyClient(seed, names, load_groups(CONFIG_DIR_CARDS / "contacts.yaml"))
    tc = TestClient(create_app(st, noisy))
    cards = {c.card_id: c for c in tc.app.state.cards.values()}  # type: ignore[attr-defined]
    stats = {"participants": 0, "commands": 0}

    for i in range(n):
        rng = random.Random(seed * 1000 + i)
        comfort = rng.choice(["hindi_dominant", "english_dominant", "balanced"])
        noise = rng.choices(["quiet", "some", "noisy"], [5, 3, 2])[0]
        r = tc.post("/api/sessions", json={"consent_version": "v2", "language_comfort": comfort, "noise_self_report": noise,
                                           "device_class": "mobile", "os": rng.choice(["Android", "Android", "iOS"]),
                                           "browser": rng.choice(["Chrome", "Chrome", "Safari", "Samsung"])}).json()  # fmt: skip
        sid = r["session_id"]
        noisy.noise_boost = {"quiet": 0.0, "some": 0.03, "noisy": 0.08}[noise]
        quits_after = rng.randint(1, 8) if rng.random() < 0.06 else None
        for sc in ("mic", "task"):
            tc.post("/api/events", json={"session_id": sid, "type": "screen_view", "payload": {"screen": sc}})
        done_cards, trust = 0, 4.0
        while True:
            nc = tc.get(f"/api/sessions/{sid}/next-card").json()
            if nc["done"]:
                break
            card = cards[nc["card"]["card_id"]]
            noisy.current = card
            retries = 0
            while True:
                name = names[card.truth_payee_id]
                req = {"session_id": sid, "card_id": card.card_id, "client_request_id": f"{i}-{card.card_id}-{retries}",
                       "dev_transcript": f"{name} ko {card.truth_amount} rupaye bhej do"}  # fmt: skip
                res = tc.post("/api/commands", data=req).json()
                stats["commands"] += 1
                mode, fields = res["mode"], res["fields"]
                t_mic, t_res = int(rng.lognormvariate(7.8, 0.3)), int(rng.lognormvariate(8.2, 0.4))
                act: dict[str, Any]
                if mode == "retry":
                    if retries < 2 and rng.random() < 0.6:
                        act = {"action": "retry", "taps_count": 1}
                        retries += 1
                    else:
                        act = {"action": "manual", "final_payee_id": card.truth_payee_id, "final_amount": card.truth_amount, "taps_count": 4}
                elif mode == "fast":
                    shown_ok = (fields["payee"]["id"], fields["amount"]) == (card.truth_payee_id, card.truth_amount)
                    blind = rng.random() < 0.30 if not shown_ok else True  # invented blind-confirmation rate
                    act = ({"action": "pay", "taps_count": 1} if blind
                           else {"action": "edit", "final_payee_id": card.truth_payee_id, "final_amount": card.truth_amount, "taps_count": 4})  # fmt: skip
                elif mode == "confirm_all":
                    shown_ok = (fields["payee"]["id"], fields["amount"]) == (card.truth_payee_id, card.truth_amount)
                    if shown_ok or rng.random() < 0.25:
                        act = {"action": "pay", "taps_count": 3}
                    else:
                        act = {"action": "edit", "final_payee_id": card.truth_payee_id, "final_amount": card.truth_amount, "taps_count": 5}
                    t_res = int(t_res * 1.5)
                else:  # verify
                    opts = res["chips"]["options"]
                    want = card.truth_amount if res["chips"]["field"] == "amount" else card.truth_payee_id
                    hit = next((o for o in opts if o["value"] == want), None)
                    if hit and rng.random() < 0.9:
                        act = {"action": "pay", "chip_field": res["chips"]["field"], "chip_value": hit["value"], "taps_count": 2}
                    else:
                        act = {"action": "edit", "final_payee_id": card.truth_payee_id,
                               "final_amount": card.truth_amount, "taps_count": 4}  # fmt: skip
                    t_res = int(t_res * 1.2)
                act |= {"time_to_mic_ms": t_mic, "time_result_to_action_ms": t_res, "time_to_complete_ms": t_mic + t_res + 3000}
                tc.post(f"/api/commands/{res['cmd_id']}/action", json=act)
                if act["action"] != "retry":
                    break
            done_cards += 1
            if quits_after and done_cards >= quits_after:
                break
        stats["participants"] += 1
        if quits_after and done_cards >= quits_after:
            continue
        for sc in ("processing", "result", "success", "survey", "end"):
            tc.post("/api/events", json={"session_id": sid, "type": "screen_view", "payload": {"screen": sc}})
        tc.post(f"/api/sessions/{sid}/survey", json={"trust_amount": max(1, min(5, round(rng.gauss(trust, 0.8)))),
                                                     "low_effort": max(1, min(5, round(rng.gauss(4.1, 0.8)))),
                                                     "would_use": max(1, min(5, round(rng.gauss(3.6, 1.0))))})  # fmt: skip
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--db", default="sqlite:///data/synthetic.db")
    a = ap.parse_args()
    if a.db.startswith("sqlite:///"):
        Path(a.db.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        Path(a.db.removeprefix("sqlite:///")).unlink(missing_ok=True)
    print("SYNTHETIC DATA. Not results.", run(a.db, a.n, a.seed))
