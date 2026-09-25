import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from pii_redactor import EntityType
from pii_redactor.detector import PIIDetector
from pii_redactor.image_engine import ImageRedactor
from pii_redactor.pseudonymizer import Pseudonymizer

pytestmark = pytest.mark.skipif(not ImageRedactor.available(), reason="tesseract not installed")


class _Part:
    partname = "/word/media/test.png"

    def __init__(self, blob):
        self._blob = blob

    @property
    def blob(self):
        return self._blob


def test_pan_card_is_redacted_consistently():
    img = Image.new("RGB", (1000, 500), "white")
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
    for y, t in [(20, "INCOME TAX DEPARTMENT"), (90, "NBWPS1951N"), (160, "Name"), (210, "VISHAL SINGH"),
                 (280, "Date of Birth"), (330, "06/05/2000")]:
        d.text((40, y), t, font=f, fill="black")
    b = io.BytesIO(); img.save(b, "PNG")
    ps = Pseudonymizer()
    ps.register("Vishal Singh", EntityType.PERSON)
    part = _Part(b.getvalue())
    rep = ImageRedactor(PIIDetector(), ps).process_part(part)
    kinds = {h["type"] for h in rep.hits}
    assert {"PAN", "PERSON", "DOB"} <= kinds
    fake = ps.fake_for("Vishal Singh", EntityType.PERSON).upper()
    assert any(h["pseudonym"].upper() == fake for h in rep.hits if h["type"] == "PERSON")


def _id_card(portrait: bool) -> bytes:
    img = Image.new("RGB", (1000, 600), "white")
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
    d.text((40, 20), "INCOME TAX DEPARTMENT", font=f, fill="black")
    d.text((300, 90), "Permanent Account Number Card", font=f, fill="black")
    d.text((300, 150), "NBWPS1951N", font=f, fill="black")
    if portrait:
        d.rectangle((50, 80, 250, 330), fill=(200, 150, 120))
    d.text((40, 360), "Name", font=f, fill="black")
    d.text((40, 410), "VISHAL SINGH", font=f, fill="black")
    d.text((40, 470), "Date of Birth", font=f, fill="black")
    d.text((40, 520), "06/05/2000", font=f, fill="black")
    b = io.BytesIO(); img.save(b, "PNG")
    return b.getvalue()


def test_pan_photo_masked_by_layout_when_no_face_found():
    part = _Part(_id_card(portrait=True))
    red = ImageRedactor(PIIDetector(), Pseudonymizer(), policy="mask")
    red._find_faces = lambda arr, words: []  # simulate an undetectable face
    rep = red.process_part(part)
    assert rep.id_document and [p["rule"] for p in rep.photo_regions] == ["pan_layout"]
    out = Image.open(io.BytesIO(part.blob)).convert("RGB")
    assert out.getpixel((150, 200)) == (0, 0, 0)  # centre of the photo frame is blacked out
