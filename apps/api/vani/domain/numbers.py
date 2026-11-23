"""Spoken Hindi / Hinglish / English amount parsing.

Pure functions, no I/O. Fail-safe by design: anything that cannot be parsed
cleanly yields no candidate instead of a guess, so the router sees "no amount".

Known ambiguity handled here: "bhej do" / "de do" / "kar do" use "do" as a verb
(give), not the number 2. Candidates carry a confidence so callers can tell.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from fractions import Fraction

# ---------------------------------------------------------------- vocabulary

# Canonical Roman spellings for 1..99. Spelling variants are absorbed by _norm()
# below. NOTE: starter table; have a Hindi speaker review it and extend it from
# real pilot transcripts (see docs/ASSUMPTIONS.md).
_HI_1_99 = (
    "ek do teen char paanch chhe saat aath nau das "
    "gyarah barah terah chaudah pandrah solah satrah atharah unnis bees "
    "ikkis baais teis chaubis pachchis chhabbis sattais atthais unatis tees "
    "ikatis battis tentis chauntis paintis chhattis saintis adtis untalis chalis "
    "iktalis bayalis taitalis chauvalis paintalis chhiyalis saitalis adtalis unchas pachaas "
    "ikyavan baavan tirpan chauvan pachpan chhappan sattavan atthavan unsath saath "
    "iksath baasath tirsath chausath painsath chhiyasath sadsath adsath unhattar sattar "
    "ikhattar bahattar tihattar chauhattar pachattar chhihattar satattar athattar unnasi assi "
    "ikyasi bayasi tirasi chaurasi pachasi chhiyasi sattasi atthasi nauasi nabbe "
    "ikyanve baanve tiranve chauranve pachanve chhiyanve sattanve atthanve ninyanve"
).split()
assert len(_HI_1_99) == 99

_EN_UNITS = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_EN_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}  # fmt: skip

# kind: N number, S scale, F fractional number (dedh/dhai/sawa), P offset
# (saade +0.5 / paune -0.25), C currency word, V send-verb word.
_Entry = tuple[str, Fraction]
_EXACT: dict[str, _Entry] = {}
for _i, _w in enumerate(_EN_UNITS):
    _EXACT[_w] = ("N", Fraction(_i))
for _w, _v in _EN_TENS.items():
    _EXACT[_w] = ("N", Fraction(_v))
for _i, _w in enumerate(_HI_1_99, start=1):
    _EXACT[_w] = ("N", Fraction(_i))
_EXACT.update({"tin": ("N", Fraction(3)), "panch": ("N", Fraction(5)), "chhah": ("N", Fraction(6))})
for _w in ("sau", "hundred"):
    _EXACT[_w] = ("S", Fraction(100))
for _w in ("hazaar", "hazar", "hajar", "thousand"):
    _EXACT[_w] = ("S", Fraction(1000))
for _w in ("lakh", "lakhs", "lac", "lacs"):
    _EXACT[_w] = ("S", Fraction(100000))
for _w in ("dedh", "derh", "der"):
    _EXACT[_w] = ("F", Fraction(3, 2))
for _w in ("dhai", "dhaai", "adhai"):
    _EXACT[_w] = ("F", Fraction(5, 2))
for _w in ("sawa", "sava"):
    _EXACT[_w] = ("F", Fraction(5, 4))
for _w in ("saade", "sade", "saadhe"):
    _EXACT[_w] = ("P", Fraction(1, 2))
for _w in ("paune", "pone"):
    _EXACT[_w] = ("P", Fraction(-1, 4))
for _w in ("rupaye", "rupaiye", "rupees", "rupee", "rupya", "rupiya", "rupay", "rupe", "rs", "inr"):
    _EXACT[_w] = ("C", Fraction(0))
for _w in (
    "bhej", "bhejo", "bhejna", "bhejdo", "bhejiye", "de", "dena", "dedo",
    "kar", "karo", "kardo", "karna", "send", "pay", "transfer", "daal", "dalo",
):  # fmt: skip
    _EXACT[_w] = ("V", Fraction(0))


def _collapse(tok: str) -> str:
    return re.sub(r"(.)\1+", r"\1", tok.replace("w", "v"))


def _build_norm() -> dict[str, _Entry]:
    """Normalised fallback index (spelling variants). Collisions are dropped."""
    seen: dict[str, set[_Entry]] = {}
    for word, entry in _EXACT.items():
        if entry[0] in ("C", "V"):
            continue
        if word in _EN_UNITS or word in _EN_TENS or word in ("hundred", "thousand"):
            continue
        seen.setdefault(_collapse(word), set()).add(entry)
    out: dict[str, _Entry] = {}
    for key, entries in seen.items():
        if len(entries) != 1 or key in _EXACT:
            continue  # ambiguous or shadowed by an exact word (e.g. "ten" vs "teen")
        out[key] = next(iter(entries))
    return out


_NORM = _build_norm()

# ------------------------------------------------------------------ Devanagari


def _dev_clean(text: str) -> str:
    t = unicodedata.normalize("NFD", text)
    t = t.replace("\u093c", "").replace("\u0901", "\u0902")  # drop nukta, chandrabindu -> anusvara
    return unicodedata.normalize("NFC", t)


_DEV_WORDS = {
    "एक": "ek", "दो": "do", "तीन": "teen", "चार": "char", "पांच": "paanch", "पाँच": "paanch",
    "छह": "chhe", "सात": "saat", "आठ": "aath", "नौ": "nau", "दस": "das",
    "ग्यारह": "gyarah", "बारह": "barah", "तेरह": "terah", "चौदह": "chaudah",
    "पंद्रह": "pandrah", "पन्द्रह": "pandrah", "सोलह": "solah", "सत्रह": "satrah",
    "अठारह": "atharah", "उन्नीस": "unnis", "बीस": "bees", "तीस": "tees", "चालीस": "chalis",
    "पचास": "pachaas", "साठ": "saath", "सत्तर": "sattar", "अस्सी": "assi", "नब्बे": "nabbe",
    "सौ": "sau", "हज़ार": "hazaar", "हजार": "hazaar", "लाख": "lakh",
    "डेढ़": "dedh", "ढाई": "dhai", "सवा": "sawa", "साढ़े": "saade", "पौने": "paune",
    "रुपये": "rupaye", "रुपए": "rupaye", "रुपया": "rupaye", "रुपयों": "rupaye",
    "भेज": "bhej", "भेजो": "bhejo", "भेजना": "bhejna", "दे": "de", "देना": "dena", "कर": "kar",
    "करो": "karo",
}  # fmt: skip
_DEV = {_dev_clean(k): v for k, v in _DEV_WORDS.items()}
_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# ------------------------------------------------------------------- tokenizer


@dataclass(frozen=True)
class _Tok:
    kind: str  # N S F P C V D (digits) X (other) A ("and")
    val: Fraction
    raw: str


def _raw_tokens(text: str) -> list[str]:
    t = _dev_clean(text).lower().replace("₹", " rs ").translate(_DEV_DIGITS)
    t = re.sub(r"(?<=\d),(?=\d)", "", t)
    return re.findall(r"\d+(?:\.\d+)?|[a-z]+|[\u0900-\u097f]+", t)


def _lookup(raw: str) -> _Tok:
    if raw.isdigit():
        return _Tok("D", Fraction(int(raw)), raw) if len(raw) <= 9 else _Tok("X", Fraction(0), raw)
    if raw in _DEV:
        raw = _DEV[raw]
    if raw == "and":
        return _Tok("A", Fraction(0), raw)
    entry = _EXACT.get(raw) or _NORM.get(_collapse(raw))
    return _Tok(entry[0], entry[1], raw) if entry else _Tok("X", Fraction(0), raw)


def _type_tokens(text: str, ignore: set[str]) -> list[_Tok]:
    return [
        _Tok("X", Fraction(0), r) if r in ignore else _lookup(r) for r in _raw_tokens(text)
    ]


# --------------------------------------------------------------------- grammar

_NUMERIC = ("N", "D", "F", "P", "S")


def _eval_run(run: list[_Tok]) -> int | None:
    """Evaluate one run of numeric tokens in the Indian system. None = invalid."""
    total = Fraction(0)
    cur = Fraction(0)
    pending = Fraction(0)
    last_scale = Fraction(10**12)
    for tok in run:
        if tok.kind in ("N", "D"):
            cur += tok.val + pending
            pending = Fraction(0)
        elif tok.kind == "F":
            if cur != 0 or pending != 0:
                return None
            cur = tok.val
        elif tok.kind == "P":
            if pending != 0:
                return None
            pending = tok.val
        elif tok.kind == "S":
            if pending != 0 or tok.val >= last_scale and tok.val != 100:
                return None
            if tok.val == 100:
                if cur >= 100:
                    return None
                cur = (cur or Fraction(1)) * 100
            else:
                if cur >= 1000:
                    return None
                total += (cur or Fraction(1)) * tok.val
                cur = Fraction(0)
                last_scale = tok.val
    if pending != 0:
        return None
    result = total + cur
    if result.denominator != 1 or result <= 0:
        return None
    return int(result)


@dataclass(frozen=True)
class ParsedAmount:
    value: int
    confidence: float
    currency_adjacent: bool
    text: str


def _runs(toks: list[_Tok]) -> list[tuple[int, int]]:
    """Maximal [start, end) spans of tokens that can belong to one number."""
    spans: list[tuple[int, int]] = []
    i, n = 0, len(toks)
    while i < n:
        if toks[i].kind not in _NUMERIC:
            i += 1
            continue
        start, j = i, i + 1
        while j < n:
            prev, t = toks[j - 1], toks[j]
            if t.kind == "A" and prev.kind == "S" and j + 1 < n and toks[j + 1].kind == "N":
                j += 1  # "two hundred and fifty"
                continue
            if t.kind not in _NUMERIC:
                break
            if t.kind in ("N", "D") and prev.kind in ("N", "D"):
                tens_then_unit = (
                    prev.kind == "N" and prev.val >= 20 and prev.val % 10 == 0 and 1 <= t.val <= 9
                )
                if not tens_then_unit:
                    break
            if t.kind in ("F", "P") and prev.kind != "S":
                break
            j += 1
        spans.append((start, j))
        i = j
    return spans


def parse_amounts(text: str, ignore: str = "") -> list[ParsedAmount]:
    """All plausible amounts in `text`, best first.

    `ignore` is text (e.g. the payee name) whose tokens must not be read as
    numbers; "Rahul Das ko ..." must not yield 10 from "Das".
    """
    ignore_set = set(_raw_tokens(ignore))
    toks = _type_tokens(text, ignore_set)
    best: dict[int, ParsedAmount] = {}
    for start, end in _runs(toks):
        run = [t for t in toks[start:end] if t.kind != "A"]
        value = _eval_run(run)
        if value is None:
            continue
        before = toks[start - 1].kind if start > 0 else ""
        after = toks[end].kind if end < len(toks) else ""
        currency = before == "C" or after == "C"
        conf = 0.85 if all(t.kind == "D" for t in run) else 0.8
        if currency:
            conf = 0.95
        if len(run) == 1 and run[0].raw == "do":
            if before == "V":
                conf = 0.15  # "bhej do": a verb, not the number two
            elif not currency:
                conf = min(conf, 0.3)
        cand = ParsedAmount(value, conf, currency, " ".join(t.raw for t in run))
        if value not in best or best[value].confidence < conf:
            best[value] = cand
    return sorted(best.values(), key=lambda c: (-c.confidence, c.value))


def parse_amount(text: str, ignore: str = "") -> int | None:
    """Best single amount, or None. Callers needing ambiguity use parse_amounts."""
    cands = parse_amounts(text, ignore)
    return cands[0].value if cands else None


# ------------------------------------------------------------------ confusables

CONFUSABLE_PAIRS: dict[int, int] = {13: 30, 14: 40, 15: 50, 16: 60, 17: 70, 18: 80, 19: 90}
_PARTNER: dict[int, int] = {**CONFUSABLE_PAIRS, **{v: k for k, v in CONFUSABLE_PAIRS.items()}}


def confusable_partner(amount: int) -> int | None:
    """Amount that noisy audio could swap this one with (terah/tees, pandrah/pachaas...).

    Rule (narrow on purpose): bare amounts under 100 swap with their pair
    (15 <-> 50); whole hundreds or thousands swap the leading number (1500 <-> 5000,
    15000 <-> 50000). Amounts like 150 or 250 are NOT flagged: "dedh sau" and
    "dhai sau" are distinct words. Widen only if pilot data (H4) says to.
    """
    if amount < 100:
        return _PARTNER.get(amount)
    for unit in (100, 1000):
        if amount % unit == 0 and (amount // unit) in _PARTNER:
            return _PARTNER[amount // unit] * unit
    return None


def is_confusable(amount: int) -> bool:
    return confusable_partner(amount) is not None
