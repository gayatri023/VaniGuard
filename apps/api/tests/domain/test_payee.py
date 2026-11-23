from vani.domain.payee import Contact, normalize_name, rank_payees

CONTACTS = [
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


def top(q: str) -> str:
    return rank_payees(q, CONTACTS).candidates[0].payee_id


def test_exact_full_name() -> None:
    m = rank_payees("Rahul Sharma", CONTACTS)
    assert m.candidates[0].payee_id == "rahul_sharma"
    assert m.exact_alias_hit and not m.ambiguous


def test_bare_first_name_is_ambiguous_between_rahuls() -> None:
    m = rank_payees("Rahul", CONTACTS)
    assert m.ambiguous and m.margin < 0.10
    assert {c.payee_id for c in m.candidates[:2]} == {"rahul_sharma", "rahul_sethi"}


def test_confusable_sets_resolve() -> None:
    assert top("Rohit Sharma") == "rohit_sharma"
    assert top("Rahul Sethi") == "rahul_sethi"
    assert top("Amit") == "amit" and top("Ankit") == "ankit"
    assert top("Sumit") == "sumit" and top("Sunit") == "sunit"
    assert top("Priya") == "priya" and top("Pooja") == "pooja"


def test_spelling_variants_and_honorifics() -> None:
    assert top("Rahul Sharmaa") == "rahul_sharma"
    assert top("Rahul Sarma ji") == "rahul_sharma"
    assert top("Priya didi") == "priya"
    assert top("Pooja bhabhi") == "pooja"
    assert top("Puja") == "pooja"


def test_ravi_vs_ravi_kumar() -> None:
    m = rank_payees("Ravi", CONTACTS)
    assert m.candidates[0].payee_id == "ravi" and not m.ambiguous
    assert top("Ravi Kumar") == "ravi_kumar"


def test_devanagari_input() -> None:
    assert top("राहुल शर्मा") == "rahul_sharma"
    assert top("रोहित शर्मा") == "rohit_sharma"


def test_empty_and_no_contacts_fail_safe() -> None:
    assert rank_payees("", CONTACTS).ambiguous
    assert rank_payees("Rahul", []).candidates == ()


def test_normalize_name() -> None:
    assert normalize_name("Rahul Bhai") == "rahul"
    assert normalize_name("Sheetal") == normalize_name("Sitaal")
