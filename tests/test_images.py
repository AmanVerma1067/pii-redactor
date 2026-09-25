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
