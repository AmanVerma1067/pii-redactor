"""Global, deterministic, format-preserving pseudonymization.

* One `Pseudonymizer` instance = one global mapping cache for a document (text, tables, headers,
  footers, hyperlinks, metadata AND images all share it).
* Deterministic: fakes are derived from HMAC(salt, entity) so re-running with the same salt gives
  the same output; change the salt to get a different (unlinkable) pseudonym space.
* Consistent at token level: "Kushal Subbayya Hegde", "Rajesh Kushal Hegde", "Mr. Hegde" and
  "KUSHAL HEGDE" all reuse the same fake tokens, so family relations and references survive.
* Format-preserving: IDs keep length, separators, case and structural fields (PAN holder type,
  CIN listing status, SEBI prefix, phone country code); fakes are checksum-valid where the real
  scheme has one (Aadhaar-Verhoeff, card-Luhn).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import random
import re
import string
from collections import defaultdict

from .entities import ALNUM_TYPES, EntityType as T
from .gazetteer import (ADDR_AREA, ADDR_BUILDING, ADDR_CITY, ADDR_STREET, ADDR_UNIT, COMMON_WORD_NAMES,
                        FAKE_BRANDS, FAKE_FEMALE, FAKE_MALE, FAKE_SURNAMES, FIRST_FEMALE, FIRST_MALE,
                        FIRST_NAMES, GENERIC_ORG_WORDS, GIVEN_PREFIX, GIVEN_SUFFIX, NAME_STOP,
                        PUBLIC_EMAIL_PROVIDERS, ROLE_MAILBOX_WORDS, SURNAME_PREFIX, SURNAME_SUFFIX)
from .heuristics import LEGAL_SUFFIX, strip_honorific
from .validators import digits, luhn_digit, verhoeff_digit

SEP = r"[ \u00a0]+"
STATE_CODES = "MH KA GJ DL TN TG KL WB UP RJ MP HR PB GA".split()
LEGAL_WORDS = {"private", "limited", "ltd", "ltd.", "pvt", "pvt.", "llp", "inc", "inc.", "corporation",
               "corp.", "llc", "plc", "gmbh", "pte", "pte.", "public", "co", "co.", "company", "associates", "bank"}
_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
           "October", "November", "December"]


def match_case(src: str, fake: str) -> str:
    letters = [c for c in src if c.isalpha()]
    if len(letters) > 1 and all(c.isupper() for c in letters):
        return fake.upper()
    if letters and all(c.islower() for c in letters):
        return fake.lower()
    return fake


def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def alnum_key(s: str) -> str:
    return "".join(ch for ch in s if ch.isalnum()).upper()


def _lev1(a: str, b: str) -> bool:
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    return any(b[:i] + b[i + 1:] == a for i in range(len(b)))


class Pseudonymizer:
    def __init__(self, salt: str = "scaler-ai-labs"):
        self.salt = salt.encode()
        self.name_tokens: dict[str, str] = {}
        self.org_groups: dict[str, str] = {}      # distinctive org span (lower) -> fake brand
        self.org_single: dict[str, str] = {}      # individual distinctive tokens -> brand (for domains)
        self.domains: dict[str, str] = {}
        self.values: dict[tuple[T, str], str] = {}
        self.used: dict[str, set] = defaultdict(set)
        self.entities: dict[tuple[str, str], str] = {}   # (type, original surface) -> fake (report)
        self.text_surfaces: dict[str, tuple[T, bool]] = {}
        self.alnum_surfaces: dict[str, T] = {}
        self._matcher: re.Pattern | None = None
        self._cache: dict[tuple[T, str], str] = {}

    # ================================================================== RNG / pools
    def _rng(self, key: str) -> random.Random:
        h = hmac.new(self.salt, key.encode("utf-8"), hashlib.sha256).digest()
        return random.Random(int.from_bytes(h[:8], "big"))

    def _pick(self, key: str, pool: list[str], bucket: str, fallback) -> str:
        rng = self._rng(key)
        for cand in rng.sample(pool, len(pool)):
            if cand.lower() not in self.used[bucket] and cand.lower() != key.split("|")[-1]:
                self.used[bucket].add(cand.lower())
                return cand
        for i in range(10_000):
            cand = fallback(rng)
            if cand.lower() not in self.used[bucket]:
                self.used[bucket].add(cand.lower())
                return cand
        raise RuntimeError("pseudonym space exhausted")

    # ================================================================== registration (pass 1)
    def register(self, text: str, etype: T) -> None:
        text = re.sub(r"[ \t\u00a0]+", " ", text).strip()
        if len(text) < 2:
            return
        if etype is T.ADDRESS and "\n" in text:
            for piece in text.split("\n"):
                piece = piece.strip(" ,")
                if len(piece) >= 6:
                    self.register(piece, T.ADDRESS)
            return
        text = text.replace("\n", " ")
        self._matcher = None
        if etype is T.PERSON:
            self._register_person(text)
        elif etype is T.ORG:
            self._register_org(text)
        elif etype in (T.EMAIL, T.URL, T.DOMAIN):
            self.text_surfaces[norm_text(text)] = (etype, False)
            host = self._host(text)
            if host and host not in PUBLIC_EMAIL_PROVIDERS and etype is not T.DOMAIN:
                self.text_surfaces[host] = (T.DOMAIN, False)
        elif etype in ALNUM_TYPES:
            key = digits(text) if etype is T.PHONE else alnum_key(text)
            if len(key) >= 6:
                self.alnum_surfaces[key] = etype
        else:  # ADDRESS, DOB, IP_ADDRESS
            self.text_surfaces[norm_text(text)] = (etype, False)
        self.entities[(etype.value, text)] = self.fake_for(text, etype)

    def _register_person(self, text: str) -> None:
        _, name = strip_honorific(text)
        toks = name.split()
        if not toks or any(not re.fullmatch(r"[A-Za-z][A-Za-z.'’\-]*", t) for t in toks):
            return
        keys = [t.lower().strip(".'’") for t in toks]
        if all(k in NAME_STOP for k in keys):
            return
        if any(k in {"contact", "person", "secretary", "compliance", "officer", "director", "manager", "auditor", "shareholder", "promoter", "board", "company"} for k in keys):
            return
        # establish token roles from the full name (given ... surname)
        content = [t for t in toks if not re.fullmatch(r"[A-Za-z]\.?", t)]
        for i, t in enumerate(content):
            role = "surname" if (i == len(content) - 1 and len(content) > 1) else "given"
            if len(content) == 1:
                role = "given" if t.lower() in FIRST_NAMES else "surname"
            self._name_token(t, role)
        self.text_surfaces[norm_text(name)] = (T.PERSON, False)
        if len(content) >= 3:
            self.text_surfaces[norm_text(f"{content[0]} {content[-1]}")] = (T.PERSON, False)
        for t in content:
            k = t.lower().strip(".'’")
            if len(k) >= 4 and k not in COMMON_WORD_NAMES and k not in NAME_STOP:
                self.text_surfaces.setdefault(k, (T.PERSON, True))

    def _register_org(self, text: str) -> None:
        nt = norm_text(text)
        words = [re.sub(r"[^\w]", "", w).lower() for w in text.split()]
        words = [w for w in words if w]
        if not words or all(w in NAME_STOP or w in GENERIC_ORG_WORDS for w in words):
            return
        if nt in {"company", "our company", "the company", "by our company", "against our company", "limited", "pvt ltd"}:
            return
        self.text_surfaces[nt] = (T.ORG, False)
        for group in self._org_groups(text):
            g = " ".join(group)
            self._brand_for_group(group)
            if len(g) >= 3 and g.lower() not in NAME_STOP and g.lower() not in COMMON_WORD_NAMES and g.lower() not in GENERIC_ORG_WORDS:
                self.text_surfaces.setdefault(norm_text(g), (T.ORG, True))

    # ================================================================== surface -> fake
    def fake_for(self, surface: str, etype: T) -> str:
        ck = (etype, surface)
        if ck in self._cache:
            return self._cache[ck]
        f = {
            T.PERSON: self._fake_person, T.ORG: self._fake_org, T.EMAIL: self._fake_email,
            T.URL: self._fake_url, T.DOMAIN: self._fake_domain, T.ADDRESS: self._fake_address,
            T.DOB: self._fake_date, T.IP_ADDRESS: self._fake_ip,
        }.get(etype)
        out = f(surface) if f else self._fake_alnum(surface, etype)
        self._cache[ck] = out
        return out

    # ---------------------------------------------------------------- persons
    def _name_token(self, tok: str, role: str) -> str:
        key = tok.lower().strip(".'’")
        if key in self.name_tokens:
            return self.name_tokens[key]
        if role == "surname":
            fake = self._pick(f"SUR|{key}", FAKE_SURNAMES, "name",
                              lambda r: r.choice(SURNAME_PREFIX) + r.choice(SURNAME_SUFFIX))
        else:
            rng = self._rng(f"GEN|{key}")
            female = key in FIRST_FEMALE or (key not in FIRST_MALE and rng.random() < 0.5)
            fake = self._pick(f"GIV|{key}", FAKE_FEMALE if female else FAKE_MALE, "name",
                              lambda r: r.choice(GIVEN_PREFIX) + r.choice(GIVEN_SUFFIX))
        self.name_tokens[key] = fake
        return fake

    def _fake_person(self, surface: str) -> str:
        hon, name = strip_honorific(surface)
        parts = re.split(r"(\s+)", name)
        content_idx = [i for i, p in enumerate(parts) if p.strip() and not re.fullmatch(r"[A-Za-z]\.?", p)]
        out = []
        for i, p in enumerate(parts):
            if not p.strip():
                out.append(p)
            elif re.fullmatch(r"[A-Za-z]\.?", p):  # initial
                letter = self._letter(p[0].upper())
                out.append(match_case(p, letter) + ("." if p.endswith(".") else ""))
            else:
                role = "surname" if (i == content_idx[-1] and len(content_idx) > 1) else "given"
                if len(content_idx) == 1:
                    role = "given" if p.lower() in FIRST_NAMES else "surname"
                core = p.strip(".'’")
                fake = self._name_token(core, role)
                out.append(p.replace(core, match_case(core, fake)))
        return hon + "".join(out)

    def _letter(self, ch: str) -> str:
        key = f"LETTER|{ch}"
        if key not in self._cache_letters():
            letters = list(string.ascii_uppercase)
            self._rng("LETTERPERM").shuffle(letters)
            for a, b in zip(string.ascii_uppercase, letters):
                self._letters[f"LETTER|{a}"] = b
        return self._letters.get(key, ch)

    def _cache_letters(self) -> dict:
        if not hasattr(self, "_letters"):
            self._letters = {}
        return self._letters

    # ---------------------------------------------------------------- organisations
    @staticmethod
    def _org_groups(surface: str) -> list[list[str]]:
        body = LEGAL_SUFFIX.sub(" ", surface)
        toks = body.split()
        groups, cur = [], []
        for t in toks:
            k = t.lower().strip(",.")
            if k in GENERIC_ORG_WORDS or k in LEGAL_WORDS or k.strip("()") in GENERIC_ORG_WORDS:
                if cur:
                    groups.append(cur)
                cur = []
            else:
                cur.append(t.strip(","))
        if cur:
            groups.append(cur)
        if not groups and toks:
            groups = [[toks[0]]]
        return groups

    def _brand_for_group(self, group: list[str]) -> str:
        key = " ".join(group).lower()
        if key in self.org_groups:
            return self.org_groups[key]
        if len(group) == 1 and len(group[0]) <= 3 and group[0].isupper():  # acronym -> acronym
            rng = self._rng(f"ACR|{key}")
            fake = key.upper()
            while fake.lower() == key or fake.lower() in self.used["brand"]:
                fake = "".join(rng.choice(string.ascii_uppercase) for _ in group[0])
            self.used["brand"].add(fake.lower())
        else:
            fake = self._pick(f"BRAND|{key}", FAKE_BRANDS, "brand",
                              lambda r: r.choice(FAKE_BRANDS) + r.choice(["ex", "ia", "on", "ix", "ara"]))
        self.org_groups[key] = fake
        for t in group:
            if len(t) >= 3:
                self.org_single.setdefault(t.lower(), fake)
        return fake

    def _fake_org(self, surface: str) -> str:
        out = surface
        for group in sorted(self._org_groups(surface), key=lambda g: -len(" ".join(g))):
            g = " ".join(group)
            fake = self._brand_for_group(group)
            pat = re.compile(SEP.join(re.escape(t) for t in group), re.I)
            m = pat.search(out)
            if m:
                out = out[:m.start()] + match_case(m.group(), fake) + out[m.end():]
        return out

    # ---------------------------------------------------------------- email / url / domain
    @staticmethod
    def _host(text: str) -> str:
        t = text.lower()
        if "@" in t:
            return t.rsplit("@", 1)[1]
        t = re.sub(r"^(?:https?://)?", "", t)
        t = re.sub(r"^www\.", "", t)
        return t.split("/")[0].split(":")[0]

    def _fake_domain(self, domain: str) -> str:
        d = domain.lower().rstrip(".")
        www = ""
        if d.startswith("www."):
            www, d = "www.", d[4:]
        if d in PUBLIC_EMAIL_PROVIDERS:
            return www + "example.com"
        if d in self.domains:
            return www + self.domains[d]
        labels = d.split(".")
        idx = -3 if len(labels) >= 3 and labels[-2] in ("co", "org", "net", "gov", "ac", "com") else -2
        sld = labels[idx] if len(labels) >= 2 else labels[0]
        new = sld
        for k, v in sorted(self.org_groups.items(), key=lambda kv: -len(kv[0])):
            kk = re.sub(r"[^a-z0-9]", "", k)
            if len(kk) >= 3 and kk in new:
                new = new.replace(kk, re.sub(r"[^a-z0-9]", "", v.lower()))
        if new == sld:
            for k, v in sorted(self.org_single.items(), key=lambda kv: -len(kv[0])):
                kk = re.sub(r"[^a-z0-9]", "", k)
                if len(kk) >= 3 and kk in new:
                    new = new.replace(kk, re.sub(r"[^a-z0-9]", "", v.lower()))
        if new == sld:
            new = self._pick(f"DOM|{sld}", FAKE_BRANDS, "brand",
                             lambda r: r.choice(FAKE_BRANDS) + r.choice(["ex", "ia", "on"])).lower()
        fake = f"{new}.example.com"
        self.domains[d] = fake
        return www + fake

    def _fake_local(self, local: str) -> str:
        parts = re.split(r"([._\-+])", local)
        out = []
        for p in parts:
            if not p or p in "._-+":
                out.append(p)
                continue
            k = p.lower()
            replaced = None
            for gk, gv in sorted(self.org_groups.items(), key=lambda kv: -len(kv[0])):
                kk = re.sub(r"[^a-z0-9]", "", gk)
                if len(kk) >= 3 and kk in k:
                    replaced = k.replace(kk, re.sub(r"[^a-z0-9]", "", gv.lower()))
                    break
            if replaced is None and k in self.name_tokens:
                replaced = self.name_tokens[k].lower()
            if replaced is None and len(k) >= 5:
                for nk, nv in self.name_tokens.items():
                    if len(nk) >= 4 and _lev1(k, nk):
                        replaced = nv.lower()
                        break
            if replaced is None and (k in ROLE_MAILBOX_WORDS or len(k) <= 2):
                replaced = k
            if replaced is None and k.isdigit():
                replaced = "".join(self._rng(f"LD|{k}").choice(string.digits) for _ in k)
            if replaced is None:
                replaced = self._name_token(k, "given").lower()
            out.append(replaced)
        return "".join(out)

    def _fake_email(self, surface: str) -> str:
        local, _, domain = surface.rpartition("@")
        return match_case(surface, f"{self._fake_local(local)}@{self._fake_domain(domain)}")

    def _fake_url(self, surface: str) -> str:
        m = re.match(r"(?i)^(https?://)?(www\.)?([^/\s:]+)(.*)$", surface)
        if not m:
            return surface
        scheme, www, host, rest = m.groups()
        return (scheme or "") + (www or "") + self._fake_domain(host) + rest

    # ---------------------------------------------------------------- dates / ip / address
    def _fake_date(self, surface: str) -> str:
        rng = self._rng(f"DATE|{norm_text(surface)}")
        offset = rng.randint(60, 900) * rng.choice([-1, 1])
        m = re.fullmatch(r"(\d{1,2})([/\-.])(\d{1,2})\2(\d{2}|\d{4})", surface.strip())
        try:
            if m:
                d, sep, mo, y = m.groups()
                year = int(y) if len(y) == 4 else 1900 + int(y) if int(y) > 30 else 2000 + int(y)
                nd = dt.date(year, int(mo), int(d)) + dt.timedelta(days=offset)
                return (f"{nd.day:0{len(d)}d}{sep}{nd.month:0{len(mo)}d}{sep}"
                        f"{nd.year if len(y) == 4 else nd.year % 100:0{len(y)}d}")
            m2 = re.fullmatch(r"(\d{1,2})(st|nd|rd|th)?(\s+)([A-Za-z]+)(\.?,?\s+)(\d{4})", surface.strip())
            m3 = re.fullmatch(r"([A-Za-z]+)(\.?\s+)(\d{1,2})(st|nd|rd|th)?(,?\s+)(\d{4})", surface.strip())
            if m2 or m3:
                if m2:
                    d, suf, s1, mon, s2, y = m2.groups()
                else:
                    mon, s1, d, suf, s2, y = m3.groups()
                mi = [x[:3].lower() for x in _MONTHS].index(mon[:3].lower())
                nd = dt.date(int(y), mi + 1, int(d)) + dt.timedelta(days=offset)
                name = _MONTHS[nd.month - 1]
                name = name[:3] if len(mon) <= 4 and mon.lower() not in ("june", "july") else name
                name = match_case(mon, name)
                suf2 = ""
                if suf:
                    suf2 = "th" if 11 <= nd.day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(nd.day % 10, "th")
                if m2:
                    return f"{nd.day}{suf2}{s1}{name}{s2}{nd.year}"
                return f"{name}{s1}{nd.day}{suf2}{s2}{nd.year}"
        except (ValueError, IndexError):
            pass
        return self._fake_alnum(surface, T.DOB)

    def _fake_ip(self, surface: str) -> str:
        rng = self._rng(f"IP|{surface}")
        if ":" in surface:
            return "2001:db8::" + ":".join(f"{rng.randint(0, 65535):x}" for _ in range(3))
        return rng.choice(["192.0.2.", "198.51.100.", "203.0.113."]) + str(rng.randint(1, 254))

    def _fake_address(self, surface: str) -> str:
        rng = self._rng(f"ADDR|{norm_text(surface)}")
        n_parts = max(2, min(6, surface.count(",") + 1))
        pin = re.search(r"[1-9]\d{2}\s?\d{3}(?!\d)", surface)
        comps = [rng.choice(ADDR_UNIT).format(n=rng.randint(1, 250), m=rng.randint(1, 20)),
                 rng.choice(ADDR_BUILDING), rng.choice(ADDR_STREET), rng.choice(ADDR_AREA)]
        comps = comps[:max(1, n_parts - 1)]
        city = rng.choice(ADDR_CITY)
        if pin:
            fpin = "9" + "".join(rng.choice(string.digits) for _ in range(5))
            if " " in pin.group():
                fpin = fpin[:3] + " " + fpin[3:]
            city = f"{city} {fpin}"
        comps.append(city)
        if re.search(r"(?i)\bindia\b", surface):
            comps.append("India")
        return match_case(surface, ", ".join(comps))

    # ---------------------------------------------------------------- alphanumeric identifiers
    def _value(self, etype: T, key: str) -> str:
        ck = (etype, key)
        if ck in self.values:
            return self.values[ck]
        rng = self._rng(f"{etype.value}|{key}")
        for _ in range(1000):
            fake = self._gen_alnum(etype, key, rng)
            if fake != key and fake not in self.used[etype.value]:
                break
        self.used[etype.value].add(fake)
        self.values[ck] = fake
        return fake

    def _gen_alnum(self, etype: T, key: str, rng: random.Random) -> str:
        U, D = string.ascii_uppercase, string.digits
        L = lambda n: "".join(rng.choice(U) for _ in range(n))  # noqa: E731
        N = lambda n: "".join(rng.choice(D) for _ in range(n))  # noqa: E731
        n = len(key)
        if etype is T.PAN and n == 10:
            return L(3) + key[3] + L(1) + N(4) + L(1)
        if etype is T.AADHAAR and n == 12:
            body = rng.choice("23456789") + N(10)
            return body + verhoeff_digit(body)
        if etype is T.CIN and n == 21:
            return key[0] + N(5) + rng.choice(STATE_CODES) + str(rng.randint(1950, 2022)) + key[12:15] + N(6)
        if etype is T.GSTIN and n == 15:
            return f"{rng.randint(1, 37):02d}" + self._value(T.PAN, key[2:12]) + key[12] + "Z" + rng.choice(U + D)
        if etype is T.SEBI_REG:
            alpha_len = len(key) - len(key.lstrip(U))
            prefix = key[:alpha_len]
            num_part = key[alpha_len:]
            zeros = len(num_part) - len(num_part.lstrip("0"))
            digits_needed = len(num_part) - zeros - 1
            if digits_needed >= 0:
                return prefix + "0" * zeros + rng.choice("123456789") + N(digits_needed)
            return prefix + N(len(num_part))
        if etype is T.DIN:
            zeros = len(key) - len(key.lstrip("0"))
            return "0" * zeros + rng.choice("123456789") + N(n - zeros - 1)
        if etype is T.IFSC and n == 11:
            return L(4) + "0" + N(6)
        if etype is T.CREDIT_CARD:
            body = key[0] + N(n - 2)
            return body + luhn_digit(body)
        if etype is T.SSN and n == 9:
            return "9" + N(8)
        if etype is T.PASSPORT and n == 8:
            return rng.choice("ABCDEFGHJKLMNPRSTUVWY") + rng.choice("123456789") + N(6)
        if etype is T.PHONE:
            keep = n - 10 if n > 10 else 0
            if key.startswith("1800"):
                keep = 4
            head, body = key[:keep], key[keep:]
            if not body:
                return head
            if body[0] in "6789" and len(body) == 10:
                first = rng.choice("6789")
            else:
                first = body[0]
            return head + first + N(len(body) - 1)
        if etype is T.BANK_ACCOUNT:
            return rng.choice("123456789") + N(n - 1)
        # generic: letters->letters, digits->digits
        return "".join(rng.choice(U) if c.isalpha() else rng.choice(D) for c in key)

    def _fake_alnum(self, surface: str, etype: T) -> str:
        key = digits(surface) if etype in (T.PHONE, T.DOB) else alnum_key(surface)
        if not key:
            return surface
        if etype is T.DOB:
            rng = self._rng(f"DOBD|{key}")
            fake = "".join(rng.choice(string.digits) for _ in key)
        else:
            fake = self._value(etype, key)
        it = iter(fake)
        out = []
        for ch in surface:
            if (ch.isdigit() if etype in (T.PHONE, T.DOB) else ch.isalnum()):
                f = next(it, ch)
                out.append(f.lower() if ch.islower() else f)
            else:
                out.append(ch)
        return "".join(out)

    # ================================================================== matching (pass 2)
    def _build_matcher(self) -> re.Pattern | None:
        pats: list[tuple[int, str]] = []
        for s, (et, _) in self.text_surfaces.items():
            body = SEP.join(re.escape(t) for t in s.split(" "))
            if et is T.DOMAIN:
                pats.append((len(s), rf"(?<![\w.\-]){body}(?![\w\-])"))
            else:
                lb = r"(?<![\w])" if s[:1].isalnum() else ""
                la = r"(?![\w])" if s[-1:].isalnum() else ""
                pats.append((len(s), lb + body + la))
        for k, et in self.alnum_surfaces.items():
            sep = r"[ \-.\u00a0()]{0,2}"
            body = sep.join(re.escape(c) for c in k)
            pre = r"\+?" if et is T.PHONE else ""
            pats.append((len(k), rf"(?<![A-Za-z0-9+]){pre}{body}(?![A-Za-z0-9])"))
        if not pats:
            return None
        pats.sort(key=lambda p: -p[0])
        return re.compile("|".join(p for _, p in pats), re.I)

    def lookup(self, matched: str) -> T | None:
        n = norm_text(matched)
        if n in self.text_surfaces:
            et, cap = self.text_surfaces[n]
            if cap and not matched[:1].isupper():
                return None
            return et
        for key in (alnum_key(matched), digits(matched)):
            if key in self.alnum_surfaces:
                return self.alnum_surfaces[key]
        return None

    def replace_spans(self, text: str) -> list[tuple[int, int, str]]:
        if self._matcher is None:
            self._matcher = self._build_matcher()
        if self._matcher is None or not text:
            return []
        out = []
        for m in self._matcher.finditer(text):
            et = self.lookup(m.group())
            if et is None:
                continue
            fake = self.fake_for(m.group(), et)
            if et is T.PERSON:
                fake = match_case(m.group(), fake) if m.group().isupper() else fake
            if fake != m.group():
                out.append((m.start(), m.end(), fake))
        return out

    def replace_text(self, text: str) -> str:
        for s, e, r in reversed(self.replace_spans(text)):
            text = text[:s] + r + text[e:]
        return text

    # ================================================================== export
    def mapping(self) -> list[dict]:
        return [{"type": t, "original": o, "pseudonym": f} for (t, o), f in sorted(self.entities.items())]
