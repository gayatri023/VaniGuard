import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "analysis"))
pipeline = pytest.importorskip("pipeline")
run_mod = pytest.importorskip("run")

from vani.app import create_app
from vani.export import export_all
from vani.settings import load_settings
from vani.simulate import run as simulate


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):  # type: ignore[no-untyped-def]
    d = tmp_path_factory.mktemp("syn")
    url = f"sqlite:///{d}/s.db"
    simulate(url, n=14, seed=3)
    export_all(url, d / "export")
    return url, d / "export" / "commands_flat.csv"


def test_dashboard_replay_equals_analysis_to_four_decimals(synthetic) -> None:  # type: ignore[no-untyped-def]
    url, csv = synthetic
    st = load_settings({"VANI_DEV": "1", "DATABASE_URL": url})
    api = TestClient(create_app(st)).get("/api/admin/risk-coverage", headers={"X-Admin-Token": "dev-admin-token"}).json()
    df = pipeline.add_scores(pipeline.study_rows(pipeline.load(csv)), pipeline.router_cfg())
    mine = pipeline.curve_table(df)
    assert len(api["curve"]) == len(mine) == 41
    for a, b in zip(api["curve"], mine.to_dict("records"), strict=True):
        assert a["threshold"] == b["threshold"]
        for k in ("n_total", "n_fast", "n_wrong"):
            assert a[k] == b[k]
        for k in ("coverage", "wilson_lo", "wilson_hi", "safe_fast_rate"):
            assert round(a[k], 4) == round(float(b[k]), 4), (a["threshold"], k)
        if a["wrong_rate"] is not None:
            assert round(a["wrong_rate"], 4) == round(float(b["wrong_rate"]), 4)


def test_analysis_is_reproducible_and_flags_synthetic(synthetic, tmp_path) -> None:  # type: ignore[no-untyped-def]
    _, csv = synthetic
    outs = []
    for i in range(2):
        out = tmp_path / f"o{i}"
        run_mod.main(csv, out)
        outs.append({str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob("*")) if p.is_file()})
    assert outs[0] == outs[1] and "results.md" in outs[0] and len(outs[0]) >= 8
    text = (tmp_path / "o0" / "results.md").read_text()
    assert "SYNTHETIC DATA. NOT RESULTS." in text and "PREREG INCOMPLETE" in text
    assert "H1:" in text and "H2:" in text and "H3:" in text and "H4:" in text


def test_folds_never_split_a_participant() -> None:
    groups = np.array([f"p{i // 5}" for i in range(200)])
    f = pipeline.folds_for(groups, 5, seed=0)
    for g in set(groups.tolist()):
        assert len(set(f[groups == g].tolist())) == 1
    assert (f == pipeline.folds_for(groups, 5, seed=0)).all() and len(set(f.tolist())) == 5


def test_probes_and_practice_never_count_toward_accuracy(synthetic) -> None:  # type: ignore[no-untyped-def]
    _, csv = synthetic
    raw = pipeline.load(csv)
    study = pipeline.study_rows(raw)
    assert not study.is_probe.any() and not study.is_practice.any()
    assert len(study) == int(((raw.is_probe == False) & (raw.is_practice == False)).sum())
    assert (raw.is_probe == True).any()


def test_small_data_is_refused(tmp_path) -> None:  # type: ignore[no-untyped-def]
    url = f"sqlite:///{tmp_path}/t.db"
    simulate(url, n=1, seed=1)
    export_all(url, tmp_path / "e")
    with pytest.raises(SystemExit, match="nothing meaningful"):
        run_mod.main(tmp_path / "e" / "commands_flat.csv", tmp_path / "o")
