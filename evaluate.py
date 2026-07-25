"""
Computes precision / recall / accuracy of the redactor against a
ground-truth PII list.

Methodology (see evaluation_report.md for the full write-up):
  - Ground truth is a JSON list of {"type": <PII_TYPE>, "text": <exact
    substring as it appears in the source>}, one entry PER OCCURRENCE
    (a value mentioned twice must appear twice in ground truth).
  - Detections come from the redactor's --spans-json output on the SAME
    source document.
  - Matching is done per PII type as a multiset comparison of normalised
    text (trim + collapse whitespace + casefold), which tolerates trivial
    formatting differences without allowing cross-type or wrong-value
    matches to count as correct.
  - TP = matched instances; FN = ground-truth instances with no matching
    detection; FP = detections with no matching ground-truth instance.
  - Precision = TP / (TP + FP)
  - Recall    = TP / (TP + FN)
  - F1        = 2PR / (P + R)
  - "Accuracy" for a span-detection task has no natural true-negative
    count (there's no fixed inventory of "non-PII slots" to be right
    about), so we report the standard substitute used for this style of
    task: Accuracy = TP / (TP + FP + FN) -- i.e. the fraction of the
    union of (predicted, actual) instances that were predicted correctly.
    This is sometimes called the Jaccard / IoU-style accuracy and
    coincides with F1's "harshness" on both false positives and
    negatives at once.

Usage:
    python evaluate.py --ground-truth sample_data/ground_truth.json \
                        --detected spans_detected.json \
                        --out evaluation_report_results.md
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).casefold()


def load_instances(path: str, text_key: str) -> dict[str, Counter]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    by_type: dict[str, Counter] = defaultdict(Counter)
    for item in data:
        by_type[item["type"]][norm(item[text_key])] += 1
    return by_type


def evaluate(ground_truth_path: str, detected_path: str):
    gt = load_instances(ground_truth_path, "text")
    det = load_instances(detected_path, "text")

    types = sorted(set(gt) | set(det))
    rows = []
    totals = Counter()

    for t in types:
        gt_counter = gt.get(t, Counter())
        det_counter = det.get(t, Counter())
        tp = sum((gt_counter & det_counter).values())
        fn = sum(gt_counter.values()) - tp
        fp = sum(det_counter.values()) - tp

        precision = tp / (tp + fp) if (tp + fp) else float("nan")
        recall = tp / (tp + fn) if (tp + fn) else float("nan")
        f1 = (2 * precision * recall / (precision + recall)) if (tp and (precision + recall)) else 0.0
        accuracy = tp / (tp + fp + fn) if (tp + fp + fn) else float("nan")

        rows.append(dict(type=t, tp=tp, fp=fp, fn=fn, precision=precision, recall=recall, f1=f1, accuracy=accuracy))
        totals["tp"] += tp
        totals["fp"] += fp
        totals["fn"] += fn

    tp, fp, fn = totals["tp"], totals["fp"], totals["fn"]
    overall_precision = tp / (tp + fp) if (tp + fp) else float("nan")
    overall_recall = tp / (tp + fn) if (tp + fn) else float("nan")
    overall_f1 = (
        2 * overall_precision * overall_recall / (overall_precision + overall_recall)
        if (tp and (overall_precision + overall_recall)) else 0.0
    )
    overall_accuracy = tp / (tp + fp + fn) if (tp + fp + fn) else float("nan")

    return rows, dict(
        tp=tp, fp=fp, fn=fn,
        precision=overall_precision, recall=overall_recall,
        f1=overall_f1, accuracy=overall_accuracy,
    )


def render_markdown(rows, overall) -> str:
    lines = ["| PII Type | TP | FP | FN | Precision | Recall | F1 | Accuracy |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r['type']} | {r['tp']} | {r['fp']} | {r['fn']} | "
            f"{r['precision']:.2f} | {r['recall']:.2f} | {r['f1']:.2f} | {r['accuracy']:.2f} |"
        )
    lines.append(
        f"| **Overall (micro-avg)** | {overall['tp']} | {overall['fp']} | {overall['fn']} | "
        f"**{overall['precision']:.2f}** | **{overall['recall']:.2f}** | "
        f"**{overall['f1']:.2f}** | **{overall['accuracy']:.2f}** |"
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--detected", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    rows, overall = evaluate(args.ground_truth, args.detected)
    table = render_markdown(rows, overall)
    print(table)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(table + "\n")
        print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
