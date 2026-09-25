"""Embedded-image PII: extract media parts -> OCR (Tesseract) -> detect -> in-place redaction.

Scanned ID cards (PAN / Aadhaar) are the critical edge case: plain text extraction never sees them.
For every image part inside the .docx package we:
  1. pre-process (grayscale, upscale small scans) and OCR with word-level boxes;
  2. run the SAME detector used for text, plus ID-card layout rules
     ("Name" / "Father's Name" / "DOB" labels whose value sits on the next line, ALL-CAPS name lines,
     "Address:" blocks up to the PIN code);
  3. register hits in the SAME global pseudonymizer, so "VISHAL SINGH" on the card and in the text
     receive the same fake;
  4. paint over each hit: `replace` (background-matched box + fake text), `mask` (black box) or `blur`;
  5. optionally pixelate QR codes (Aadhaar QR encodes the holder's data) and the holder's photo
     (Haar face detection, widened to the portrait frame; ID-layout fallback when no face is found);
  6. fail-safe: an image that looks like an ID card but yields no OCR hits is blurred entirely.
The image is re-encoded in its original format (which also strips EXIF/GPS metadata).
"""
from __future__ import annotations

import io
import logging
import os
import re
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .entities import EntityType as T, Span

log = logging.getLogger(__name__)

try:
    import pytesseract
    from pytesseract import Output
except Exception:  # pragma: no cover
    pytesseract = None

try:
    import cv2
    import numpy as np
except Exception:  # pragma: no cover
    cv2 = None
    np = None

ID_KEYWORDS = ("income tax", "permanent account", "govt", "government of india", "aadhaar", "aadhar",
               "unique identification", "date of birth", "dob", "father", "enrolment", "vid", "male",
               "female", "passport", "election commission", "driving licence", "आधार")
ID_BOILERPLATE = set("""income tax department govt government of india permanent account number card signature
unique identification authority male female dob address aadhaar aadhar mera pehchan help enrolment no vid
issue date year birth name father's fathers father to www uidai gov in the republic my identity""".split())
LABEL_RE = re.compile(r"(?i)\b(father'?s?\s*name|mother'?s?\s*name|husband'?s?\s*name|name|s\s*/\s*o|d\s*/\s*o|w\s*/\s*o|c\s*/\s*o)\b\s*[:\-.]?\s*")
ADDR_LABEL_RE = re.compile(r"(?i)\baddress\b\s*[:\-.]?\s*")
PORTRAIT_BLOCK_RE = re.compile(r"(?i)\b(father|mother|husband|dob|date\s+of\s+birth|year\s+of\s+birth|male|female)\b")
PIN_RE = re.compile(r"(?<!\d)[1-9]\d{2}\s?\d{3}(?!\d)")
REL_RE = re.compile(r"(?i)^(?:s|d|w|c)\s*/\s*o\s*[:.]?\s*([A-Za-z][A-Za-z.'\-]*(?:\s+[A-Za-z][A-Za-z.'\-]*){0,3})\s*,")
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf", "/Library/Fonts/Arial Bold.ttf",
]


@dataclass
class Word:
    text: str
    box: tuple[int, int, int, int]  # left, top, right, bottom (original image coords)
    conf: float


@dataclass
class Line:
    words: list[Word]
    text: str = ""
    offsets: list[tuple[int, int]] = field(default_factory=list)

    def build(self) -> "Line":
        parts, pos = [], 0
        for w in self.words:
            self.offsets.append((pos, pos + len(w.text)))
            parts.append(w.text)
            pos += len(w.text) + 1
        self.text = " ".join(parts)
        return self


@dataclass
class ImageHit:
    line: int
    start: int
    end: int
    type: T
    text: str
    source: str


@dataclass
class ImageReport:
    part: str
    size: tuple[int, int]
    id_document: bool = False
    ocr_words: int = 0
    hits: list[dict] = field(default_factory=list)
    faces: int = 0
    photo_regions: list[dict] = field(default_factory=list)
    qr_codes: int = 0
    failsafe_blur: bool = False
    skipped: str | None = None


def _font(size: int):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


