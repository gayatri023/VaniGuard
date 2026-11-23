"""Run REAL recorded clips through the REAL pipeline and the live Gemini API, then print what you need to
trust it: accuracy, tier mix, wrong fast-path commands, latency p50/p95 by stage, cost per command.

    1. Record 10 to 30 clips (consented speakers; include hard cases and a couple of prompt-injection clips).
    2. Put them in a folder with a truth.csv:   file,payee_id,amount
         priya_150.m4a,priya,150
         amit_15_noisy.m4a,amit,15
       (payee_id must exist in config/cards/contacts.yaml; the amount is what the speaker MEANT.)
    3. python -m vani.livecheck clips/            (needs the live env vars: key, model, caps, pricing)
Audio is processed in memory and temp files only, exactly like production; nothing is stored.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .cards import CONFIG_DIR_CARDS, load_contacts
from .pipeline.audio import AudioError, to_wav16k
from .pipeline.clients import ModelClient, ModelInput
from .pipeline.run import run_pipeline
from .settings import Settings, load_settings


@dataclass
class Clip:
    path: Path
    payee_id: str
    amount: int


def load_truth(folder: Path) -> list[Clip]:
    rows = list(csv.DictReader((folder / "truth.csv").read_text(encoding="utf-8").splitlines()))
    clips = [Clip(folder / r["file"].strip(), r["payee_id"].strip(), int(r["amount"])) for r in rows]
    missing = [c.path.name for c in clips if not c.path.exists()]
    if missing:
        raise SystemExit(f"files listed in truth.csv but not found: {missing}")
    return clips


async def run_livecheck(
    clips: list[Clip], st: Settings, client: ModelClient, ceiling_factor: int = 10,
    on_clip: Callable[[Clip], None] | None = None,
) -> dict[str, Any]:  # fmt: skip
    contacts = load_contacts(CONFIG_DIR_CARDS / "contacts.yaml")
    ids = {c.payee_id for c in contacts}
    rows: list[dict[str, Any]] = []
    for clip in clips:
        if clip.payee_id not in ids:
            raise SystemExit(f"{clip.path.name}: unknown payee_id '{clip.payee_id}'")
        t0 = time.perf_counter()
        try:
            wav = await to_wav16k(clip.path.read_bytes())
        except AudioError as e:
            rows.append({"file": clip.path.name, "tier": "C", "ok": False, "fast_wrong": False, "error": e.code, "total_ms": 0, "stages": {}, "cost": 0.0})
            continue
        if on_clip:
            on_clip(clip)
        res = await run_pipeline(client, ModelInput(wav=wav), contacts, max(500, clip.amount * ceiling_factor), st)
        ok = res.payee_id == clip.payee_id and res.amount == clip.amount
        rows.append({"file": clip.path.name, "truth": f"{clip.payee_id}/{clip.amount}", "parsed": f"{res.payee_id}/{res.amount}", "tier": res.tier, "ok": ok,
                     "fast_wrong": res.tier == "A" and not ok, "error": res.error_code or "", "flags": res.flags, "total_ms": int((time.perf_counter() - t0) * 1000),
                     "stages": res.stage_ms, "cost": res.cost_usd, "tokens": res.tokens_in + res.tokens_out})  # fmt: skip
    n = len(rows)
    tot = [r["total_ms"] for r in rows if r["total_ms"]]
    stage_names = sorted({k for r in rows for k in r["stages"]})
    return {
        "n": n, "accuracy": sum(r["ok"] for r in rows) / n if n else float("nan"),
        "tiers": {t: sum(1 for r in rows if r["tier"] == t) for t in "ABC"},
        "fast_wrong": sum(r["fast_wrong"] for r in rows),
        "latency_ms": {"total": {"p50": float(np.percentile(tot, 50)), "p95": float(np.percentile(tot, 95))} if tot else {},
                       **{s: {"p50": float(np.percentile([r["stages"][s] for r in rows if s in r["stages"]], 50)),
                              "p95": float(np.percentile([r["stages"][s] for r in rows if s in r["stages"]], 95))} for s in stage_names}},
        "cost_usd_per_command": float(np.mean([r["cost"] for r in rows])) if rows else 0.0,
        "rows": rows,
    }  # fmt: skip


def print_report(rep: dict[str, Any]) -> None:
    print(f"\n{'file':<28}{'truth':<18}{'parsed':<18}{'tier':<5}{'ok':<6}{'ms':>6}  flags / error")
    for r in rep["rows"]:
        print(f"{r['file']:<28}{r.get('truth', ''):<18}{r.get('parsed', ''):<18}{r['tier']:<5}{('yes' if r['ok'] else 'NO'):<6}{r['total_ms']:>6}  {','.join(r.get('flags', [])) or r['error']}")
    lat = rep["latency_ms"]
    print(f"\nn={rep['n']}  accuracy (payee+amount) {rep['accuracy']:.1%}  tiers {rep['tiers']}  WRONG FAST-PATH: {rep['fast_wrong']}")
    print("latency ms  " + "  ".join(f"{k}: p50 {v['p50']:.0f} / p95 {v['p95']:.0f}" for k, v in lat.items() if v))
    p95 = lat.get("total", {}).get("p95")
    if p95 and p95 > 5000:
        print(f"WARNING: p95 {p95:.0f} ms exceeds the 5000 ms budget")
    print(f"cost per command: ${rep['cost_usd_per_command']:.5f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path)
    a = ap.parse_args()
    st = load_settings()
    if st.backend != "gemini":
        raise SystemExit("livecheck needs the live model: unset VANI_DEV and set GEMINI_API_KEY, GEMINI_MODEL, caps and config/pricing.yaml")
    from .app import build_client

    print_report(asyncio.run(run_livecheck(load_truth(a.folder), st, build_client(st))))


if __name__ == "__main__":
    main()
