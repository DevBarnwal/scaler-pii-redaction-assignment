"""
PII detectors.

Each `find_*` function takes the full document text and returns a list of
`Span` objects. To add a new PII type: write a `find_<type>(text)` function
following the same signature, add its priority to `PRIORITY`, and register
it in `ALL_DETECTORS`. Nothing else in the pipeline needs to change --
`redactor.py` iterates `ALL_DETECTORS` generically.

Detection strategy per type (see README.md for the full rationale):
  - EMAIL, IP, SSN            : regex, high precision by construction.
  - CREDIT_CARD                : regex + Luhn checksum (cuts false positives
                                  on other 13-19 digit numbers).
  - PHONE                      : regex covering common international /
                                  Indian / US formats.
  - DOB                        : date-pattern regex, but ONLY within a short
                                  window after an explicit "date of birth"
                                  style cue -- generic ticket/order dates are
                                  intentionally left alone (precision).
  - COMPANY, ADDRESS, NAME     : heuristic, context-cue + gazetteer based
                                  (regex has no way to "know" a word is a
                                  name; see README for tradeoffs). If spaCy
                                  and a trained English model are available
                                  in the runtime environment, `find_names`
                                  and `find_companies` transparently upgrade
                                  to NER (see `_spacy_entities`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from . import gazetteer as G


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    text: str
    type: str
    priority: int


# Lower number = resolved first when two detectors claim overlapping text.
PRIORITY = {
    "SSN": 1,
    "CREDIT_CARD": 2,
    "EMAIL": 3,
    "IP": 4,
    "DOB": 5,
    "PHONE": 6,
    "ADDRESS": 7,
    "COMPANY": 8,
    "NAME": 9,
}


def _mk(start: int, end: int, text: str, ptype: str) -> Span:
    return Span(start, end, text, ptype, PRIORITY[ptype])


# --------------------------------------------------------------------------
# Optional spaCy upgrade path (used only if spacy + an English model are
# already installed in the environment; the tool works fully offline
# without them via the gazetteer/regex fallback below).
# --------------------------------------------------------------------------
_NLP = None
_SPACY_TRIED = False


def _get_nlp():
    global _NLP, _SPACY_TRIED
    if _SPACY_TRIED:
        return _NLP
    _SPACY_TRIED = True
    try:
        import spacy
        for model_name in ("en_core_web_sm", "en_core_web_md", "en_core_web_lg"):
            try:
                _NLP = spacy.load(model_name)
                break
            except OSError:
                continue
    except ImportError:
        _NLP = None
    return _NLP


def _spacy_entities(text: str, label: str, ptype: str) -> List[Span]:
    nlp = _get_nlp()
    if nlp is None:
        return []
    spans = []
    for ent in nlp(text).ents:
        if ent.label_ == label:
            spans.append(_mk(ent.start_char, ent.end_char, ent.text, ptype))
    return spans


# --------------------------------------------------------------------------
# EMAIL
# --------------------------------------------------------------------------
EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9](?:[A-Za-z0-9._%+-]*[A-Za-z0-9])?"
    r"@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}\b"
)


def find_emails(text: str) -> List[Span]:
    return [_mk(m.start(), m.end(), m.group(), "EMAIL") for m in EMAIL_RE.finditer(text)]


# --------------------------------------------------------------------------
# IP ADDRESS (IPv4)
# --------------------------------------------------------------------------
IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)


def find_ips(text: str) -> List[Span]:
    return [_mk(m.start(), m.end(), m.group(), "IP") for m in IPV4_RE.finditer(text)]


# --------------------------------------------------------------------------
# SSN (US format only: NNN-NN-NNNN). Kept strict on purpose -- a looser
# "any 9 digits" rule would flag huge numbers of unrelated IDs.
# --------------------------------------------------------------------------
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def find_ssns(text: str) -> List[Span]:
    return [_mk(m.start(), m.end(), m.group(), "SSN") for m in SSN_RE.finditer(text)]


# --------------------------------------------------------------------------
# CREDIT CARD -- candidate digit runs (13-19 digits, optionally grouped
# with spaces/dashes) validated with the Luhn checksum so we don't flag
# arbitrary long numeric IDs.
# --------------------------------------------------------------------------
CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def find_credit_cards(text: str) -> List[Span]:
    spans = []
    for m in CREDIT_CARD_RE.finditer(text):
        raw = m.group()
        digits = re.sub(r"[ -]", "", raw)
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            spans.append(_mk(m.start(), m.end(), raw, "CREDIT_CARD"))
    return spans


# --------------------------------------------------------------------------
# PHONE -- ordered most-specific-first so the regex engine's alternation
# prefers the fuller match at a given position. `\+\s?` (not just `\+`)
# because the real reference document routinely writes country codes as
# "+ 91 ..." with a space after the plus sign -- a plain `\+\d` missed
# these entirely, which a stratified check against real document text
# caught (a phone number was silently passing through unredacted).
# --------------------------------------------------------------------------
PHONE_RE = re.compile(
    r"(?:\+\s?\d{1,3}[-.\s]?\d{2,5}[-.\s]?\d{2,4}[-.\s]?\d{2,4})"  # +91 20 4505 3237 / +91 98765 43210
    r"|(?:\+\s?\d{1,3}[-.\s]?\d{10})"                       # +919876543210
    r"|(?:\(\d{2,4}\)[-.\s]?\d{3,4}[-.\s]?\d{3,4})"         # (022) 4567 8901
    r"|(?:\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b)"                 # 123-456-7890
    r"|(?:\b[6-9]\d{9}\b)"                                  # bare Indian mobile
)


def find_phones(text: str) -> List[Span]:
    spans = []
    for m in PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 7 <= len(digits) <= 15:
            spans.append(_mk(m.start(), m.end(), m.group(), "PHONE"))
    return spans


# --------------------------------------------------------------------------
# DATE OF BIRTH -- date-shaped text found close after an explicit DOB cue.
# --------------------------------------------------------------------------
_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_RE = re.compile(
    rf"\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}"
    rf"|\d{{4}}-\d{{1,2}}-\d{{1,2}}"
    rf"|{_MONTH}\.?\s+\d{{1,2}},?\s+\d{{4}}"
    rf"|\d{{1,2}}\s+{_MONTH}\.?,?\s+\d{{4}}",
    re.IGNORECASE,
)


def find_dobs(text: str) -> List[Span]:
    spans = []
    lower = text.lower()
    for cue in G.DOB_CONTEXT_CUES:
        start = 0
        while True:
            idx = lower.find(cue, start)
            if idx == -1:
                break
            window_start = idx + len(cue)
            window_end = min(len(text), window_start + 40)
            dm = DATE_RE.search(text[window_start:window_end])
            if dm:
                abs_start = window_start + dm.start()
                abs_end = window_start + dm.end()
                spans.append(_mk(abs_start, abs_end, text[abs_start:abs_end], "DOB"))
            start = idx + len(cue)
    return spans


# --------------------------------------------------------------------------
# COMPANY -- suffix-based ("Acme Technologies Pvt Ltd") and context-cue
# based ("Employer: Acme Corp").
# --------------------------------------------------------------------------
_SUFFIX_ALT = "|".join(re.escape(s) for s in sorted(G.COMPANY_SUFFIXES, key=len, reverse=True))
# Prefix tokens are normally capitalized words, but also allow a bare
# number (entity names using an arabic numeral instead of a Roman numeral,
# e.g. "KSH Infra Park 5 Private Limited") and the lowercase connector
# "and" (real multi-part company names like "CG Power and Industrial
# Solutions Limited" -- without this, "and" being lowercase broke the
# prefix chain and only "Industrial Solutions Limited" got captured,
# missing "CG Power" entirely; caught by testing against the real
# reference document's supplier/customer list).
# Suffix alternation matched case-insensitively (scoped -- see the
# NAME_CUE_RE comment for why a global re.IGNORECASE would be wrong here
# too) so "WATERLOO INDUSTRIAL PARK VI PRIVATE LIMITED" on a cover page
# matches just as well as "Waterloo Industrial Park VI Private Limited"
# in running prose. Without this, ALL-CAPS company names fell through to
# NAME's ALL-CAPS fallback tier instead, which has no way to know
# "PARK" here is part of a company rather than a coincidental surname
# match.
COMPANY_SUFFIX_RE = re.compile(
    rf"\b(?:(?:[A-Z][\w&.'-]*|\d+|and|&)\s+){{1,6}}(?i:{_SUFFIX_ALT})\b"
)


_SUFFIX_WORDS_LOWER = {w.lower().rstrip(".") for s in G.COMPANY_SUFFIXES for w in s.split()}


def _clean_company_span(start: int, end: int, raw: str) -> tuple | None:
    """Post-process a raw COMPANY match: trim any leading sentence
    fragment that got swept in (a stray ". " means a new sentence started
    inside the match), then reject boilerplate defined-terms and
    suffix-only matches. Returns (start, end, text) or None to drop it."""
    text = raw
    local_start = start
    last_boundary = text.rfind(". ")
    if last_boundary != -1:
        local_start = start + last_boundary + 2
        text = text[last_boundary + 2:]

    text = text.strip()
    # A leading conjunction/article commonly gets swept in from a list
    # context ("... Trust AND Waterloo Industrial Park VI Private
    # Limited") since it's just another capitalized-looking prefix token.
    for lead in ("and ", "or ", "the "):
        if text[:len(lead)].lower() == lead:
            local_start += len(lead)
            text = text[len(lead):]
            break
    if not text:
        return None

    norm = re.sub(r"\s+", " ", text).lower().rstrip(".")
    if norm in G.COMPANY_STOPPHRASES:
        return None

    tokens = [t.lower().rstrip(".") for t in text.split()]
    if all(t in _SUFFIX_WORDS_LOWER for t in tokens):
        return None

    return local_start, local_start + len(text), text


def find_companies(text: str) -> List[Span]:
    spacy_spans = _spacy_entities(text, "ORG", "COMPANY")
    if spacy_spans:
        return spacy_spans

    candidates = [(m.start(), m.end(), m.group()) for m in COMPANY_SUFFIX_RE.finditer(text)]
    for cue in G.COMPANY_CONTEXT_CUES:
        # Same scoped-case-insensitivity reasoning as NAME_CUE_RE above.
        pattern = re.compile(
            rf"\b(?i:{re.escape(cue)})\s*[:\-]?\s+([A-Z][\w&.'-]*(?:\s+[A-Z][\w&.'-]*){{0,5}})"
        )
        for m in pattern.finditer(text):
            candidates.append((m.start(1), m.end(1), m.group(1)))

    spans = []
    for start, end, raw in candidates:
        cleaned = _clean_company_span(start, end, raw)
        if cleaned is None:
            continue
        c_start, c_end, c_text = cleaned
        spans.append(_mk(c_start, c_end, c_text, "COMPANY"))
    return spans


# --------------------------------------------------------------------------
# ADDRESS -- heuristic: "<house/unit number> ... <street-type word>"
# optionally followed by a city/state/PIN tail. Weakest-recall detector in
# this toolkit; see README.
# --------------------------------------------------------------------------
_STREET_ALT = "|".join(re.escape(s) for s in G.STREET_TYPES)
# Widened against the real reference document during testing: Indian
# building/society names routinely run 5-6 words before the street-type
# keyword ("... NCL co-operative housing society"), and the tail after it
# is usually comma- OR en-dash-separated ("Pune – 411 004"), not just
# comma-separated. See README for the (still real) recall gap this leaves.
ADDRESS_RE = re.compile(
    rf"\b\d{{1,6}}[A-Za-z]?,?\s+(?:[A-Za-z0-9.'-]+,?\s+){{0,6}}(?:{_STREET_ALT})\b"
    rf"(?:[,–—-]\s*[A-Za-z0-9.'\- ]{{2,50}}){{0,5}}"
    rf"(?:[,–—-]?\s*\b\d{{5}}(?:-\d{{4}})?\b|\s*\b\d{{6}}\b)?",
    re.IGNORECASE,
)


def find_addresses(text: str) -> List[Span]:
    spans = []
    for m in ADDRESS_RE.finditer(text):
        raw = m.group()
        # The trailing "city/state" capture group is intentionally
        # permissive (addresses are written inconsistently), which means
        # it sometimes swallows a sentence-ending period. Trim that back
        # off rather than redact the full stop along with the address.
        trimmed = raw.rstrip(" .,;:")
        if not trimmed:
            continue
        spans.append(_mk(m.start(), m.start() + len(trimmed), trimmed, "ADDRESS"))
    return spans


# --------------------------------------------------------------------------
# NAME -- two tiers:
#   1) high-confidence: honorific- or field-label-prefixed capitalised
#      sequence ("Mr. Rohan Dey", "Customer Name: Rashi Patil").
#   2) fallback: bare Title-Case bigram/trigram, accepted only if at least
#      one token is in the first/last-name gazetteer and none is a known
#      ticket-log stopword.
# --------------------------------------------------------------------------
# Capital letter followed by lower-case letters only, so ALL-CAPS acronyms
# ("IP", "SLA", "TCK") don't masquerade as "Title Case" name tokens.
_TITLE_TOKEN = r"[A-Z][a-z'\-]+"

# NOTE: the cue alternation is matched case-insensitively via a *scoped*
# inline flag `(?i: ... )` rather than compiling the whole pattern with
# re.IGNORECASE -- a global IGNORECASE would also flatten the `[A-Z]` in
# _TITLE_TOKEN below, defeating the whole point of requiring Title Case
# for the captured name (this was a real bug caught during testing: it
# let lowercase words like "log" get captured as a "name").
_CUE_ALT = "|".join(re.escape(c) for c in sorted(G.NAME_CONTEXT_CUES, key=len, reverse=True))
NAME_CUE_ANCHOR_RE = re.compile(rf"\b(?i:{_CUE_ALT})\s*[:\-]?\s+")
NAME_TITLE_ANCHOR_RE = re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof|Shri|Smt|Mx)\.?\s+")

# A maximal run of consecutive Title-Case tokens, e.g. in "Sarthak
# Malvadkar Company Secretary and Compliance Officer" this matches
# "Sarthak Malvadkar Company Secretary" (stops at "and", the first
# non-Title-Case token).
_TITLE_RUN_RE = re.compile(rf"{_TITLE_TOKEN}(?:\s+{_TITLE_TOKEN})*")

# ALL-CAPS run, e.g. "KUSHAL SUBBAYYA HEGDE" on a prospectus cover page.
# Legal/financial cover pages routinely render promoter/signatory names in
# full caps for emphasis, which _TITLE_TOKEN deliberately does NOT match
# (that exclusion is what stops 2-3 letter acronyms like "IP"/"SLA"/"TCK"
# from being mistaken for names -- see the comment on _TITLE_TOKEN).
# Requiring >=2 tokens here (via `_run_windows(min_len=2, ...)` below)
# keeps that acronym protection: a lone all-caps word never qualifies on
# its own, only a multi-word run does, and every window still has to pass
# the gazetteer check just like the Title-Case bare-bigram tier.
_CAPS_TOKEN = r"[A-Z]{2,}"
_CAPS_RUN_RE = re.compile(rf"{_CAPS_TOKEN}(?:\s+{_CAPS_TOKEN})*")


def _clean_name_group(raw: str) -> str:
    return raw.strip().rstrip(",.;:")


def _tokens_ok(name: str) -> bool:
    tokens = [t.lower().strip("'.") for t in name.split()]
    if not tokens:
        return False
    if any(t in G.NAME_STOPWORDS for t in tokens):
        return False
    if " ".join(tokens) in G.PLACE_NAME_STOPWORDS:
        return False
    return True


def _in_gazetteer(name: str) -> bool:
    tokens = [t.lower().strip("'.") for t in name.split()]
    return any(t in G.FIRST_NAMES or t in G.LAST_NAMES for t in tokens)


def _run_windows(text: str, run_start: int, run_end: int, min_len: int, max_len: int,
                  require_gazetteer: bool, token_pattern: str = _TITLE_TOKEN):
    """Scan a maximal Title-Case run left to right. At each position, try
    the LONGEST window (up to max_len tokens) first and fall back to
    shorter ones, accepting the first that passes `_tokens_ok` (and the
    gazetteer check, if required).

    This exists because a plain greedy regex (`(?:TOKEN\\s*){1,4}`) only
    ever tries the maximal span at a given start position: if "Sarthak
    Malvadkar Company Secretary" is what's there, a bare greedy match
    swallows "Company" (a stopword) into the candidate, `_tokens_ok`
    rejects the WHOLE thing, and the regex engine -- having already
    consumed those characters as "the match at that position" -- never
    backs off to try the valid "Sarthak Malvadkar" prefix on its own.
    That's a real bug this fixes: it was caught by a name on the
    document's own cover page ("Sarthak Malvadkar Company Secretary and
    Compliance Officer") going completely unredacted, immediately
    followed by "Company" every other place that same name appeared with
    normal surrounding prose *did* get redacted correctly.
    """
    tokens = [(m.start(), m.end(), m.group()) for m in re.finditer(token_pattern, text[run_start:run_end])]
    tokens = [(run_start + s, run_start + e, t) for s, e, t in tokens]

    windows = []
    i = 0
    n = len(tokens)
    while i < n:
        matched = False
        top = min(max_len, n - i)
        for length in range(top, min_len - 1, -1):
            window = tokens[i:i + length]
            cand_start, cand_end = window[0][0], window[-1][1]
            cand_text = text[cand_start:cand_end]
            if not _tokens_ok(cand_text):
                continue
            if require_gazetteer and not _in_gazetteer(cand_text):
                continue
            windows.append((cand_start, cand_end, cand_text))
            i += length
            matched = True
            break
        if not matched:
            i += 1
    return windows


def find_names(text: str) -> List[Span]:
    spacy_spans = _spacy_entities(text, "PERSON", "NAME")
    if spacy_spans:
        return spacy_spans

    spans: List[Span] = []
    claimed: List[tuple] = []  # (start, end) already emitted by a higher-confidence tier

    def _overlaps_claimed(start, end) -> bool:
        return any(not (end <= a or start >= b) for a, b in claimed)

    # Tier 1: honorific-prefixed ("Mr. Rohan Dey") -- highest confidence,
    # no gazetteer check needed since the honorific itself is the signal.
    for anchor in NAME_TITLE_ANCHOR_RE.finditer(text):
        run = _TITLE_RUN_RE.match(text, anchor.end())
        if not run:
            continue
        for start, end, name in _run_windows(text, run.start(), run.end(), min_len=1, max_len=4, require_gazetteer=False):
            spans.append(_mk(start, end, name, "NAME"))
            claimed.append((start, end))

    # Tier 2: field-label/cue-prefixed ("Customer Name: Rashi Patil").
    for anchor in NAME_CUE_ANCHOR_RE.finditer(text):
        run = _TITLE_RUN_RE.match(text, anchor.end())
        if not run or _overlaps_claimed(run.start(), run.end()):
            continue
        for start, end, name in _run_windows(text, run.start(), run.end(), min_len=1, max_len=4, require_gazetteer=False):
            spans.append(_mk(start, end, name, "NAME"))
            claimed.append((start, end))

    # Tier 3: bare Title-Case bigram/trigram fallback, gated on the
    # gazetteer so we don't flag every capitalized phrase in the document.
    for run in _TITLE_RUN_RE.finditer(text):
        if _overlaps_claimed(run.start(), run.end()):
            continue
        for start, end, name in _run_windows(text, run.start(), run.end(), min_len=2, max_len=3, require_gazetteer=True):
            spans.append(_mk(start, end, name, "NAME"))
            claimed.append((start, end))

    # Tier 4: bare ALL-CAPS bigram/trigram (cover pages, signature blocks).
    # Same gazetteer gate and >=2-token minimum as Tier 3 -- see the
    # _CAPS_TOKEN comment for why single acronym-length tokens can't
    # qualify here.
    for run in _CAPS_RUN_RE.finditer(text):
        if _overlaps_claimed(run.start(), run.end()):
            continue
        for start, end, name in _run_windows(
            text, run.start(), run.end(), min_len=2, max_len=3,
            require_gazetteer=True, token_pattern=_CAPS_TOKEN,
        ):
            spans.append(_mk(start, end, name, "NAME"))
            claimed.append((start, end))

    return spans


ALL_DETECTORS = [
    find_ssns,
    find_credit_cards,
    find_emails,
    find_ips,
    find_dobs,
    find_phones,
    find_addresses,
    find_companies,
    find_names,
]


def detect_all(text: str) -> List[Span]:
    """Run every registered detector and return the raw (possibly
    overlapping) spans. Overlap resolution happens in `redactor.py`."""
    spans: List[Span] = []
    for detector in ALL_DETECTORS:
        spans.extend(detector(text))
    return spans


def resolve_overlaps(spans: List[Span]) -> List[Span]:
    """Greedy interval scheduling: higher-priority (more specific) detector
    types win; among equal priority, longer spans win; ties broken by
    left-to-right position. Guarantees the final span list is
    non-overlapping."""
    ordered = sorted(spans, key=lambda s: (s.priority, -(s.end - s.start), s.start))
    chosen: List[Span] = []
    occupied: List[tuple] = []
    for s in ordered:
        if any(not (s.end <= a or s.start >= b) for a, b in occupied):
            continue
        chosen.append(s)
        occupied.append((s.start, s.end))
    chosen.sort(key=lambda s: s.start)
    return chosen
