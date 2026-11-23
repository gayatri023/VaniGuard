"""Payee matching against a contact list. Pure functions, no I/O.

Roman names are normalised for Hinglish spelling variation (aa/a, ee/i, oo/u,
v/w, sh/s, double consonants, honorifics) and compared with rapidfuzz plus a
consonant-skeleton "phonetic" key. Devanagari input is matched against
`devanagari_name`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from rapidfuzz import fuzz

_HONORIFICS = {
    "ji", "bhai", "bhaiya", "bhaiyya", "bhaiyaa", "didi", "sir", "madam", "saab", "sahab",
    "sahib", "uncle", "aunty",
}  # fmt: skip
_DEVANAGARI = re.compile(r"[\u0900-\u097f]")


@dataclass(frozen=True)
class Contact:
    payee_id: str
    display_name: str
    aliases: tuple[str, ...] = ()
    devanagari_name: str | None = None


@dataclass(frozen=True)
class PayeeCandidate:
    payee_id: str
    display_name: str
    score: float  # 0..1


@dataclass(frozen=True)
class PayeeMatch:
    candidates: tuple[PayeeCandidate, ...]  # top 3, best first
    margin: float  # top-1 score minus top-2 score
    exact_alias_hit: bool
    ambiguous: bool
    n_exact: int = field(default=0)


def _dev_clean(s: str) -> str:
    t = unicodedata.normalize("NFD", s).replace("\u093c", "").replace("\u0901", "\u0902")
    return unicodedata.normalize("NFC", t)


_RULES = [
    ("ph", "f"), ("sh", "s"), ("dh", "d"), ("bh", "b"), ("kh", "k"), ("gh", "g"),
    ("jh", "j"), ("th", "t"), ("ck", "k"), ("w", "v"), ("z", "j"), ("q", "k"),
    ("aa", "a"), ("ee", "i"), ("ii", "i"), ("oo", "u"), ("uu", "u"),
]  # fmt: skip


def _roman_norm(token: str) -> str:
    for a, b in _RULES:
        token = token.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", token)


def normalize_name(name: str) -> str:
    s = re.sub(r"[^a-z\u0900-\u097f ]", " ", _dev_clean(name).lower())
    out = []
    for tok in s.split():
        if tok in _HONORIFICS:
            continue
        out.append(tok if _DEVANAGARI.search(tok) else _roman_norm(tok))
    return " ".join(out)


def skeleton(norm: str) -> str:
    """Consonant skeleton: keep the first letter of each token, drop later vowels."""
    return " ".join(t[:1] + re.sub(r"[aeiou]", "", t[1:]) for t in norm.split())


def _blend(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return (0.5 * fuzz.ratio(a, b) + 0.5 * fuzz.token_set_ratio(a, b)) / 100.0


def _variants(c: Contact) -> list[str]:
    raw = [c.display_name, *c.aliases] + ([c.devanagari_name] if c.devanagari_name else [])
    return [v for v in (normalize_name(r) for r in raw) if v]


def rank_payees(
    query: str, contacts: list[Contact], delta: float = 0.10, top_k: int = 3
) -> PayeeMatch:
    q = normalize_name(query)
    if not q or not contacts:
        return PayeeMatch((), 0.0, False, True, 0)
    qs = skeleton(q) if not _DEVANAGARI.search(q) else q
    scored: list[PayeeCandidate] = []
    n_exact = 0
    for c in contacts:
        variants = _variants(c)
        if q in variants:
            n_exact += 1
            scored.append(PayeeCandidate(c.payee_id, c.display_name, 1.0))
            continue
        best = 0.0
        for v in variants:
            if _DEVANAGARI.search(q) != _DEVANAGARI.search(v):
                continue
            vs = skeleton(v) if not _DEVANAGARI.search(v) else v
            best = max(best, 0.7 * _blend(q, v) + 0.3 * _blend(qs, vs))
        scored.append(PayeeCandidate(c.payee_id, c.display_name, round(best, 6)))
    scored.sort(key=lambda c: (-c.score, c.payee_id))
    top = tuple(scored[:top_k])
    margin = top[0].score - (top[1].score if len(top) > 1 else 0.0)
    ambiguous = n_exact > 1 or (n_exact == 0 and margin < delta)
    return PayeeMatch(top, round(margin, 6), n_exact >= 1, ambiguous, n_exact)