class ImageRedactor:
    def __init__(self, detector, pseudo, policy: str = "replace", lang: str = "eng", min_side: int = 120,
                 mask_qr: bool = True, blur_faces: bool = True, failsafe: bool = True):
        self.detector, self.pseudo = detector, pseudo
        self.policy, self.lang, self.min_side = policy, lang, min_side
        self.mask_qr, self.blur_faces, self.failsafe = mask_qr, blur_faces, failsafe

    @staticmethod
    def available() -> bool:
        if pytesseract is None:
            return False
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------ OCR
    def ocr(self, img: Image.Image) -> list[Line]:
        scale = 2.0 if max(img.size) < 1600 else 1.0
        g = img.convert("L")
        if scale != 1.0:
            g = g.resize((int(g.width * scale), int(g.height * scale)), Image.LANCZOS)
        lines = self._ocr_pass(g, scale, "--oem 3 --psm 3")
        if sum(len(l.words) for l in lines) < 6:
            lines = self._ocr_pass(g, scale, "--oem 3 --psm 11")
        return lines

    def _ocr_pass(self, g: Image.Image, scale: float, config: str) -> list[Line]:
        d = pytesseract.image_to_data(g, lang=self.lang, config=config, output_type=Output.DICT)
        groups: dict[tuple, list[Word]] = {}
        for i, txt in enumerate(d["text"]):
            txt = (txt or "").strip()
            if not txt or float(d["conf"][i]) < 0:
                continue
            l, t, w, h = (d[k][i] for k in ("left", "top", "width", "height"))
            box = (int(l / scale), int(t / scale), int((l + w) / scale), int((t + h) / scale))
            key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
            groups.setdefault(key, []).append(Word(txt, box, float(d["conf"][i])))
        lines = [Line(sorted(ws, key=lambda w: w.box[0])).build() for ws in groups.values()]
        return sorted(lines, key=lambda l: (min(w.box[1] for w in l.words), min(w.box[0] for w in l.words)))

    # ------------------------------------------------------------------ detection
    def detect(self, lines: list[Line]) -> tuple[list[ImageHit], bool]:
        full = "\n".join(l.text for l in lines).lower()
        id_ctx = sum(k in full for k in ID_KEYWORDS) >= 2
        hits: list[ImageHit] = []
        for i, line in enumerate(lines):
            for sp in self.detector.detect(line.text, id_context=id_ctx):
                hits.append(ImageHit(i, sp.start, sp.end, sp.type, sp.text, sp.source))
        if id_ctx:
            hits += self._id_rules(lines)
        return self._dedupe(hits), id_ctx

    def _id_rules(self, lines: list[Line]) -> list[ImageHit]:
        out: list[ImageHit] = []
        for i, line in enumerate(lines):
            txt = line.text
            m = LABEL_RE.search(txt)
            if m:
                rest = txt[m.end():].split(",")[0].strip(" :-.")
                if len(re.sub(r"[^A-Za-z]", "", rest)) >= 3:
                    s = txt.index(rest, m.end())
                    out.append(ImageHit(i, s, s + len(rest), T.PERSON, rest, "id_label_inline"))
                elif i + 1 < len(lines) and self._namelike(lines[i + 1].text):
                    nxt = lines[i + 1].text
                    out.append(ImageHit(i + 1, 0, len(nxt), T.PERSON, nxt, "id_label_nextline"))
            a = ADDR_LABEL_RE.search(txt)
            if a:
                j, first = i, True
                while j < len(lines) and j <= i + 6:
                    lt = lines[j].text
                    s = a.end() if first else 0
                    seg = lt[s:].strip()
                    rel = REL_RE.match(seg) if first else None
                    if rel:  # "Address: S/O Sudhdan Khan, saray dan shah" -> PERSON + ADDRESS
                        ps = lt.index(seg, s) + rel.start(1)
                        out.append(ImageHit(j, ps, ps + len(rel.group(1)), T.PERSON, rel.group(1), "id_relation"))
                        s = ps + len(rel.group(1))
                        seg = lt[s:].strip(" ,")
                    if seg:
                        s = lt.index(seg, s)
                        out.append(ImageHit(j, s, s + len(seg), T.ADDRESS, seg, "id_address_block"))
                    first = False
                    if PIN_RE.search(lt):
                        break
                    j += 1
            if self._namelike(txt) and txt.isupper():
                out.append(ImageHit(i, 0, len(txt), T.PERSON, txt, "id_caps_line"))
        return out

    @staticmethod
    def _namelike(text: str) -> bool:
        toks = text.split()
        if not 2 <= len(toks) <= 4:
            return False
        if not all(re.fullmatch(r"[A-Za-z][A-Za-z.'\-]*", t) for t in toks):
            return False
        return not any(t.lower().strip(".'") in ID_BOILERPLATE for t in toks)

    @staticmethod
    def _dedupe(hits: list[ImageHit]) -> list[ImageHit]:
        pri = {"id_label_inline": 3, "id_label_nextline": 3, "id_relation": 3, "id_address_block": 2}
        hits = sorted(hits, key=lambda h: (-(h.end - h.start), -pri.get(h.source, 1)))
        kept: list[ImageHit] = []
        for h in hits:
            if not any(k.line == h.line and h.start < k.end and k.start < h.end for k in kept):
                kept.append(h)
        return kept

    # ------------------------------------------------------------------ rendering
    def _boxes_for(self, line: Line, hit: ImageHit) -> tuple[int, int, int, int] | None:
        idx = [k for k, (a, b) in enumerate(line.offsets) if a < hit.end and hit.start < b]
        if not idx:
            return None
        bs = [line.words[k].box for k in idx]
        return (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))

    @staticmethod
    def _bg_fg(img: Image.Image, box) -> tuple[tuple, tuple]:
        l, t, r, b = box
        pad = 3
        crop = img.crop((max(0, l - pad), max(0, t - pad), min(img.width, r + pad), min(img.height, b + pad))).convert("RGB")
        px = list(crop.get_flattened_data() if hasattr(crop, "get_flattened_data") else crop.getdata())
        w, h = crop.size
        border = [px[y * w + x] for y in range(h) for x in range(w) if x in (0, w - 1) or y in (0, h - 1)]
        med = lambda seq, c: sorted(p[c] for p in seq)[len(seq) // 2]  # noqa: E731
        bg = tuple(med(border, c) for c in range(3))
        dark = sorted(px, key=lambda p: sum(p))[: max(1, len(px) // 10)]
        fg = tuple(med(dark, c) for c in range(3))
        return bg, fg

    def _paint(self, img: Image.Image, box, fake: str) -> None:
        l, t, r, b = box
        if self.policy == "blur":
            region = img.crop(box).filter(ImageFilter.GaussianBlur(radius=max(4, (b - t) // 2)))
            img.paste(region, box)
            return
        draw = ImageDraw.Draw(img)
        if self.policy == "mask":
            draw.rectangle((l - 2, t - 2, r + 2, b + 2), fill=(0, 0, 0))
            return
        bg, fg = self._bg_fg(img, box)
        draw.rectangle((l - 2, t - 2, r + 2, b + 2), fill=bg)
        size = max(8, int((b - t) * 1.05))
        font = _font(size)
        while size > 8 and draw.textlength(fake, font=font) > (r - l) * 1.35:
            size -= 1
            font = _font(size)
        draw.text((l, t + (b - t) / 2), fake, fill=fg, font=font, anchor="lm")

    @staticmethod
    def _pixelate(img: Image.Image, box, block: int = 16) -> None:
        region = img.crop(box)
        small = region.resize((max(1, region.width // block), max(1, region.height // block)), Image.NEAREST)
        img.paste(small.resize(region.size, Image.NEAREST).filter(ImageFilter.GaussianBlur(6)), box)

    def _obscure(self, img: Image.Image, box) -> None:
        """Photos / QR codes cannot be 'replaced' with fake text: black box for `mask`, else pixelate."""
        if self.policy == "mask":
            ImageDraw.Draw(img).rectangle(box, fill=(0, 0, 0))
        else:
            self._pixelate(img, box)

    @staticmethod
    def _text_cover(box, words: list[Word]) -> float:
        l, t, r, b = box
        area = max(1, (r - l) * (b - t))
        cov = sum(max(0, min(r, w.box[2]) - max(l, w.box[0])) * max(0, min(b, w.box[3]) - max(t, w.box[1]))
                  for w in words)
        return cov / area

    def _find_qr(self, arr, words: list[Word], id_doc: bool) -> list[tuple[int, int, int, int]]:
        h, w = arr.shape[:2]
        try:
            ok, pts = cv2.QRCodeDetector().detect(arr)
        except Exception as exc:  # pragma: no cover
            log.debug("QR detection failed: %s", exc)
            ok, pts = False, None
        if ok and pts is not None:
            xs, ys = pts[0][:, 0], pts[0][:, 1]
            return [(int(max(0, xs.min() - 8)), int(max(0, ys.min() - 8)),
                     int(min(w, xs.max() + 8)), int(min(h, ys.max() + 8)))]
        if not id_doc:
            return []
        # Photographed cards are often too blurred for the decoder: fall back to a dense, square,
        # solidly-filled high-edge-density block that is not OCR text.
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
        k = max(9, min(h, w) // 40)
        dens = cv2.blur((cv2.Canny(gray, 60, 160) > 0).astype(np.float32), (k, k))
        m = cv2.morphologyEx(((dens > 0.22) * 255).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
        out = []
        for c in cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
            x, y, bw, bh = cv2.boundingRect(c)
            box = (max(0, x - 4), max(0, y - 4), min(w, x + bw + 4), min(h, y + bh + 4))
            if (bw * bh >= 0.01 * w * h and 0.8 <= bw / bh <= 1.25 and cv2.contourArea(c) / (bw * bh) >= 0.85
                    and self._text_cover(box, words) < 0.15):
                # edge density can bleed into an adjacent text line: stop the box above/below it
                # (only words in the outer 20% bands: OCR noise inside the code itself is ignored)
                top, bot = box[1] + 0.2 * (box[3] - box[1]), box[1] + 0.8 * (box[3] - box[1])
                for wd in words:
                    wl, wt, wr, wb = wd.box
                    if wr > box[0] and wl < box[2] and wb > box[1] and wt < box[3]:
                        cy = (wt + wb) / 2
                        if cy > bot:
                            box = (box[0], box[1], box[2], min(box[3], wt - 2))
                        elif cy < top:
                            box = (box[0], max(box[1], wb + 2), box[2], box[3])
                out.append(box)
        return out

    def _find_faces(self, arr, words: list[Word]) -> list[tuple[int, int, int, int]]:
        if not hasattr(cv2, "CascadeClassifier"):  # OpenCV 5 moved Haar cascades out of the main package
            log.warning("cv2.CascadeClassifier unavailable (OpenCV %s): face detection disabled, "
                        "falling back to ID-card layout rules", cv2.__version__)
            return []
        path = os.path.join(getattr(getattr(cv2, "data", None), "haarcascades", ""), "haarcascade_frontalface_default.xml")
        if not os.path.exists(path):
            return []
        clf = cv2.CascadeClassifier(path)
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
        found: list[tuple[int, int, int, int]] = []
        # equalised pass catches low-contrast scans, raw pass catches well-lit photos that equalisation washes out
        for g in (gray, cv2.equalizeHist(gray)):
            for (x, y, w, h) in clf.detectMultiScale(g, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60)):
                box = (int(x), int(y), int(x + w), int(y + h))
                if self._text_cover(box, words) > 0.2:  # a "face" made of OCR'd words is a false positive
                    continue
                if not any(min(box[2], f[2]) > max(box[0], f[0]) and min(box[3], f[3]) > max(box[1], f[1]) for f in found):
                    found.append(box)
        return found

    @staticmethod
    def _portrait_from_face(face, words: list[Word], size) -> tuple[int, int, int, int]:
        """Widen a face box to the whole passport photo, stopping short of neighbouring text."""
        l, t, r, b = face
        fw, fh = r - l, b - t
        L, T_, R, B = max(0, int(l - 0.45 * fw)), max(0, int(t - 0.45 * fh)), min(size[0], int(r + 0.45 * fw)), min(size[1], int(b + 0.75 * fh))
        for w in words:
            wl, wt, wr, wb = w.box
            if wr <= L or wl >= R or wb <= T_ or wt >= B:
                continue
            if wt >= b and wl < r and wr > l:
                B = min(B, wt - 2)
            elif wl >= r:
                R = min(R, wl - 2)
            elif wr <= l:
                L = max(L, wr + 2)
            elif wb <= t:
                T_ = max(T_, wb + 2)
        return L, T_, R, B

    @staticmethod
    def _portrait_from_layout(lines: list[Line], size) -> tuple[tuple[int, int, int, int], str] | None:
        """No face found on an ID card: locate the photo frame from the printed layout.

        PAN: photo sits under the 'INCOME TAX DEPARTMENT' line, above the 'Name' label, left of the
        'Permanent Account Number' title. Aadhaar: photo sits left of the name/father/DOB/gender block.
        """
        def bbox(line):
            return (min(w.box[0] for w in line.words), min(w.box[1] for w in line.words),
                    max(w.box[2] for w in line.words), max(w.box[3] for w in line.words))
        text = [l.text.lower() for l in lines]
        find = lambda pat: next((i for i, t in enumerate(text) if re.search(pat, t)), None)  # noqa: E731
        itd, pan_title = find(r"income\s*tax"), find(r"permanent\s+account")
        if itd is not None and pan_title is not None:
            name = next((i for i in range(pan_title, len(lines)) if re.search(r"\bname\b", text[i])), None)
            if name is not None:
                top, right = bbox(lines[itd])[3] + 4, bbox(lines[pan_title])[0] - 6
                bottom, left = bbox(lines[name])[1] - 4, max(0, bbox(lines[name])[0] - 8)
                if right - left > 20 and bottom - top > 20:
                    return (left, top, right, bottom), "pan_layout"
        block = [i for i, t in enumerate(text) if PORTRAIT_BLOCK_RE.search(t)]
        if block:
            first = block[0] - 1 if block[0] > 0 and ImageRedactor._namelike(lines[block[0] - 1].text) else block[0]
            boxes = [bbox(lines[i]) for i in range(first, block[-1] + 1)]
            top, bottom = min(b[1] for b in boxes), max(b[3] for b in boxes)
            pad = int(0.25 * (bottom - top))
            top, bottom = max(0, top - pad), min(size[1], bottom + pad)
            right = min(b[0] for b in boxes) - 6
            left = max(0, int(right - 0.85 * (bottom - top)))
            if right - left > 20 and bottom - top > 20:
                return (left, top, right, bottom), "aadhaar_layout"
        return None

    def _qr_and_faces(self, img: Image.Image, rep: ImageReport, lines: list[Line]) -> Image.Image:
        if cv2 is None:
            return img
        arr = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
        words = [w for l in lines for w in l.words]
        if self.mask_qr:
            for box in self._find_qr(arr, words, rep.id_document):
                self._obscure(img, box)
                rep.qr_codes += 1
        if self.blur_faces:
            faces = self._find_faces(arr, words)
            rep.faces = len(faces)
            for f in faces:
                box = self._portrait_from_face(f, words, img.size) if rep.id_document else f
                self._obscure(img, box)
                rep.photo_regions.append({"box": box, "rule": "face"})
            if rep.id_document and not faces:
                found = self._portrait_from_layout(lines, img.size)
                if found:
                    self._obscure(img, found[0])
                    rep.photo_regions.append({"box": found[0], "rule": found[1]})
        return img

    # ------------------------------------------------------------------ entry point
    def process_part(self, part) -> ImageReport:
        rep = ImageReport(part=str(part.partname), size=(0, 0))
        try:
            img = Image.open(io.BytesIO(part.blob))
            img.load()
        except Exception:
            rep.skipped = "unsupported image format (e.g. EMF/WMF)"
            return rep
        fmt = img.format or "PNG"
        rep.size = img.size
        if min(img.size) < self.min_side:
            rep.skipped = "too small"
            return rep
        mode = img.mode
        work = img.convert("RGBA" if "A" in mode else "RGB")
        lines = self.ocr(work)
        rep.ocr_words = sum(len(l.words) for l in lines)
        hits, rep.id_document = self.detect(lines)
        # photo / QR first (on untouched pixels, and so pixelation never eats a painted fake)
        work = self._qr_and_faces(work, rep, lines)
        # register first (global consistency), then paint
        for h in hits:
            self.pseudo.register(h.text, h.type)
        for h in hits:
            box = self._boxes_for(lines[h.line], h)
            if box is None:
                continue
            fake = self.pseudo.fake_for(h.text, h.type)
            self._paint(work, box, fake)
            rep.hits.append({"type": h.type.value, "text": h.text, "pseudonym": fake, "box": box, "rule": h.source})
        if self.failsafe and rep.id_document and not hits:
            work = work.filter(ImageFilter.GaussianBlur(radius=max(12, min(work.size) // 25)))
            rep.failsafe_blur = True
        if not rep.hits and not rep.qr_codes and not rep.photo_regions and not rep.failsafe_blur:
            return rep  # untouched: keep the original bytes
        out = io.BytesIO()
        if fmt.upper() in ("JPEG", "JPG"):
            work.convert("RGB").save(out, format="JPEG", quality=92)
        else:
            try:
                work.save(out, format=fmt)
            except (KeyError, OSError, ValueError):
                work.save(out, format="PNG")
        part._blob = out.getvalue()
        return rep
