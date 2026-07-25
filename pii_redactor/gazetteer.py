"""
Static word lists backing the heuristic (non-ML) detectors.

Name gazetteers are pulled from Faker's own bundled data files (en_US and
en_IN locales) so the tool works fully offline -- no model download and no
network access required. This also means it is trivial to widen coverage:
add another locale's Provider to `_LOCALES` and the name lists grow
automatically.
"""

from __future__ import annotations

from faker.providers.person.en_US import Provider as _EnUS
from faker.providers.person.en_IN import Provider as _EnIN

_LOCALES = (_EnUS, _EnIN)


def _collect(attr: str) -> set[str]:
    names: set[str] = set()
    for provider in _LOCALES:
        values = getattr(provider, attr, ())
        names.update(v.strip(".") for v in values)
    return names


FIRST_NAMES = {n.lower() for n in _collect("first_names")}
LAST_NAMES = {n.lower() for n in _collect("last_names")}

# Common honorifics / titles that reliably precede a person's name.
NAME_TITLES = {
    "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "miss", "dr", "dr.",
    "prof", "prof.", "shri", "smt", "mx", "mx.",
}

# Phrases that commonly introduce a name field in a structured ticket log.
# Matched case-insensitively immediately before the candidate name.
# Deliberately excludes bare prepositions like "from"/"to"/"cc" -- those
# fired on ordinary sentences ("Called from IP ...") in testing, so only
# multi-word phrases or clearly name-specific labels are kept (precision
# over recall for this tier; the honorific tier below covers "Mr X").
NAME_CONTEXT_CUES = [
    "customer name", "full name", "client name", "contact name",
    "reported by", "requested by", "raised by", "assigned to",
    "agent name", "employee name", "account holder", "cardholder",
    "attn", "attention", "dear", "regards", "sincerely", "yours",
    "signed", "point of contact", "poc",
]

# Capitalised words that look like a "Title Case" name but are common
# ticket-log vocabulary -- excluded so precision doesn't collapse on
# generic Capitalized Words that aren't people.
NAME_STOPWORDS = {
    "ticket", "order", "invoice", "subject", "priority", "status",
    "date", "issue", "product", "reference", "case", "request",
    "company", "address", "phone", "email", "account", "reference",
    "department", "team", "support", "customer", "service", "region",
    "branch", "division", "id", "number", "amount", "total", "summary",
    "description", "category", "type", "channel", "resolution", "sla",
    "escalation", "severity", "queue", "agent", "notes", "comments",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday", "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "india", "usa", "united", "states", "pvt", "ltd", "inc", "llc",
    "name", "names", "full", "customer name", "employee", "user",
    "mr", "mrs", "ms", "miss", "dr", "prof", "shri", "smt", "mx",
    "ip", "sla", "tck", "pin", "dob", "ssn", "cc",
    # Words that are simultaneously (a) common English surnames -- so they
    # pass the gazetteer check the bare-bigram NAME fallback relies on --
    # and (b) routine capitalized vocabulary in financial/legal defined
    # terms. Found by auditing detector output against the real reference
    # document (a listed-company prospectus): "Price" caught "Floor
    # Price"/"Cap Price"/"Offer Price"; "Bank(s)" caught "Sponsor Banks";
    # "Herring" caught "Red Herring Prospectus"; "Term"/"Long"/"Short"
    # caught "Long Term"/"Short Term"; "Key"/"Green"/"Day"/"Gross" caught
    # "Key Managerial Personnel"/"Green Shoe Option"/"Working Day"/"Gross
    # Proceeds". This is an explicit precision-over-recall call: it means
    # a real person surnamed Price, Bank(s), Herring, Term, Key, Green,
    # Day, Long, Short, or Gross would be missed by ALL tiers, not just
    # the bare-bigram fallback (`_tokens_ok` gates every tier). Judged
    # worth it here: these words are common enough as ordinary/financial
    # vocabulary that leaving them in caused far more false positives
    # than the plausible true positives they'd cost on a document like
    # this one.
    "price", "bank", "banks", "herring", "term", "key", "green",
    "day", "gross", "long", "short", "board", "working", "cap",
    "floor", "offer", "cut-off", "cutoff",
    # Designation/job-title words that directly follow a person's name in
    # this document's director/KMP tables ("Ram Kumar Tiwari Independent
    # Director ..."), which the greedy-then-shrink window in
    # `_run_windows` would otherwise happily fold into the "name" since
    # they're Title-Case too. Same root cause as "Company"/"Secretary"
    # above, just more of them once real director-table text was tested.
    "website", "independent", "director", "chairman", "managing",
    "joint", "executive", "officer", "compliance", "whole-time",
    "chief", "technical", "finance",
}

