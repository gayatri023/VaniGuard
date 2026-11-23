import pytest

from vani.demo import main


def test_demo_clean_command_is_tier_a(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["Priya ko dedh sau rupaye bhej do"]) == 0
    assert "Tier A" in capsys.readouterr().out


def test_demo_model_misread_is_tier_c(capsys: pytest.CaptureFixture[str]) -> None:
    main(["Amit ko pandrah rupaye bhej do", "--amount-value", "50"])
    out = capsys.readouterr().out
    assert "Tier C" in out and "amount_mismatch_transcript" in out


def test_demo_amount_chips_exclude_the_verb_do(capsys: pytest.CaptureFixture[str]) -> None:
    main(["Amit ko pandrah rupaye bhej do", "--amount-agreement", "0.67"])
    out = capsys.readouterr().out
    assert "Tier B" in out and "\u20b915" in out and "\u20b950" in out and "\u20b92'" not in out
