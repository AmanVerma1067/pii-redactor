"""Checksum / structural validators used to cut regex false positives."""
from __future__ import annotations

import ipaddress

_VD = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],
       [4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],
       [8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]
_VP = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],
       [9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]
_VINV = [0,4,3,2,1,5,6,7,8,9]


def digits(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())


def verhoeff_ok(num: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(digits(num))):
        c = _VD[c][_VP[i % 8][int(ch)]]
    return c == 0


def verhoeff_digit(num: str) -> str:
    c = 0
    for i, ch in enumerate(reversed(digits(num))):
        c = _VD[c][_VP[(i + 1) % 8][int(ch)]]
    return str(_VINV[c])


def luhn_ok(num: str) -> bool:
    d = digits(num)
    if not 13 <= len(d) <= 19:
        return False
    total = 0
    for i, ch in enumerate(reversed(d)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def luhn_digit(partial: str) -> str:
    for c in "0123456789":
        if luhn_ok(partial + c):
            return c
    return "0"


def ip_ok(s: str) -> bool:
    try:
        ip = ipaddress.ip_address(s)
    except ValueError:
        return False
    # "1.2.3.4"-style section numbers are rejected: require at least one octet > 9 for v4
    if ip.version == 4:
        return any(int(o) > 9 for o in s.split("."))
    return True


def phone_digits_ok(s: str, lo: int = 10, hi: int = 13) -> bool:
    return lo <= len(digits(s)) <= hi
