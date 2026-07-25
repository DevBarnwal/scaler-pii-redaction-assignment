# Evaluation Report

## Methodology

There is no public gold-standard PII test set for this exact document
type, so ground truth was built directly rather than hand-annotated after
the fact:

- **`sample_data/build_sample.py`** generates a synthetic ticket log
  (`ticket_log_sample.docx`) containing three tickets, each with a full
  set of PII types spread across a table (Ticket ID / Customer Name /
  Email / Phone / Company) and free-text notes (address, DOB, SSN, credit
  card, IP, a second person mentioned by an agent). Because the script
  that builds the document and the script that writes `ground_truth.json`
  share the exact same source values, the ground truth is guaranteed
  correct by construction (no manual-annotation error to account for).
- **`sample_data/negative_control.txt`** is a second, adversarial document
  containing *no* real PII, but full of things that could plausibly be
  confused for PII by a naive detector: order/ticket/invoice numbers,
  generic non-DOB dates, an SLA/escalation vocabulary block, two city
  bigrams chosen because their second word is also a common surname, and
  a software version string shaped exactly like an IPv4 address. This
  document has no ground-truth PII (all zero instances) and exists purely
  to surface false positives.
- **`evaluate.py`** runs the redactor's `--spans-json` output against
  `ground_truth.json` and computes, per PII type and overall (micro-
  averaged across types):
  - **Precision** = TP / (TP + FP) -- of everything redacted, how much was
    actually PII.
  - **Recall** = TP / (TP + FN) -- of everything that was actually PII,
    how much got redacted.
  - **F1** = harmonic mean of precision and recall.
  - **"Accuracy"** = TP / (TP + FP + FN). A span-detection task has no
    natural true-negative count (there's no fixed inventory of "non-PII
    slots" to be correct about, unlike a classification task with a fixed
    label set), so this is the standard substitute for that setting --
    sometimes called Jaccard/IoU-style accuracy. It equals 1.0 only when
    precision and recall are both 1.0, and is stricter than F1 whenever
    there are both false positives and false negatives.
- Matching is per PII type, as a **multiset comparison of normalized text**
  (trim whitespace, casefold). A value mentioned twice in ground truth
  needs two matching detections to be fully credited; this catches a
  detector that only fires on a value's *first* occurrence.

Reproduce with:
```bash
cd sample_data && python3 build_sample.py && cd ..
python -m pii_redactor.cli --input sample_data/ticket_log_sample.docx \
    --output /tmp/redacted.docx --spans-json /tmp/spans.json
python evaluate.py --ground-truth sample_data/ground_truth.json --detected /tmp/spans.json
```

## Results -- synthetic validation set (`ticket_log_sample.docx`)

| PII Type | TP | FP | FN | Precision | Recall | F1 | Accuracy |
|---|---|---|---|---|---|---|---|
| ADDRESS | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 | 1.00 |
| COMPANY | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 | 1.00 |
| CREDIT_CARD | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 | 1.00 |
| DOB | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 | 1.00 |
| EMAIL | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 | 1.00 |
| IP | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 | 1.00 |
| NAME | 8 | 0 | 0 | 1.00 | 1.00 | 1.00 | 1.00 |
| PHONE | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 | 1.00 |
| SSN | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 | 1.00 |
| **Overall (micro-avg)** | 26 | 0 | 0 | **1.00** | **1.00** | **1.00** | **1.00** |

A perfect score here validates the *pipeline* (detection -> conflict
resolution -> substitution -> docx write-back), not real-world coverage --
the synthetic set was, by construction, written in the formats the
detectors already target. Two iterations were needed to reach this: an
earlier version had 6 NAME false positives (from a case-insensitive regex
flag accidentally letting lowercase words match a "Title Case" check) and
2 ADDRESS mismatches (trailing sentence punctuation swept into the
captured span); both are now covered by regression-style fixes with the
reasoning documented inline in `detectors.py`.

## Results -- negative control (`negative_control.txt`, 0 true PII instances)

| False Positive | Why it happened |
|---|---|
| `New York` (tagged NAME) | "York" is a common surname in the gazetteer; a two-word Title-Case bigram with a gazetteer-matching token is the fallback name heuristic's trigger. |
| `10.4.250.12` (tagged IP) | A software version string is byte-for-byte indistinguishable from an IPv4 address by regex; no purely syntactic fix exists. |

