"""Poke the domain layer by hand. No model, no network, no database.

    python -m vani.demo "Priya ko dedh sau rupaye bhej do"
    python -m vani.demo "Amit ko pandrah rupaye bhej do" --amount-value 50
    python -m vani.demo "Rahul ko pachaas rupaye bhej do"

It plays the part of the model (you pick the confidences) and runs the real
parse -> validate -> combine -> route chain from vani/domain.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_settings
from .domain.confidence import FieldFeatures
from .domain.numbers import confusable_partner, parse_amounts
from .domain.payee import Contact, rank_payees
from .domain.router import FieldInput, RouterInput, route
from .domain.validators import validate

CONFIG = Path(__file__).resolve().parents[3] / "config" / "router.yaml"

SAMPLE_CONTACTS = [
    Contact("rahul_sharma", "Rahul Sharma", ("Rahul S",), "राहुल शर्मा"),
    Contact("rahul_sethi", "Rahul Sethi", ("Rahul Seth",), "राहुल सेठी"),
    Contact("rohit_sharma", "Rohit Sharma", (), "रोहित शर्मा"),
    Contact("priya", "Priya", (), "प्रिया"),
    Contact("pooja", "Pooja", ("Puja",), "पूजा"),
    Contact("amit", "Amit", (), "अमित"),
    Contact("ankit", "Ankit", (), "अंकित"),
    Contact("sumit", "Sumit", (), "सुमित"),
    Contact("sunit", "Sunit", (), "सुनित"),
    Contact("ravi", "Ravi", (), "रवि"),
    Contact("ravi_kumar", "Ravi Kumar", (), "रवि कुमार"),
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("text", help="the Hinglish transcript, e.g. 'Priya ko dedh sau rupaye bhej do'")
    ap.add_argument("--payee", help="payee text the 'model' extracted (default: words before ' ko ')")
    ap.add_argument("--amount-value", type=int, help="amount the 'model' returned (default: best parse)")
    ap.add_argument("--self-conf", type=float, default=0.9, help="model's verbalised confidence")
    ap.add_argument("--agreement", type=float, default=1.0, help="sample agreement, payee and intent")
    ap.add_argument("--amount-agreement", type=float, help="sample agreement for the amount only")
    ap.add_argument("--intent", default="send_money")
    ap.add_argument("--ceiling", type=int, default=5000, help="scenario-card amount ceiling")
    a = ap.parse_args(argv)

    cfg = load_settings(CONFIG)
    payee_text = a.payee if a.payee is not None else (
        a.text.split(" ko ")[0] if " ko " in a.text else ""
    )
    cands = parse_amounts(a.text, ignore=payee_text)
    amount = a.amount_value if a.amount_value is not None else (cands[0].value if cands else None)
    match = rank_payees(payee_text, SAMPLE_CONTACTS, delta=cfg.payee_ambiguity_delta)
    v = validate(
        transcript=a.text, amount_text=a.text, amount_value=amount, intent=a.intent,
        speech_detected=True, payee_text=payee_text, payee_match=match, ceiling=a.ceiling,
        confusable_penalty=cfg.confusable_penalty,
    )  # fmt: skip

    amt_agree = a.amount_agreement if a.amount_agreement is not None else a.agreement
    conf = {
        "payee": cfg.combiner.combine("payee", FieldFeatures(a.self_conf, a.agreement, v.payee_score)),
        "amount": cfg.combiner.combine("amount", FieldFeatures(a.self_conf, amt_agree, v.amount_score)),
        "intent": cfg.combiner.combine("intent", FieldFeatures(a.self_conf, a.agreement, v.intent_score)),
    }  # fmt: skip

    top = match.candidates[0].score if match.candidates else 0.0
    payee_chips = tuple(c.display_name for c in match.candidates if c.score >= top - 0.25)
    partner = confusable_partner(amount) if amount is not None else None
    amount_chips = tuple(
        dict.fromkeys(f"₹{x}" for x in (amount, *(c.value for c in cands if c.confidence >= 0.5), partner) if x)
    )
    decision = route(
        RouterInput(
            FieldInput(conf["payee"], payee_chips),
            FieldInput(conf["amount"], amount_chips),
            FieldInput(conf["intent"]),
            v.flags,
        ),
        cfg.router,
    )

    print(f"transcript      : {a.text}")
    print(f"amount parses   : {[(c.value, c.confidence) for c in cands] or 'none'}")
    print(f"model amount    : {amount}")
    print("payee ranking   : " + (", ".join(f"{c.display_name} {c.score:.2f}" for c in match.candidates) or "none"))
    print(f"payee margin    : {match.margin:.2f}  ambiguous={match.ambiguous}")
    print(f"validator flags : {sorted(v.flags) or 'none'}")
    print("combined conf   : " + "  ".join(f"{k}={x:.3f} (need {cfg.router.thresholds[k]:.2f})" for k, x in conf.items()))
    print(f"ROUTE           : Tier {decision.tier.value}   reasons={list(decision.reasons)}")
    if decision.chips:
        print(f"chips           : {list(decision.chips)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
