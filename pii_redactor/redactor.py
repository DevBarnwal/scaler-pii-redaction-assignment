"""
Core orchestration: text in -> (detected spans, redacted text) out.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .detectors import Span, detect_all, resolve_overlaps
from .faker_map import FakeValueMapper


@dataclass
class RedactionResult:
    original_text: str
    redacted_text: str
    spans: List[Span]  # spans as found in the ORIGINAL text


class Redactor:
    """Stateful across an entire document: reuse one instance for every
    paragraph/cell so the same PII value maps to the same fake value
    everywhere in the file."""

    def __init__(self, seed: int = 42):
        self.mapper = FakeValueMapper(seed=seed)

    def redact(self, text: str) -> RedactionResult:
        if not text or not text.strip():
            return RedactionResult(text, text, [])

        raw_spans = detect_all(text)
        spans = resolve_overlaps(raw_spans)

        out = []
        cursor = 0
        for s in spans:
            out.append(text[cursor:s.start])
            out.append(self.mapper.fake_for(s.type, s.text))
            cursor = s.end
        out.append(text[cursor:])

        return RedactionResult(text, "".join(out), spans)
