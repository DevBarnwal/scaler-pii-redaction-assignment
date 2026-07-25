"""
Command-line entry point.

Usage:
    python -m pii_redactor.cli --input ticket_log.docx --output redacted.docx
    python -m pii_redactor.cli --input ticket_log.txt  --output redacted.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

from .docx_io import redact_docx
from .redactor import Redactor


def _run_docx(args: argparse.Namespace) -> None:
    report = redact_docx(args.input, args.output, seed=args.seed)
    print(f"Read {report.paragraph_count} non-empty paragraphs/cells.")
    print(f"Redacted {report.redacted_paragraph_count} of them.")
    print("PII instances redacted, by type:")
    for ptype, count in sorted(report.spans_by_type.items(), key=lambda kv: -kv[1]):
        print(f"  {ptype:<13} {count}")
    print(f"Wrote: {args.output}")

    if args.spans_json:
        payload = [
            {"type": s.type, "text": s.text, "start": s.start, "end": s.end}
            for s in report.all_spans
        ]
        with open(args.spans_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"Wrote detected-span log: {args.spans_json}")


def _run_txt(args: argparse.Namespace) -> None:
    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()
    redactor = Redactor(seed=args.seed)
    result = redactor.redact(text)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(result.redacted_text)

    counts = Counter(s.type for s in result.spans)
    print("PII instances redacted, by type:")
    for ptype, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {ptype:<13} {count}")
    print(f"Wrote: {args.output}")

    if args.spans_json:
        payload = [
            {"type": s.type, "text": s.text, "start": s.start, "end": s.end}
            for s in result.spans
        ]
        with open(args.spans_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"Wrote detected-span log: {args.spans_json}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Redact PII from a ticket log.")
    parser.add_argument("--input", required=True, help="Path to input .docx or .txt")
    parser.add_argument("--output", required=True, help="Path to write the redacted file")
    parser.add_argument("--seed", type=int, default=42, help="Faker random seed (determinism)")
    parser.add_argument(
        "--spans-json", default=None,
        help="Optional path to dump every detected span (type/text/offset) as JSON, for review or evaluation.",
    )
    args = parser.parse_args(argv)

    if args.input.lower().endswith(".docx"):
        _run_docx(args)
    else:
        _run_txt(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