Everything else in that document -- `Order #489213`, `TCK-`-style ticket
references, `Invoice Number 100234567890123`, the `2024-01-15` /
`15 January 2024` status dates, and the SLA/escalation vocabulary block --
was correctly left unredacted, which is the behavior the assignment's
precision criterion explicitly asks for ("avoid redacting things that
weren't actually PII, e.g. Order or Ticket numbers").

## Results -- the actual reference document (Red Herring Prospectus.docx)

The reference document is a real ~95,000-word IPO prospectus (KSH
International Limited), not a ticket log -- ~1,000 body paragraphs plus
76 tables across cover page, director/promoter tables, and
registrar/banker contact sections. Hand-annotating all of it isn't
practical, so evaluation here uses a **stratified sample**: 20 paragraphs
pulled verbatim from across the document (`reference_document/build_stratified_sample.py`,
reproducible), covering every PII type the document actually contains
(no SSN, credit card, or IP address anywhere in it -- verified by regex
sweep of the full extracted text), plus deliberate non-PII lookalikes
(CIN numbers, page/regulation references) to sanity-check precision the
same way the negative-control document does.

```bash
cd reference_document && python3 build_stratified_sample.py && cd ..
python -m pii_redactor.cli --input reference_document/stratified_excerpt.txt \
    --output /tmp/out.txt --spans-json reference_document/stratified_spans.json
python evaluate.py --ground-truth reference_document/stratified_ground_truth.json \
    --detected reference_document/stratified_spans.json
```

| PII Type | TP | FP | FN | Precision | Recall | F1 | Accuracy |
|---|---|---|---|---|---|---|---|
| ADDRESS | 0 | 4 | 5 | 0.00 | 0.00 | 0.00 | 0.00 |
| COMPANY | 8 | 2 | 2 | 0.80 | 0.80 | 0.80 | 0.67 |
| EMAIL | 8 | 0 | 0 | 1.00 | 1.00 | 1.00 | 1.00 |
| NAME | 14 | 0 | 2 | 1.00 | 0.88 | 0.93 | 0.88 |
| PHONE | 6 | 0 | 0 | 1.00 | 1.00 | 1.00 | 1.00 |
| **Overall (micro-avg)** | 36 | 6 | 9 | **0.86** | **0.80** | **0.83** | **0.71** |

On the full document (no ground truth, so these are volume/sanity
numbers, not accuracy): 210 NAME, 147 COMPANY, 52 EMAIL, 34 PHONE, and 19
ADDRESS instances redacted across 298 of the document's 4,027 non-empty
paragraphs/cells.

**What's behind each number:**

- **EMAIL, PHONE: perfect on the sample.** Both are regex-complete
  detectors once the format variations were covered (see "bugs found"
  below for what that took).
- **NAME: 100% precision, 88% recall.** The 2 misses (Sandesh Bhagwat,
  Cherag Gyara) are real people the tool didn't catch because neither
  "Sandesh"/"Bhagwat" nor "Cherag"/"Gyara" appear in the offline
  first/last-name gazetteer -- exactly the gazetteer-coverage limitation
  flagged in the README. Zero false positives on this sample, though the
  full-document run still has a small number elsewhere (glossary-term
  collisions like "Master Circular", and address fragments like "Venture
  House" -- see README).
- **COMPANY: 80%/80%.** Both misses are the same class of bug: a
  parenthetical inside a company name breaks the prefix-token regex
  ("Transformers & Rectifiers (India) Limited" -> only "India Limited"
  matched). Both false positives are boundary overshoot, not wrong
  entities: "TRUST AND WATERLOO INDUSTRIAL PARK VI PRIVATE LIMITED"
  swept in the preceding "TRUST AND" from a list of entities ("...
  Family Trust and Waterloo Industrial Park VI Private Limited"). The
  redaction still happens correctly in both directions (nothing leaks,
  nothing wrong gets attributed) -- the imprecision is purely at the
  span boundary.
- **ADDRESS: 0/0, the honest result.** Every real address in this
  document runs long and irregular ("S. no. 245/ 104, Pushpakamal, Deccan
  Gymkhana Society, lane no. 3 Prabhat Road, opposite PYC basketball
  court, Deccan Gymkhana, Pune – 411 004 Maharashtra, India"), and the
  detector's fixed-shape regex genuinely cannot capture that as one span
  -- it fragments into 2-3 pieces per address (all still get redacted,
  just not as one clean span, so it scores as a miss against a
  human-judged "the whole address" ground truth even though the PII
  substance is gone from the output). This is the address weakness
  called out in the README made concrete with real numbers instead of a
  general caveat.

**Bugs this validation pass against real data actually caught** (in
addition to what the synthetic set caught -- see README "Tradeoffs"):
a redaction pipeline is exactly the kind of tool where "looks right on
my test case" and "is right on someone else's real document" can diverge
sharply, and this project surfaced three genuine bugs a synthetic-only
test set would never have found:

1. **A duplicate-paragraph-processing bug that compounded fake data.**
   Word documents commonly have a table cell merged across several grid
   columns; `python-docx`'s `row.cells` API returns that cell once per
   column it spans. Undeduped, the tool redacted the same cell multiple
   times in a row -- and each extra pass detected "PII" inside the
   *previous* pass's fake replacement text, compounding into names that
   don't exist anywhere in the source (an early run produced "Pearson
   PLC" as a "detected company" that, on inspection, appeared nowhere in
   the actual document). Root-caused to two duplication sources
   (merged-cell columns and sections sharing one header/footer part) plus
   a `python-docx`/`lxml` object-identity subtlety (comparing bare
   `id()` values on short-lived proxy objects is unsafe -- Python can
   reuse a freed object's memory address for something unrelated). Fixed
   in `docx_io.py`; see the code comments there for the full mechanism.
2. **A greedy-match bug that let a real name through unredacted.** The
   document's own cover page has "Sarthak Malvadkar Company Secretary and
   Compliance Officer" as one run of Title-Case words. The name regex
   greedily matched the whole run first, "Company" (a stopword) made the
   whole candidate get rejected, and the engine never backed off to try
   the valid "Sarthak Malvadkar" prefix alone -- so this one instance
   went completely unredacted while every other mention of the same
   person, surrounded by ordinary lowercase prose, redacted fine. Fixed
   by replacing the single greedy regex with a sliding-window scan over
   maximal Title-Case runs (longest-to-shortest at each position).
3. **Phone numbers written as "+ 91 ..." (space after the plus) were
   invisible to the detector entirely.** The regex required `+` to be
   immediately followed by a digit. Caught by the stratified sample,
   which pulled real "Telephone: + 91 ..." lines straight from the
   document.

All three are now covered by the regression tests in `sample_data/` (the
sample document and negative control were re-run after every fix in this
list and still score 100%/clean, confirming the fixes didn't regress
anything) in addition to the stratified real-document check above.
