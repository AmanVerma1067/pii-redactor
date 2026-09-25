"""Builds the annotated RHP-style benchmark (.docx + ground_truth.json).

The document reproduces the structures and entities listed for the KSH International RHP
(promoter names, CIN, DINs, SEBI numbers, addresses, contacts, scanned PAN/Aadhaar images) plus
deliberate hard cases and false-positive traps. Values not given in the brief are synthetic.
Every PII value is annotated at the moment it is written, so the ground truth cannot drift.

    python eval/build_benchmark.py --out eval/data
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import segno
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt
from PIL import Image, ImageDraw, ImageFont

GT: list[dict] = []
NEG: list[str] = []
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


# Typical RHP boilerplate full of capitalised defined terms, numbers and dates: must survive verbatim.
FP_STRESS = [
    "Anchor Investor Bid/Offer Period means one Working Day prior to the Bid/Offer Opening Date.",
    "The Selling Shareholders, severally and not jointly, confirm that the Offered Shares are eligible for the Offer for Sale.",
    "ASBA Bidders must provide the details of their ASBA Account in the Bid cum Application Form.",
    "The Designated Stock Exchange for the purpose of the Offer is NSE.",
    "Qualified Institutional Buyers, Non-Institutional Investors and Retail Individual Investors may participate in the Offer.",
    "Our Board of Directors approved the Offer pursuant to a resolution dated July 15, 2025.",
    "The Registrar to the Offer shall ensure that refunds are credited within two Working Days.",
    "Restated Consolidated Financial Information for Fiscals 2025, 2024 and 2023 has been prepared under Ind AS.",
    "Key Managerial Personnel and Senior Management Personnel are disclosed in Our Management on page 231.",
    "Capital expenditure of ₹ 1,234.56 million is proposed for the Supa Facility and the Chakan Facility.",
    "Earnings per Equity Share (Basic and Diluted) for Fiscal 2025 was ₹ 12.34.",
    "Return on Net Worth was 18.52% and EBITDA Margin was 11.20% in Fiscal 2025.",
    "Helpline timings are 10:00 a.m. to 5:00 p.m. IST on all Working Days.",
    "The Offer is being made through the Book Building Process in terms of Rule 19(2)(b) of the SCRR read with Regulation 31 of the SEBI ICDR Regulations.",
    "The magnet winding wire market in India is expected to grow at a CAGR of 12-13% between Fiscal 2025 and Fiscal 2030 as per the Industry Report.",
    "Our manufacturing facilities are spread over approximately 2,43,000 square meters.",
    "The Company Secretary and Compliance Officer is responsible for redressal of investor grievances.",
    "The Draft Red Herring Prospectus dated March 31, 2025 was filed with SEBI.",
    "Minimum Promoters' Contribution shall be locked-in for a period of 18 months from the date of Allotment.",
    "Wilful Defaulter or Fraudulent Borrower has the meaning ascribed to it under the SEBI ICDR Regulations.",
    "UPI Bidders may bid using the UPI Mechanism for an application value of up to ₹ 5,00,000.",
    "Annual return in Form No. MGT-7 has been filed under Section 92 of the Companies Act, 2013.",
    "The ERP system was upgraded to version 2.1.4.0 during Fiscal 2024.",
    "Holding Company, Material Subsidiary and Group Company have the meanings given in the SEBI ICDR Regulations.",
    "The Hon'ble Supreme Court of India and the High Court of Bombay have not passed any adverse order.",
    "Our order book as of June 30, 2025 was ₹ 9,876.54 million across 1,245 customers in 27 countries.",
]


def E(value: str, etype: str, where: str = "text", detect: bool = True, note: str = "") -> str:
    """Annotate a PII value (deduplicated case-insensitively) and return it for writing."""
    for g in GT:
        if g["value"].lower() == value.lower() and g["type"] == etype:
            if where not in g["where"]:
                g["where"].append(where)
            return value
    GT.append({"value": value, "type": etype, "where": [where], "detect": detect, "note": note})
    return value


def N(value: str) -> str:
    NEG.append(value)
    return value


def add_hyperlink(paragraph, url: str, pieces: list[str]):
    r_id = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    hl = OxmlElement("w:hyperlink")
    hl.set(qn("r:id"), r_id)
    for i, text in enumerate(pieces):  # deliberately split the visible text across runs
        r = OxmlElement("w:r")
        rpr = OxmlElement("w:rPr")
        u = OxmlElement("w:u")
        u.set(qn("w:val"), "single")
        rpr.append(u)
        if i == 1:
            rpr.append(OxmlElement("w:b"))
        r.append(rpr)
        t = OxmlElement("w:t")
        t.text = text
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        r.append(t)
        hl.append(r)
    paragraph._p.append(hl)


def id_card(kind: str, path: Path) -> None:
    f = lambda s, b=False: ImageFont.truetype(FONT_B if b else FONT, s)  # noqa: E731
    if kind == "pan":
        img = Image.new("RGB", (1000, 620), (214, 232, 247))
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, 1000, 90), fill=(40, 90, 160))
        d.text((30, 25), "INCOME TAX DEPARTMENT", font=f(34, True), fill="white")
        d.text((640, 25), "GOVT. OF INDIA", font=f(34, True), fill="white")
        d.text((330, 110), "Permanent Account Number Card", font=f(28, True), fill=(20, 20, 20))
        d.text((380, 160), E("NBWPS1951N", "PAN", "image"), font=f(40, True), fill=(10, 10, 10))
        d.rectangle((40, 150, 250, 400), outline=(90, 90, 90), width=3)
        d.text((95, 260), "PHOTO", font=f(30), fill=(120, 120, 120))
        d.text((300, 240), "Name", font=f(24), fill=(60, 60, 60))
        d.text((300, 275), E("VISHAL SINGH", "PERSON", "image"), font=f(34, True), fill=(10, 10, 10))
        d.text((300, 335), "Father's Name", font=f(24), fill=(60, 60, 60))
        d.text((300, 370), E("SUGRIV SINGH", "PERSON", "image"), font=f(34, True), fill=(10, 10, 10))
        d.text((300, 430), "Date of Birth", font=f(24), fill=(60, 60, 60))
        d.text((300, 465), E("06/05/2000", "DOB", "image"), font=f(34, True), fill=(10, 10, 10))
        d.text((700, 540), "Signature", font=f(22), fill=(60, 60, 60))
    else:
        img = Image.new("RGB", (1100, 700), (255, 255, 255))
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, 1100, 80), fill=(255, 153, 51))
        d.text((380, 20), "Government of India", font=f(36, True), fill=(10, 10, 10))
        d.rectangle((40, 110, 250, 360), outline=(90, 90, 90), width=3)
        d.text((95, 220), "PHOTO", font=f(30), fill=(120, 120, 120))
        d.text((290, 120), E("Meraj Khan", "PERSON", "image"), font=f(34, True), fill=(10, 10, 10))
        d.text((290, 175), "DOB: " + E("12/12/1988", "DOB", "image"), font=f(30), fill=(10, 10, 10))
        d.text((290, 225), "MALE", font=f(30), fill=(10, 10, 10))
        d.text((290, 300), E("2943 6593 3461", "AADHAAR", "image"), font=f(46, True), fill=(10, 10, 10))
        d.text((40, 420), "Address: S/O " + E("Sudhdan Khan", "PERSON", "image") + ", saray dan shah,", font=f(28), fill=(10, 10, 10))
        d.text((40, 465), "Katrauli, Poore Durgi, Phoolpur,", font=f(28), fill=(10, 10, 10))
        d.text((40, 510), "Allahabad, UP 212402", font=f(28), fill=(10, 10, 10))
        E("saray dan shah, Katrauli, Poore Durgi, Phoolpur, Allahabad, UP 212402", "ADDRESS", "image")
        qr = segno.make("Meraj Khan|12/12/1988|294365933461|Allahabad 212402", error="m")
        qpath = path.with_suffix(".qr.png")
        qr.save(qpath, scale=7, border=2)
        q = Image.open(qpath).convert("RGB")
        img.paste(q, (1100 - q.width - 40, 110))
        qpath.unlink()
        d.text((330, 640), "Mera Aadhaar, Meri Pehchan", font=f(26, True), fill=(200, 30, 30))
    img.save(path)


def build(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(10.5)

    sec = doc.sections[0]
    sec.header.paragraphs[0].text = E("KSH International Limited", "ORG", "header") + " | Red Herring Prospectus"
    sec.footer.paragraphs[0].text = "CIN: " + E("U28129PN1979PLC141032", "CIN", "footer")

    doc.add_heading("RED HERRING PROSPECTUS", 0)
    doc.add_paragraph("Dated " + N("September 10, 2025") + " | 100% Book Built Offer")
    p = doc.add_paragraph()
    r = p.add_run(E("KSH INTERNATIONAL LIMITED", "ORG"))
    r.bold, r.font.size = True, Pt(20)
    doc.add_paragraph("Corporate Identity Number: " + E("U28129PN1979PLC141032", "CIN"))
    doc.add_paragraph("Registered Office: " + E("11/3, 11/4 and 11/5, Village Birdewadi, Chakan Industrial Area, Phase II, "
                      "Chakan, Taluka Khed, Pune 410 501, Maharashtra, India", "ADDRESS"))
    doc.add_paragraph("Corporate Office: " + E("Plot No. T-9, MIDC Taloja Industrial Area, Taloja, Raigad 410 208, "
                      "Maharashtra, India", "ADDRESS"))
    doc.add_paragraph("Contact Person: Ms. " + E("Anjali Kulkarni", "PERSON") + ", Company Secretary and Compliance Officer")
    p = doc.add_paragraph("Telephone: " + E("+91 20 45053237", "PHONE") + " | E-mail: ")
    email = E("cs.connect@kshinternational.com", "EMAIL")
    add_hyperlink(p, "mailto:" + email, ["cs.connect@", "kshinternational", ".com"])
    p.add_run(" | Website: " + E("www.kshinternational.com", "URL"))
    doc.add_paragraph("OUR PROMOTERS: " + E("KUSHAL SUBBAYYA HEGDE", "PERSON") + ", " + E("PUSHPA KUSHAL HEGDE", "PERSON")
                      + ", " + E("RAJESH KUSHAL HEGDE", "PERSON") + " AND " + E("ROHIT KUSHAL HEGDE", "PERSON"))

    doc.add_heading("OUR PROMOTERS AND PROMOTER GROUP", 1)
    p = doc.add_paragraph()
    p.add_run("Mr. ")
    r = p.add_run("Kus"); r.bold = True
    r = p.add_run("hal Subbayya "); r.italic = True
    p.add_run("Hegde")
    p.add_run(" is the Chairman and Managing Director of our Company and holds DIN " + E("00135070", "DIN") + ".")
    doc.add_paragraph(E("Rakhi Girija Shetty", "PERSON") + ", one of our Promoters, is the daughter of Mr. Kushal Subbayya Hegde.")
    doc.add_paragraph("Mr. " + E("Hegde", "PERSON", detect=False, note="surname-only back-reference") +
                      " has over four decades of experience in the electrical wires industry.")

    rows = [("Kushal Subbayya Hegde", "Chairman and Managing Director", "00135070", "AAEPH4521K", "14/02/1951"),
            ("Pushpa Kushal Hegde", "Whole-time Director", "00114193", "AAFPH7832M", "22/08/1955"),
            ("Rajesh Kushal Hegde", "Whole-time Director", "00134926", "ABCPH1298Q", "03/11/1978"),
            ("Rohit Kushal Hegde", "Whole-time Director", "03124510", "ABDPH5567R", "19/06/1982"),
            ("Rakhi Girija Shetty", "Non-Executive Director", "07891234", "AXKPS3321L", "09/01/1980")]
    t = doc.add_table(rows=1, cols=5)
    t.style = "Table Grid"
    for c, h in zip(t.rows[0].cells, ["Name", "Designation", "DIN", "PAN", "Date of Birth"]):
        c.text = h
    for name, des, din, pan, dob in rows:
        cells = t.add_row().cells
        cells[0].text, cells[1].text = E(name, "PERSON", "table"), des
        cells[2].text, cells[3].text, cells[4].text = E(din, "DIN", "table"), E(pan, "PAN", "table"), E(dob, "DOB", "table")

    # tracked deletion + comment (authors are personal data too)
    p = doc.add_paragraph("Promoter group members were confirmed by the Board. ")
    p._p.append(parse_xml(f'<w:del {nsdecls("w")} w:id="901" w:author="Pushpa Hegde" w:date="2025-09-01T10:00:00Z">'
                          f'<w:r><w:delText>Previously listed: {E("Pushpa Kushal Hegde", "PERSON", "tracked-change")}</w:delText></w:r></w:del>'))
    try:
        run = doc.add_paragraph("Review of promoter shareholding.").runs[0]
        doc.add_comment(run, text="Verify with the secretarial team", author=E("Rohit Hegde", "PERSON", "comment-author", detect=False), initials="RH")
    except Exception:
        pass

    doc.add_heading("BOOK RUNNING LEAD MANAGERS AND REGISTRAR", 1)
    t = doc.add_table(rows=1, cols=4)
    t.style = "Table Grid"
    for c, h in zip(t.rows[0].cells, ["Book Running Lead Manager / Registrar", "Address", "Contact", "SEBI Registration No."]):
        c.text = h
    brlm = [("Nuvama Wealth Management Limited", "801-804, Wing A, Building No. 3, Inspire BKC, G Block, Bandra Kurla Complex, Bandra East, Mumbai 400 051, Maharashtra, India",
             "+91 22 4009 4400", "ksh.ipo@nuvama.com", "Manish Tejwani", "INM000013004"),
            ("ICICI Securities Limited", "ICICI Venture House, Appasaheb Marathe Marg, Prabhadevi, Mumbai 400 025, Maharashtra, India",
             "+91 22 6807 7100", "ksh.ipo@icicisecurities.com", "Rupesh Khant", "INM000011179"),
            ("MUFG Intime India Private Limited", "C-101, 1st Floor, 247 Park, L.B.S. Marg, Vikhroli (West), Mumbai 400 083, Maharashtra, India",
             "+91 81081 14949", "kshinternational.ipo@in.mpms.mufg.com", "Shanti Gopalkrishnan", "INR000004058")]
    for org, addr, tel, mail, person, sebi in brlm:
        c = t.add_row().cells
        c[0].text = E(org, "ORG", "table")
        if org.startswith("MUFG"):
            c[0].text += " (formerly " + E("Link Intime India Private Limited", "ORG", "table") + ")"
        c[1].text = E(addr, "ADDRESS", "table")
        c[2].text = f"Tel: {E(tel, 'PHONE', 'table')}\nE-mail: {E(mail, 'EMAIL', 'table')}\nContact Person: " + \
                    ("Ms. " if person.startswith("Shanti") else "Mr. ") + E(person, "PERSON", "table")
        c[3].text = E(sebi, "SEBI_REG", "table")

    doc.add_heading("OTHER DISCLOSURES", 1)
    doc.add_paragraph("Escrow Collection Bank: " + E("Axis Bank Limited", "ORG") + ", Account No. " + E("912020045678123", "BANK_ACCOUNT")
                      + ", IFSC: " + E("UTIB0000123", "IFSC") + ".")
    doc.add_paragraph("GSTIN of our Company: " + E("27AAACK1234F1Z5", "GSTIN") + ".")
    doc.add_paragraph("The SEBI filing fee was paid using corporate card " + E("4111 1111 1111 1111", "CREDIT_CARD") + ".")
    doc.add_paragraph("Virtual data room logs show logins from IP address " + E("203.0.113.77", "IP_ADDRESS") + " and "
                      + E("10.24.8.199", "IP_ADDRESS") + ".")
    doc.add_paragraph("One overseas selling shareholder furnished US SSN " + E("123-45-6789", "SSN") + " in Form W-9.")
    doc.add_paragraph("Mr. Rohit Kushal Hegde (born on " + E("19 June 1982", "DOB") + ") holds Indian passport number "
                      + E("Z4829173", "PASSPORT") + ".")
    doc.add_paragraph("For investor grievances, write to " + E("Rashi Patil", "PERSON") + " at " + E("rashhi.patil@gmail.com", "EMAIL")
                      + " or call " + E("+91 98765 43210", "PHONE") + ".")
    doc.add_paragraph("Statutory Auditor: " + E("M S K A & Associates", "ORG") + ", Chartered Accountants.")
    # hard cases (expected to be difficult for rule-based detection)
    doc.add_paragraph("Peer comparison excludes " + E("Kotak Mahindra Capital Company", "ORG", note="no legal suffix") + " for want of data.")
    doc.add_paragraph("The draft was reviewed by " + E("rakhi shetty", "PERSON", note="lower-case name") + " on behalf of the Board.")
    doc.add_paragraph("Site visits were coordinated by " + E("Subbayya Gowda", "PERSON", note="no honorific, not in gazetteer") + " of the plant team.")

    doc.add_heading("RISK FACTORS", 1)
    doc.add_paragraph(
        f"The Equity Shares are proposed to be listed on {N('BSE Limited')} and {N('National Stock Exchange of India Limited')}. "
        f"This Red Herring Prospectus is filed under the {N('SEBI ICDR Regulations')} and the {N('Companies Act, 2013')} with the "
        f"{N('Registrar of Companies')}, Maharashtra at Pune. ISIN: {N('INE0ABC01018')}. The Offer comprises up to "
        f"{N('1,84,89,583')} Equity Shares of face value of ₹5 each aggregating up to {N('₹7,100.00 million')}. "
        f"The {N('Price Band')} is ₹365 to ₹384 per Equity Share. Bid/Offer Opening Date: {N('September 16, 2025')}. "
        f"Our Company was incorporated on {N('February 13, 1979')}. See {N('Section 2(76)')} of the Companies Act, 2013 and the "
        f"master directions of the {N('Reserve Bank of India')}. Revenue from operations grew by {N('18.45%')} to "
        f"₹ {N('4,012.37')} million in Fiscal 2025 (page {N('245')}).")

    doc.add_heading("DEFINITIONS AND ABBREVIATIONS (false-positive stress test)", 1)
    for sent in FP_STRESS:
        doc.add_paragraph(N(sent))

    doc.add_heading("ANNEXURE: KYC DOCUMENTS OF A SELLING SHAREHOLDER'S NOMINEE", 1)
    for kind in ("pan", "aadhaar"):
        path = out / f"{kind}_mock.png"
        id_card(kind, path)
        doc.add_picture(str(path), width=Inches(4.5))
        path.unlink()

    doc.save(out / "benchmark_rhp.docx")
    (out / "ground_truth.json").write_text(json.dumps({"entities": GT, "negatives": NEG}, indent=2, ensure_ascii=False))
    print(f"wrote {out/'benchmark_rhp.docx'}: {len(GT)} annotated entities, {len(NEG)} negative traps")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "data")
    build(ap.parse_args().out)
