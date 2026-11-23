import pytest

from vani.domain.numbers import (
    _EXACT,
    _NORM,
    CONFUSABLE_PAIRS,
    confusable_partner,
    is_confusable,
    parse_amount,
    parse_amounts,
)

REQUIRED = [
    ("pachaas", 50), ("sau", 100), ("dedh sau", 150), ("dhai sau", 250), ("sawa sau", 125),
    ("paune do sau", 175), ("saade teen sau", 350), ("paanch sau", 500), ("ek hazaar", 1000),
    ("dedh hazaar", 1500), ("dhai hazaar", 2500), ("do hazaar paanch sau", 2500),
    ("fifty", 50), ("two hundred fifty", 250), ("50 rupaye", 50),
]  # fmt: skip

EXTRA = [
    ("das", 10), ("pandrah", 15), ("terah", 13), ("tees", 30), ("chalis", 40), ("saath", 60),
    ("sattar", 70), ("assi", 80), ("nabbe", 90), ("ninyanve", 99), ("ek sau pachaas", 150),
    ("do sau", 200), ("teen sau", 300), ("do sau pachaas", 250), ("paanch hazaar", 5000),
    ("pachaas hazaar", 50000), ("ek lakh", 100000), ("dedh lakh", 150000),
    ("ek lakh pachaas hazaar", 150000), ("saade paanch sau", 550), ("paune teen sau", 275),
    ("sawa hazaar", 1250), ("saade teen hazaar", 3500), ("two hundred and fifty", 250),
    ("twenty five", 25), ("ninety nine", 99), ("one thousand five hundred", 1500),
    ("fifteen", 15), ("15", 15), ("1,500", 1500), ("1,50,000", 150000), ("₹250", 250),
    ("rs 75", 75), ("100 rupees", 100), ("2 hazaar", 2000), ("do hazaar", 2000),
    # spelling variants absorbed by normalisation
    ("panch sau", 500), ("pachas", 50), ("paachas", 50), ("hazar", 1000), ("dedh sau rupaye", 150),
    # Devanagari
    ("पचास", 50), ("सौ", 100), ("डेढ़ सौ", 150), ("ढाई सौ", 250), ("सवा सौ", 125),
    ("पौने दो सौ", 175), ("साढ़े तीन सौ", 350), ("पांच सौ", 500), ("पाँच सौ", 500),
    ("एक हज़ार", 1000), ("डेढ़ हजार", 1500), ("५०", 50), ("पचास रुपये", 50),
]  # fmt: skip


@pytest.mark.parametrize("text,expected", REQUIRED + EXTRA)
def test_parse_amount(text: str, expected: int) -> None:
    assert parse_amount(text) == expected


@pytest.mark.parametrize("text", ["", "hello", "dedh", "saade teen", "sau sau", "paune"])
def test_unparseable_gives_nothing(text: str) -> None:
    assert parse_amount(text) is None


def test_bhej_do_is_a_verb_not_two() -> None:
    cands = parse_amounts("Rahul ko pachaas rupaye bhej do")
    assert cands[0].value == 50 and cands[0].confidence > 0.9
    two = [c for c in cands if c.value == 2]
    assert two and two[0].confidence < 0.2


def test_devanagari_bhej_do() -> None:
    cands = parse_amounts("राहुल को पचास रुपये भेज दो")
    assert cands[0].value == 50


def test_lone_do_without_currency_is_low_confidence() -> None:
    assert parse_amounts("Rahul ko do")[0].confidence <= 0.3


def test_payee_tokens_can_be_ignored() -> None:
    # "Das" is a surname and also the number 10
    assert {c.value for c in parse_amounts("Rahul Das ko pachaas bhej do")} >= {10, 50}
    assert parse_amount("Rahul Das ko pachaas bhej do", ignore="Rahul Das") == 50


def test_english_ten_is_not_hindi_teen() -> None:
    assert parse_amount("ten") == 10
    assert parse_amount("teen") == 3


def test_normalised_index_has_no_collisions_with_exact_words() -> None:
    assert not (set(_NORM) & set(_EXACT))


def test_hindi_table_is_unique() -> None:
    from vani.domain.numbers import _HI_1_99

    assert len(set(_HI_1_99)) == 99


@pytest.mark.parametrize("small,big", sorted(CONFUSABLE_PAIRS.items()))
def test_confusable_pairs_are_symmetric(small: int, big: int) -> None:
    assert confusable_partner(small) == big
    assert confusable_partner(big) == small
    assert is_confusable(small) and is_confusable(big)


@pytest.mark.parametrize(
    "amount,partner",
    [(15, 50), (50, 15), (1500, 5000), (15000, 50000), (115, None), (150, None), (250, None), (12, None), (100, None)],
)
def test_confusable_partner_rules(amount: int, partner: int | None) -> None:
    assert confusable_partner(amount) == partner


def test_adjacent_small_numbers_are_not_merged() -> None:
    values = {c.value for c in parse_amounts("ek do")}
    assert values == {1, 2} and 3 not in values
