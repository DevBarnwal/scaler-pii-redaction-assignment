"""
pii_redactor
============

A small, dependency-light toolkit for detecting and redacting personally
identifiable information (PII) in ticket-log style documents (.docx / .txt),
replacing every instance with a *consistent* fake alternative.

Modules
-------
gazetteer   - static word lists used by the heuristic detectors (names,
              stopwords, company suffixes, address keywords).
detectors   - one function per PII type; each returns a list of `Span`
              objects. Adding a new PII type = adding one function here.
faker_map   - generates and caches fake replacement values, so the same
              original value always maps to the same fake value.
redactor    - orchestrates detection (conflict resolution across
              detectors) and substitution.
docx_io     - reads paragraphs/table cells out of a .docx and writes a
              redacted copy back.
"""

__version__ = "1.0.0"