# Suffixes that strongly indicate a company / organisation name.
# NOTE: bare "Company" and "Co" are deliberately excluded -- legal/
# financial documents (prospectuses, contracts) routinely define "the
# Company" / "our Company" as a capitalized defined term referring to the
# document's own subject, and that pattern drowned out real company names
# in testing on an actual prospectus. "Co." (with the period) is kept
# since it's a much less ambiguous signal.
COMPANY_SUFFIXES = [
    "Inc", "Inc.", "LLC", "L.L.C.", "Ltd", "Ltd.", "Limited",
    "Pvt Ltd", "Pvt. Ltd.", "Private Limited", "Corp", "Corp.",
    "Corporation", "Co.", "Technologies", "Tech",
    "Solutions", "Systems", "Enterprises", "Industries", "Group",
    "Holdings", "Labs", "Laboratories", "Partners", "Associates",
    "PLC", "GmbH", "S.A.", "LLP",
]

# Generic defined-term phrases that legal/financial documents capitalize
# but that are not actually a company's name (they're a pronoun-like
# stand-in for "this document's own subject"). Filtered out regardless of
# which detector path produced them.
COMPANY_STOPPHRASES = {
    "our company", "the company", "our group", "the group",
    "group entities", "our group entities", "the promoter",
    "the promoters", "our promoters", "private limited", "co llp",
    "co. llp", "the issuer", "our issuer", "promoter group",
    "the promoter group", "our promoter group", "we",
}

# Phrases that introduce an employer / company field. Deliberately excludes
# generic prepositions like "at", AND excludes the bare word "company" --
# both produced too many false positives in testing. "Company" is
# specifically routine in legal/financial documents as a capitalized
# DEFINED TERM ("our Company", "the Company Secretary", "Company
# Prospectuses" as a glossary heading) referring back to the document's
# own subject rather than introducing a company name, and testing against
# a real prospectus showed it swallowing unrelated capitalized words that
# happened to follow it ("Company Related Terms", "Company Secretary").
# The suffix-based regex (Ltd/Limited/LLP/Inc/...) remains the primary,
# more reliable company detector; these cues are for the label:value
# style ("Employer: Acme Corp") that suffix-matching alone would miss.
COMPANY_CONTEXT_CUES = [
    "employer", "organization", "organisation", "vendor",
    "client company", "account name", "business name", "firm",
]

# Street-type tokens used by the address heuristic (US + Indian conventions,
# since the source documents are India-based).
STREET_TYPES = [
    "Street", "St", "Road", "Rd", "Avenue", "Ave", "Lane", "Ln",
    "Drive", "Dr", "Boulevard", "Blvd", "Nagar", "Colony", "Sector",
    "Marg", "Cross", "Layout", "Block", "Society", "Apartments",
    "Apartment", "Chowk", "Path", "Circle", "Extension", "Phase",
    "Enclave", "Vihar", "Puram", "Gaon", "Gali",
]

# Multi-word place names that would otherwise pass the bare Title-Case
# name heuristic (a token like "York" or "Delhi" is a real surname in the
# gazetteer too). Not exhaustive -- see README for this known limitation
# of a gazetteer-based (rather than true NER) name detector.
PLACE_NAME_STOPWORDS = {
    "new york", "new delhi", "los angeles", "san francisco", "hong kong",
    "tel aviv", "las vegas", "new jersey", "sri lanka", "south africa",
    "united kingdom", "united states", "saudi arabia", "costa rica",
    "puerto rico", "rio de", "cape town", "salt lake", "santa monica",
    "great britain",
}

# DOB context cues -- generic dates (ticket created/updated dates) must NOT
# be redacted, only dates tied to one of these phrases.
DOB_CONTEXT_CUES = [
    "dob", "d.o.b", "date of birth", "born on", "birth date",
    "born:", "birthdate",
]
