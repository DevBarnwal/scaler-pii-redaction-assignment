# PII Redactor

Redacts personally identifiable information (PII) from a ticket-log `.docx`
(or `.txt`), replacing every instance with a consistent fake alternative --
the same original value always maps to the same fake value everywhere it
appears, so cross-references in the document (a name in a table row and
again in a comment below it) stay internally consistent after redaction.

## Quick start

```bash
pip install -r requirements.txt
python -m pii_redactor.cli --input "Reference Document.docx" --output redacted.docx --spans-json spans.json
```

`--spans-json` is optional; it dumps every detected PII instance (type,
text, character offset) for review or for feeding into `evaluate.py`.

## Testing

Three checks, all using files already committed in this repo -- no setup
beyond `pip install -r requirements.txt` needed.

**1. Regression test against the synthetic ticket log** (expect 1.00
precision/recall/F1 across all 9 PII types):
```bash
python3 -m pii_redactor.cli --input sample_data/ticket_log_sample.docx \
    --output /tmp/redacted.docx --spans-json /tmp/spans.json
python3 evaluate.py --ground-truth sample_data/ground_truth.json --detected /tmp/spans.json
```

**2. Negative-control check** (should redact almost nothing -- this
document is deliberately full of non-PII text designed to look like PII):
```bash
python3 -m pii_redactor.cli --input sample_data/negative_control.txt \
    --output /tmp/negative_out.txt --spans-json /tmp/neg_spans.json
```
Expect exactly one flagged instance (an IP-shaped software version
string -- a known, documented false positive, see "Tradeoffs" below).

**3. Run against the real reference document** (reproduces the numbers
in `evaluation_report.md` -- 210 NAME / 147 COMPANY / 52 EMAIL / 34
PHONE / 19 ADDRESS across 298 of 4,027 non-empty paragraphs/cells):
```bash
python3 -m pii_redactor.cli --input "reference_document/Red Herring Prospectus - Original.docx" \
    --output /tmp/rhp_redacted.docx --spans-json /tmp/rhp_spans.json
```

