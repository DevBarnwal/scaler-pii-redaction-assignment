"""
Builds a stratified evaluation sample FROM THE REAL REFERENCE DOCUMENT.

The reference document (Red Herring Prospectus.docx) is ~95,000 words --
too large to hand-annotate PII for in full. Instead this pulls ~20
paragraphs verbatim from across the document (contact/registrar section,
the director/promoter table, cover-page banner, financial boilerplate)
covering every PII type the document actually contains, plus deliberate
non-PII lookalikes (CIN numbers, page references, regulation citations,
ticket-style IDs) to test precision the same way the negative-control
document does.

Every string in `EXCERPTS` below was copied verbatim from the source
document (verified via `pandoc -t plain` and `python-docx` extraction
while building the tool) so the ground truth in `GROUND_TRUTH` is a
faithful, checkable annotation of real content -- not synthetic data.

Run:
    python build_stratified_sample.py
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# Paragraphs copied verbatim from the source document.
EXCERPTS = [
    "KSH INTERNATIONAL LIMITED CORPORATE IDENTITY NUMBER: U28129PN1979PLC141032",
    "11/3, 11/4 and 11/5 Village Birdewadi Chakan Taluka - Khed Pune – 410 501 Maharashtra, India",
    "Contact Person: Sarthak Malvadkar, Company Secretary and Compliance Officer; Telephone: + 91 20 4505 3237;",
    "E-mail: cs.connect@kshinternational.com; Website: www.kshinternational.com",
    "OUR PROMOTERS: KUSHAL SUBBAYYA HEGDE, PUSHPA KUSHAL HEGDE, RAJESH KUSHAL HEGDE, ROHIT KUSHAL HEGDE, RAKHI GIRIJA SHETTY, DHAULAGIRI FAMILY TRUST, EVEREST FAMILY TRUST, MAKALU FAMILY TRUST, BROAD FAMILY TRUST, ANNAPURNA FAMILY TRUST, KANCHENJUNGA FAMILY TRUST AND WATERLOO INDUSTRIAL PARK VI PRIVATE LIMITED",
    "Kushal Subbayya Hegde Chairman and Executive Director 00135070 S. no. 245/ 104, Pushpakamal, Deccan Gymkhana Society, lane no. 3 Prabhat Road, opposite PYC basketball court, Deccan Gymkhana, Pune – 411 004 Maharashtra, India",
    "Rajesh Kushal Hegde Managing Director 00114193 12 Buena Monte, NCL co-operative housing society, Panchvati, Pashan, Pune – 411 008, Maharashtra, India",
    "Ram Kumar Tiwari Independent Director 10938958 A-259, JK Road, Minal Residency, Huzur, Govindpura, Bhopal – 462 023, Madhya Pradesh, India",
    "Indu Jacob Independent Director 05293084 A29, Abhimanshree Society, Pashan Road, Pune – 411 008, Maharashtra, India",
    "Certain of our SMs including, Sandesh Bhagwat, CEO, Amod Joshi, CFO, Sarthak Malvadkar, CS and Compliance Officer, and Ganesh Prasad, Technical Director, are also our KMPs.",
    "Telephone: +91 22 4009 4400 Email: ksh.ipo@nuvama.com, prakash.boricha@nuvama.com, and",
    "Telephone: +91 22 6807 7100 Email: ksh@icicisecurities.com Website: www.icicisecurities.com Investor grievance E-mail: customercare@icicisecurities.com",
    "Telephone: +91 20 6606 4494 Email: hitesh.ramani@citi.com",
    "Telephone: +91-20-26234000 Contact Person: Sharmila Joshi Website: www.indusind.com/ Email: sharmila.joshi@indusind.com",
    "Telephone: + 91 8879770456 Contact Person: Cherag Gyara Website: www.icicibank.com Email: cherag.gyara@icicibank.com",
    "Note: Our top 10 customers include Al-Ahleia Switchgear Co., Bharat Bijlee Limited; CG Power and Industrial Solutions Limited; Emirates Transformer & Switchgear Limited; Georgia Transformer Corporation; Nidec Industrial Automation India Private Limited; Transformers & Rectifiers (India) Limited; and Virginia Transformer Corporation.",
    "The Equity Shares offered through this Red Herring Prospectus are proposed to be listed on the BSE Limited (“BSE”) and National Stock Exchange of India Limited (“NSE”, together with BSE, the “Stock Exchanges”).",
    "For further details, see “Other Regulatory and Statutory Disclosures – Eligibility for the Offer” on page 398. For details of share reservation among Qualified Institutional Buyers, Non-Institutional Investors and Retail Individual Investors, see “Offer Structure” on page 417.",
    "The Offer is being made pursuant to Regulation 6(1) of the Securities and Exchange Board of India (Issue of Capital and Disclosure Requirements) Regulations, 2018 (“SEBI ICDR Regulations”).",
    "Fresh Issue and Offer for Sale Up to [●] Equity Shares of face value of ₹5 each aggregating up to ₹4,200.00 million",
]

GROUND_TRUTH = [
    {"type": "COMPANY", "text": "KSH INTERNATIONAL LIMITED"},
    {"type": "ADDRESS", "text": "11/3, 11/4 and 11/5 Village Birdewadi Chakan Taluka - Khed Pune – 410 501 Maharashtra, India"},
    {"type": "NAME", "text": "Sarthak Malvadkar"},
    {"type": "PHONE", "text": "+ 91 20 4505 3237"},
    {"type": "EMAIL", "text": "cs.connect@kshinternational.com"},
    # NOTE on the phone numbers below: initially omitted from this ground
    # truth by oversight (only the first Telephone: line was annotated),
    # which made the tool look like it had terrible phone precision when
    # actually every one of these is a real phone number it correctly
    # found -- ground truth just hadn't caught up with the excerpt yet.
    # Kept this note because it's a good illustration of why hand-built
    # ground truth needs its own double-checking pass.
    {"type": "PHONE", "text": "+91 22 4009 4400"},
    {"type": "PHONE", "text": "+91 22 6807 7100"},
    {"type": "PHONE", "text": "+91 20 6606 4494"},
    {"type": "PHONE", "text": "+91-20-26234000"},
    {"type": "PHONE", "text": "+ 91 8879770456"},
    {"type": "NAME", "text": "KUSHAL SUBBAYYA HEGDE"},
    {"type": "NAME", "text": "PUSHPA KUSHAL HEGDE"},
    {"type": "NAME", "text": "RAJESH KUSHAL HEGDE"},
    {"type": "NAME", "text": "ROHIT KUSHAL HEGDE"},
    {"type": "NAME", "text": "RAKHI GIRIJA SHETTY"},
    {"type": "COMPANY", "text": "WATERLOO INDUSTRIAL PARK VI PRIVATE LIMITED"},
    {"type": "NAME", "text": "Kushal Subbayya Hegde"},
    {"type": "ADDRESS", "text": "S. no. 245/ 104, Pushpakamal, Deccan Gymkhana Society, lane no. 3 Prabhat Road, opposite PYC basketball court, Deccan Gymkhana, Pune – 411 004 Maharashtra, India"},
    {"type": "NAME", "text": "Rajesh Kushal Hegde"},
    {"type": "ADDRESS", "text": "12 Buena Monte, NCL co-operative housing society, Panchvati, Pashan, Pune – 411 008, Maharashtra, India"},
    {"type": "NAME", "text": "Ram Kumar Tiwari"},
    {"type": "ADDRESS", "text": "A-259, JK Road, Minal Residency, Huzur, Govindpura, Bhopal – 462 023, Madhya Pradesh, India"},
    {"type": "NAME", "text": "Indu Jacob"},
    {"type": "ADDRESS", "text": "A29, Abhimanshree Society, Pashan Road, Pune – 411 008, Maharashtra, India"},
    {"type": "NAME", "text": "Sandesh Bhagwat"},
    {"type": "NAME", "text": "Amod Joshi"},
    {"type": "NAME", "text": "Sarthak Malvadkar"},
    {"type": "NAME", "text": "Ganesh Prasad"},
    {"type": "EMAIL", "text": "ksh.ipo@nuvama.com"},
    {"type": "EMAIL", "text": "prakash.boricha@nuvama.com"},
    {"type": "EMAIL", "text": "ksh@icicisecurities.com"},
    {"type": "EMAIL", "text": "customercare@icicisecurities.com"},
    {"type": "EMAIL", "text": "hitesh.ramani@citi.com"},
    {"type": "NAME", "text": "Sharmila Joshi"},
    {"type": "EMAIL", "text": "sharmila.joshi@indusind.com"},
    {"type": "NAME", "text": "Cherag Gyara"},
    {"type": "EMAIL", "text": "cherag.gyara@icicibank.com"},
    {"type": "COMPANY", "text": "CG Power and Industrial Solutions Limited"},
    {"type": "COMPANY", "text": "Bharat Bijlee Limited"},
    {"type": "COMPANY", "text": "Emirates Transformer & Switchgear Limited"},
    {"type": "COMPANY", "text": "Georgia Transformer Corporation"},
    {"type": "COMPANY", "text": "Nidec Industrial Automation India Private Limited"},
    {"type": "COMPANY", "text": "Transformers & Rectifiers (India) Limited"},
    {"type": "COMPANY", "text": "Virginia Transformer Corporation"},
    {"type": "COMPANY", "text": "BSE Limited"},
]


if __name__ == "__main__":
    txt_path = os.path.join(HERE, "stratified_excerpt.txt")
    gt_path = os.path.join(HERE, "stratified_ground_truth.json")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(EXCERPTS))
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(GROUND_TRUTH, f, indent=2, ensure_ascii=False)
    print(f"Wrote {txt_path} ({len(EXCERPTS)} paragraphs)")
    print(f"Wrote {gt_path} ({len(GROUND_TRUTH)} PII instances)")
