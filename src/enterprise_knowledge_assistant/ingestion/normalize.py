from __future__ import annotations

import unicodedata

# CJK Radicals Supplement glyphs that PDF fonts emit in place of the ordinary
# character and that NFKC leaves untouched.
_RADICALS = {
    "⺟": "母", "⺠": "民", "⻁": "虎", "⻄": "西", "⻅": "見", "⻆": "角", "⻋": "車",
    "⻑": "長", "⻔": "門", "⻗": "雨", "⻘": "青", "⻛": "風", "⻜": "飛", "⻝": "食",
    "⻡": "首", "⻢": "馬", "⻣": "骨", "⻤": "鬼", "⻥": "魚", "⻦": "鳥", "⻩": "黃",
    "⻫": "齊", "⻭": "齒", "⻯": "龍", "⻱": "龜",
}


def clean_text(text: str) -> str:
    """Replace radical look-alikes and unprintable glyphs; keep everything else.

    Only the radical blocks are normalized so full-width punctuation in the
    source survives unchanged.
    """

    out = []
    for char in text:
        code = ord(char)
        if 0x2E80 <= code <= 0x2FDF:
            char = _RADICALS.get(char) or unicodedata.normalize("NFKC", char)
        elif 0xE000 <= code <= 0xF8FF:
            char = "•"  # private-use bullet glyphs
        elif unicodedata.category(char) == "Cc" and char not in "\n\t":
            continue
        out.append(char)
    return "".join(out)