**4. Stratified precision/recall check against real document content**
(reproduces the table in `evaluation_report.md`'s "Results -- the actual
reference document" section):
```bash
cd reference_document && python3 build_stratified_sample.py && cd ..
python3 -m pii_redactor.cli --input reference_document/stratified_excerpt.txt \
    --output /tmp/strat_out.txt --spans-json reference_document/stratified_spans.json
python3 evaluate.py --ground-truth reference_document/stratified_ground_truth.json \
    --detected reference_document/stratified_spans.json
```

Because Faker is seeded (`--seed 42` by default), every one of these is
deterministic -- re-running produces byte-identical output every time,
which is what makes "diff this against what's in the repo" a valid check
on its own.

## Approach

Nine PII types are covered: full names, emails, phone numbers, company
names, physical/mailing addresses, SSNs, credit card numbers, dates of
birth, and IP addresses. Each type has its own detector function in
`pii_redactor/detectors.py`; a detector is just "text in, list of matched
spans out", so adding an unsupported type (say, passport numbers) means
writing one `find_passport_numbers(text)` function and registering it --
nothing else in the pipeline changes.

**Regex, validated where possible** — emails, IPv4 addresses, and SSNs use
straightforward format regexes. Credit card numbers additionally run
through a **Luhn checksum**, so an arbitrary 16-digit account or ticket ID
doesn't get flagged just because it happens to be the right length.

**Context-gated, not just pattern-gated** — dates of birth are the clearest
example of why this matters. A ticket log is full of dates (created date,
updated date, order date) that are not PII, so `find_dobs` only fires on a
date-shaped string within ~40 characters of an explicit cue ("DOB",
"Date of Birth", "Born on"). Company detection similarly combines a
suffix-based regex ("... Pvt Ltd", "... Technologies") with field-label
cues ("Employer:", "Company:").

**Gazetteer-based name detection, offline** — there's no way for a regex to
"know" a capitalized word is a person's name. Rather than requiring a
model download (blocked in the environment this was built in, and not
guaranteed in whatever environment grades it), `find_names` uses a
sliding-window scan (see `_run_windows` in `detectors.py`) over three
tiers, from most to least confident: (1) honorific-prefixed ("Mr./Dr./
Shri ..."), (2) field-label-cue-prefixed ("Customer Name:", "Reported
by:"), (3) bare two-to-three-word Title-Case sequence, accepted only if
at least one token appears in a first/last-name gazetteer (built from
Faker's bundled en_US + en_IN name lists, ~1,700 names, zero network
calls) and none of the tokens is a known non-name stopword ("Ticket",
"Company", "Independent", "Price", ...) or common place name ("New
York", "New Delhi", ...). A fourth tier repeats the same windowed scan
over ALL-CAPS runs (e.g. "KUSHAL SUBBAYYA HEGDE" on a prospectus cover
page), gated the same way so a lone 2-3 letter acronym ("IP", "SLA")
still can't qualify on its own. **If spaCy and a trained English model
happen to be available in the runtime environment, `find_names` and
`find_companies` transparently switch to NER instead** (`_get_nlp()` in
`detectors.py`) — no config needed, it's just a better detector for the
same job when it exists.

**Fake values, not placeholders** — `faker_map.py` uses `Faker` to
generate realistic-looking replacements (e.g. `4517 6398 2231 0084`
instead of `[REDACTED]`), which is closer to what "replace with a fake
alternative" (per the assignment brief) implies than a blackout mask
would be, and is friendlier for anyone downstream re-testing workflows
against the redacted file. Faker is seeded (`--seed`, default 42) so a
re-run on the same input is byte-identical, and a lightweight word-level
cache keeps first/last names consistent even when a person is referred to
inconsistently (full name in one place, just a surname elsewhere).

## Tradeoffs and known false positives/negatives

This was validated three ways (all reproducible):

1. **A synthetic ticket log** (`sample_data/build_sample.py` generates it,
   with `ground_truth.json` recording every PII value planted) — the
   redactor scores **100% precision/recall across all nine types** on
   this set. Expected: it validates pipeline mechanics, not real-world
   coverage.
2. **A negative-control document** (`sample_data/negative_control.txt`)
   deliberately full of near-miss, non-PII text -- ticket/order/invoice
   numbers, generic status dates, an escalation/SLA vocabulary block, and
   two adversarial cases picked specifically to probe the heuristics:
   - `New York` / `New Delhi` -- "Delhi" and "York" are also real
     surnames in the name gazetteer. A small `PLACE_NAME_STOPWORDS` list
     covers the common cases, but this is not exhaustive and remains a
     source of NAME false positives in this design; a real NER model
     does noticeably better here (which is why the code auto-upgrades to
     spaCy when it's present).
   - `10.4.250.12` (a software version string) is indistinguishable from
     a real IPv4 address by pattern alone and gets redacted as an IP.
     There is no purely syntactic fix for this; it would need document
     context (e.g. "version" nearby) similar to how DOB detection is
     context-gated, which wasn't extended to IP for this pass.
3. **The actual reference document** (`Red Herring Prospectus.docx`, a
   real ~95,000-word IPO prospectus) via a stratified 20-paragraph sample
   pulled verbatim from across it -- see `evaluation_report.md` for the
   full results table. Headline numbers: EMAIL and PHONE 100%/100%, NAME
   100% precision / 88% recall, COMPANY 80%/80%, ADDRESS 0%/0% (see
   below -- this one's real and worth understanding, not a bug). This
   pass against a real, large, structurally-messy document caught three
   genuine bugs a synthetic test set never would have:
   - **A duplicate-paragraph-processing bug that compounded fake data.**
     `python-docx`'s `row.cells` yields a merged cell once per grid
     column it spans; undeduped, the tool redacted the same cell multiple
     times, and each extra pass re-detected the *previous* pass's fake
     replacement as if it were real PII -- producing a "detected company"
     that didn't exist anywhere in the source document. Fixed in
     `docx_io.py` (dedup on live XML element identity, not bare `id()`
     values, which turned out to be unsafe for the reason explained in
     that file's comments).
   - **A greedy-regex bug that let a real name through unredacted.** The
     document's own cover page has "Sarthak Malvadkar Company Secretary
     and Compliance Officer" as one Title-Case run; the old greedy regex
     swallowed "Company" into the candidate, the stopword check rejected
     the whole thing, and it never backed off to try "Sarthak Malvadkar"
     alone. Fixed by replacing the greedy match with the sliding-window
     scan described above.
   - **Phone numbers written "+ 91 ..." (space after the `+`) were
     invisible to the old regex entirely.** Found via the stratified
     sample, which uses real `Telephone: + 91 ...` lines from the
     document.

   ADDRESS's 0%/0% on the stratified sample is the honest result of a
   real, still-open limitation: this document's addresses are long and
   irregular ("S. no. 245/ 104, Pushpakamal, Deccan Gymkhana Society,
   lane no. 3 Prabhat Road, opposite PYC basketball court, ... Pune –
   411 004 Maharashtra, India"), and the fixed-shape address regex
   fragments each one into 2-3 pieces instead of one clean span -- every
   fragment still gets redacted (no PII substance leaks), but it doesn't
   match a human-judged "the whole address" ground truth, so it scores
   as a miss. This is the address weakness below, demonstrated with real
   numbers instead of just a general caveat.

**Explicit precision choice, per the assignment's evaluation criteria:**
"Order #4482", "Ticket TCK-1001", and similar ID-style numbers are treated
as *not* PII and are never redacted -- only numbers matching a specific
PII shape (SSN's `NNN-NN-NNNN`, a Luhn-valid card number, a 10-digit
Indian mobile, etc.) are flagged. This trades a small amount of recall
(a determined attacker could conceivably cross-reference an order number)
for a large precision gain, since ticket logs are otherwise full of
numeric IDs.

**Formatting note on the .docx output:** Word splits a paragraph's visible
text across multiple internal `<w:r>` runs. Detection has to run on the
whole paragraph's joined text (a PII value can straddle a run boundary),
so the redacted text is written back into the paragraph's first run and
any other runs in that paragraph are cleared. Paragraph-level formatting
(heading style, table structure, alignment) is fully preserved; run-level
formatting that varied *within* a paragraph (e.g. only one word bolded)
collapses to whatever the first run's formatting was.

**Address detection is the weakest-recall detector** here -- it depends on
recognizing a street-type keyword (Road, Street, Nagar, Colony, ...) next
to a house/unit number, which will miss address formats that don't follow
that shape (e.g. a bare apartment name with no street-type word).

## Extending to a new PII type

1. Add a `find_<type>(text) -> List[Span]` function to `detectors.py`.
2. Add its entry to `PRIORITY` in the same file (controls which detector
   wins when two overlap -- more specific/validated formats should rank
   above broader heuristics).
3. Register it in `ALL_DETECTORS`.
4. Add a `_gen_<type>(self, original)` method to `FakeValueMapper` in
   `faker_map.py` describing how to fake a replacement value (falls back
   to a generic fake word if omitted).

Nothing in `redactor.py`, `docx_io.py`, or `cli.py` needs to change.

## Files

```
pii_redactor/
  detectors.py       PII detection (one function per type)
  gazetteer.py        static word lists backing the heuristics
  faker_map.py         consistent fake-value generation/caching
  redactor.py          orchestrates detect -> resolve overlaps -> substitute
  docx_io.py            .docx paragraph/table/header-footer traversal
  cli.py                command-line entry point
evaluate.py             precision/recall/accuracy scoring against ground truth
sample_data/
  build_sample.py       generates the synthetic validation ticket log + its ground truth
  ticket_log_sample.docx / ground_truth.json
  negative_control.txt  adversarial "should NOT be redacted" test document
reference_document/
  build_stratified_sample.py   builds a verbatim excerpt + ground truth from the real reference doc
  Red Herring Prospectus - Redacted.docx   the actual deliverable: the redacted reference document
evaluation_report.md    methodology + results (see separate deliverable)
```
