"""
Generates and caches fake replacement values so that the SAME original
piece of PII always maps to the SAME fake value everywhere it appears in
the document (e.g. every occurrence of "rashi.patil@gmail.com" becomes the
same "john.doe@example.com", and "Rashi Patil" always becomes the same
fake person).

Determinism: `Faker.seed(SEED)` makes a re-run of the tool on the same
document produce byte-identical output, which makes the redacted file
diffable / reviewable across runs.
"""

from __future__ import annotations

import re
from typing import Dict

from faker import Faker

SEED = 42


class FakeValueMapper:
    def __init__(self, seed: int = SEED):
        self.fake = Faker()
        Faker.seed(seed)
        # one cache per PII type, keyed by a normalised form of the original
        self._cache: Dict[str, Dict[str, str]] = {}
        # word-level cache so name FRAGMENTS (just a first name, just a
        # surname) stay consistent with any full name already mapped
        self._name_word_cache: Dict[str, str] = {}

    def _cache_for(self, ptype: str) -> Dict[str, str]:
        return self._cache.setdefault(ptype, {})

    @staticmethod
    def _norm(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())

    # ------------------------------------------------------------------
    def fake_for(self, ptype: str, original: str) -> str:
        cache = self._cache_for(ptype)
        key = self._norm(original)
        if key in cache:
            return cache[key]

        method = getattr(self, f"_gen_{ptype.lower()}", None)
        fake_value = method(original) if method else self.fake.word()
        cache[key] = fake_value
        return fake_value

    # ------------------------------------------------------------------
    def _gen_name(self, original: str) -> str:
        tokens = original.split()
        fake_tokens = []
        for i, tok in enumerate(tokens):
            wkey = tok.lower().strip("'.")
            if wkey in self._name_word_cache:
                fake_tokens.append(self._name_word_cache[wkey])
                continue
            if i == 0:
                fake_word = self.fake.first_name()
            else:
                fake_word = self.fake.last_name()
            self._name_word_cache[wkey] = fake_word
            fake_tokens.append(fake_word)
        return " ".join(fake_tokens)

    def _gen_email(self, original: str) -> str:
        local = original.split("@", 1)[0]
        # Try to derive "first.last" style from a name we've already faked,
        # otherwise fake a plausible-looking local part directly.
        guess_tokens = re.split(r"[._\-+0-9]+", local)
        guess_tokens = [t for t in guess_tokens if t]
        fake_tokens = []
        for tok in guess_tokens or [local]:
            wkey = tok.lower()
            if wkey in self._name_word_cache:
                fake_tokens.append(self._name_word_cache[wkey])
            else:
                fake_tokens.append(self.fake.first_name() if not fake_tokens else self.fake.last_name())
        fake_local = ".".join(t.lower() for t in fake_tokens) if fake_tokens else self.fake.user_name()
        return f"{fake_local}@example.com"

    def _gen_phone(self, original: str) -> str:
        digits = re.sub(r"\D", "", original)
        if len(digits) >= 12 and digits.startswith("91"):
            new_number = str(self.fake.random_int(6, 9)) + "".join(
                str(self.fake.random_digit()) for _ in range(9)
            )
            return f"+91 {new_number}"
        if len(digits) == 10:
            new_number = str(self.fake.random_int(6, 9)) + "".join(
                str(self.fake.random_digit()) for _ in range(9)
            )
            return new_number
        # generic fallback: keep length & punctuation skeleton, randomise digits
        out = []
        for ch in original:
            out.append(str(self.fake.random_digit()) if ch.isdigit() else ch)
        return "".join(out)

    def _gen_company(self, original: str) -> str:
        return self.fake.company()

    def _gen_address(self, original: str) -> str:
        return self.fake.address().replace("\n", ", ")

    def _gen_ssn(self, original: str) -> str:
        return self.fake.ssn()

    def _gen_credit_card(self, original: str) -> str:
        digits = re.sub(r"[ -]", "", original)
        new_digits = self.fake.credit_card_number()
        new_digits = re.sub(r"\D", "", new_digits)
        new_digits = (new_digits + new_digits)[: len(digits)]
        # re-apply the original grouping/punctuation skeleton
        out = []
        di = 0
        for ch in original:
            if ch.isdigit():
                out.append(new_digits[di])
                di += 1
            else:
                out.append(ch)
        return "".join(out)

    def _gen_dob(self, original: str) -> str:
        fake_date = self.fake.date_of_birth(minimum_age=18, maximum_age=75)
        if re.match(r"\d{4}-\d{1,2}-\d{1,2}", original):
            return fake_date.strftime("%Y-%m-%d")
        if re.search(r"[A-Za-z]", original):
            return fake_date.strftime("%d %B %Y")
        if "/" in original:
            return fake_date.strftime("%d/%m/%Y")
        return fake_date.strftime("%d-%m-%Y")

    def _gen_ip(self, original: str) -> str:
        return self.fake.ipv4_public()
