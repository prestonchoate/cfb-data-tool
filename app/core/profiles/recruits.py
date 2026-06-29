# SPDX-License-Identifier: GPL-3.0-or-later
"""Recruit-card scrape profile.

Ported from the original CLI's ``src/scraper.py`` extract_* methods + ``src/models.py``
validation. Made OCR-backend-agnostic: extractors consume the ``OcrEngine`` interface
and tolerate both EasyOCR-style (one box per word) and RapidOCR-style (whole line per
box) output.
"""

from __future__ import annotations

import json
import logging
import re
from difflib import get_close_matches
from pathlib import Path

from .. import processor
from .base import ScrapeProfile, register_profile

logger = logging.getLogger(__name__)

# --- Output schema (column order for CSV/SQLite) ---
BASIC_INFO_HEADERS = [
    "NAME", "POSITION", "ARCHETYPE", "STARS", "GEM",
    "HEIGHT", "WEIGHT", "CLASS", "HOMETOWN", "DEV TRAIT",
]

ATTRIBUTE_HEADERS = [
    "SPEED", "ACCELERATION", "AGILITY", "CHANGE OF DIRECTION", "STRENGTH", "AWARENESS",
    "CARRYING", "BC VISION", "BREAK TACKLE", "TRUCKING", "STIFF ARM", "SPIN MOVE",
    "JUKE MOVE", "CATCHING", "CATCH IN TRAFFIC", "SPECTACULAR CATCH", "SHORT ROUTE",
    "MEDIUM ROUTE", "DEEP ROUTE", "RELEASE", "JUMPING", "THROW POWER", "SHORT ACCURACY",
    "MEDIUM ACCURACY", "DEEP ACCURACY", "THROW ON RUN", "UNDER PRESSURE", "BREAK SACK",
    "PLAY ACTION", "PASS BLOCK", "PASS BLOCK POWER", "PASS BLOCK FINESSE", "RUN BLOCK",
    "RUN BLOCK POWER", "RUN BLOCK FINESSE", "LEAD BLOCK", "IMPACT BLOCKING", "PLAY RECOGNITION",
    "TACKLE", "HIT POWER", "BLOCK SHEDDING", "FINESSE MOVES", "POWER MOVES", "PURSUIT",
    "MAN COVERAGE", "ZONE COVERAGE", "PRESS", "KICK RETURN", "KICK POWER", "KICK ACCURACY",
    "STAMINA", "TOUGHNESS", "INJURY", "LONG SNAPPER",
]

ABILITY_HEADERS = [
    "ABILITY_1", "ABILITY_1_LEVEL",
    "ABILITY_2", "ABILITY_2_LEVEL",
    "ABILITY_3", "ABILITY_3_LEVEL",
    "ABILITY_4", "ABILITY_4_LEVEL",
    "ABILITY_5", "ABILITY_5_LEVEL",
]

MENTAL_HEADERS = [
    "MENTAL_1", "MENTAL_1_LEVEL",
    "MENTAL_2", "MENTAL_2_LEVEL",
    "MENTAL_3", "MENTAL_3_LEVEL",
]

MENTAL_NAMES = [
    "Best Friend", "Clear Headed", "Clutch Kicker", "Defensive Rally",
    "Fan Favorite", "Field General", "Hot Head", "Headstrong",
    "Legion", "Offensive Rally", "Road Dog", "Team Player",
    "The Natural", "Winning Time",
]

POSITION_ATTRIBUTE_COUNT = {
    "QB": 10, "HB": 10, "FB": 10, "WR": 10, "TE": 10,
    "OT": 10, "OG": 10, "C": 10, "DT": 10, "DE": 10,
    "OLB": 10, "MLB": 10, "CB": 10, "SS": 10, "FS": 10,
    "K": 10, "P": 10, "ATH": 10,
}

# Fields that must be present & non-error for a scan to count as valid
# (mirrors the original test_accuracy.py pass criteria).
_REQUIRED = ["NAME", "POSITION", "ARCHETYPE", "CLASS", "HOMETOWN", "HEIGHT", "WEIGHT"]

_DEV_TRAIT_MAP = {"normal": "Normal", "impact": "Impact", "star": "Star", "elite": "Elite"}

_HEADER_MAP = {h.replace(" ", "").upper(): h for h in ATTRIBUTE_HEADERS}


# ---------------------------------------------------------------------------
# Low-level OCR helpers
# ---------------------------------------------------------------------------
def _crop(img, roi):
    y, h, x, w = roi
    return img[y:y + h, x:x + w]


def _read(ocr, img, roi):
    """OCR a cropped ROI; return list of (text, conf) in reading order."""
    results = ocr.readtext(_crop(img, roi), detail=1)
    return [(text, conf) for _bbox, text, conf in results]


def _read_with_pos(ocr, img, roi):
    """OCR a cropped ROI; return list of (top_y, text, conf) for spatial sorting."""
    results = ocr.readtext(_crop(img, roi), detail=1)
    return [(bbox[0][1], text, conf) for bbox, text, conf in results]


def _read_with_xy(ocr, img, roi):
    """OCR a cropped ROI; return list of (x, y, text, conf) from the top-left corner."""
    results = ocr.readtext(_crop(img, roi), detail=1)
    return [(bbox[0][0], bbox[0][1], text, conf) for bbox, text, conf in results]


def _mean_conf(confs) -> float:
    confs = [c for c in confs if c is not None]
    return round(sum(confs) / len(confs), 3) if confs else 0.0


# ---------------------------------------------------------------------------
# Field extractors  (return (value, confidence))
# ---------------------------------------------------------------------------
def extract_name(ocr, img, rois):
    pairs = _read(ocr, img, rois["name"])
    words = " ".join(t for t, _ in pairs).split()
    if len(words) < 2:
        return "Error", 0.0
    return f"{words[0]} {words[1]}", _mean_conf([c for _, c in pairs])


def extract_position(ocr, img, rois):
    pairs = _read(ocr, img, rois["position"])
    words = [w for w in " ".join(t for t, _ in pairs).split() if w.upper() != "POSITION"]
    if not words:
        return "Error", 0.0
    # The position code is the last token (drops any leading label).
    return words[-1], _mean_conf([c for _, c in pairs])


def extract_archetype(ocr, img, rois):
    raw = _read_with_xy(ocr, img, rois["archetype"])
    items = [(x, y, text) for x, y, text, _ in raw if text.upper() != "ARCHETYPE"]
    if not items:
        return "Error", 0.0
    # Order top-to-bottom, then left-to-right within a row. Y-only sorting left
    # same-line words at the mercy of OCR order ("Raw Strength" -> "Strength Raw").
    items.sort(key=lambda it: (round(it[1] / 25), it[0]))
    result = " ".join(text for _, _, text in items)

    # OCR reads "/" as "W"/"I": "East/West" -> "EastWWest"/"EastIWest". Fix this
    # before the PascalCase split below so the doubled W isn't broken apart.
    result = re.sub(r"East(?:/|[WI]+)West", "East/West", result)
    # RapidOCR often merges the two words into one box ("RawStrength",
    # "PassProtector"); re-insert the space at lower->upper case boundaries.
    result = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", result)
    # OCR occasionally inserts a stray "." between words ("Edge . Setter").
    result = re.sub(r"\s+\.\s+", " ", result)
    result = re.sub(r"\s{2,}", " ", result).strip()
    return result, _mean_conf([c for *_, c in raw])


def extract_recruit_class(ocr, img, rois):
    pairs = _read(ocr, img, rois["recruit_class"])
    words = [w for w in " ".join(t for t, _ in pairs).split() if w.upper() != "CLASS"]
    # RapidOCR sometimes appends a stray period ("High School." -> "High School").
    # No real class value contains a period, so strip them.
    result = " ".join(words).replace(".", "").strip()
    return (result or "Error"), _mean_conf([c for _, c in pairs])


def extract_hometown(ocr, img, rois):
    pairs = _read(ocr, img, rois["hometown"])
    texts = [t for t, _ in pairs if t.strip().upper() != "HOMETOWN"]
    s = " ".join(texts).replace(";", ",").strip()
    if not s:
        return "Error", 0.0
    # The card shows a small state/flag icon between city and state that RapidOCR
    # misreads as a stray glyph ("Sharpsburg, @ GA"). Real hometowns only contain
    # letters, spaces, commas, periods, hyphens and apostrophes — drop the rest.
    s = re.sub(r"[^A-Za-zÀ-ÿ ,.'\-]", "", s)
    # Ensure "City, State" form even if OCR dropped the comma.
    if "," not in s:
        head, _, tail = s.rpartition(" ")
        if head:
            s = f"{head}, {tail}"
    s = re.sub(r"\s*,\s*", ", ", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    # Uppercase the trailing 2-letter state ("Monument, Co" -> "Monument, CO").
    m = re.match(r"^(.*),\s*([A-Za-z]{2})$", s)
    if m:
        s = f"{m.group(1)}, {m.group(2).upper()}"
    return s, _mean_conf([c for _, c in pairs])


def _parse_height(s: str) -> str:
    """Parse a CFB height (feet'inches") from messy OCR text.

    Handles the foot-mark glyphs RapidOCR emits (' ' ′ ʹ ´ `), doubled marks
    ("6′'3" -> 6'3"), and a dropped mark with a trailing inch mark ("66" -> 6'6").
    """
    s = re.sub(r"[’′ʹ´`]", "'", s)  # normalize all foot-mark glyphs to '

    # feet, one-or-more foot marks, inches
    m = re.search(r"(\d)\s*'+\s*(\d{1,2})", s)
    if m:
        return f"{m.group(1)}'{m.group(2)}\""

    # feet+inches glued with no foot mark but a trailing inch mark: 66" -> 6'6"
    m = re.search(r"(?<!\d)(\d)(\d)\s*\"", s)
    if m:
        return f"{m.group(1)}'{m.group(2)}\""

    return ""


def extract_height_weight(ocr, img, rois):
    pairs = _read(ocr, img, rois["height_weight"])
    s = " ".join(t for t, _ in pairs)
    conf = _mean_conf([c for _, c in pairs])

    height = _parse_height(s)

    # Weight = the 3 digits before the "lbs" unit (OCR reads it "Ibs"/"lbs").
    # Anchoring to the unit isolates the weight even when height and weight glue
    # together with no separator ("5'10190Ibs" -> 190). Fall back to a standalone
    # 3-digit run if the unit wasn't recognized.
    wm = re.search(r"(\d{3})\s*[il]bs", s, re.IGNORECASE)
    if not wm:
        wm = re.search(r"(?<!\d)(\d{3})(?!\d)", s)
    weight = wm.group(1) if wm else ""

    return height, weight, conf


def extract_attributes(ocr, img, rois):
    """Extract the recruit-card attributes preserving the in-game layout.

    The card shows attributes in two columns; each cell is a label above its
    value. We split boxes into left/right columns by X, then pair label->value
    within each column by Y. Pairing per-column (not globally) avoids mismatches
    when the two columns' rows aren't perfectly aligned — e.g. Speed (right) and
    Medium Accuracy (left) sitting at nearly the same height. Results are emitted
    column-major (whole left column top-to-bottom, then right) so the order
    mirrors the screenshot.
    """
    roi = rois["attributes"]
    mid_x = roi[3] / 2  # ROI width / 2 divides the two columns
    items = _read_with_xy(ocr, img, roi)
    confs = []

    # side -> (labels, values), each a list of (y, text)
    cols = {"L": ([], []), "R": ([], [])}

    for x, y, raw, conf in items:
        confs.append(conf)
        labels, values = cols["L"] if x < mid_x else cols["R"]
        s = raw.strip()

        # Pure 2-digit value (a rating).
        if s.isdigit():
            if len(s) == 2:
                values.append((y, s))
            continue

        # Combined "LABEL 95" in a single box (RapidOCR occasionally merges a cell).
        m = re.match(r"^(.*?)[\s:]+(\d{2})$", s)
        if m and m.group(1).replace(" ", "").upper() in _HEADER_MAP:
            labels.append((y, _HEADER_MAP[m.group(1).replace(" ", "").upper()]))
            values.append((y, m.group(2)))
            continue

        # Pure label.
        key = s.replace(" ", "").upper()
        if key in _HEADER_MAP:
            labels.append((y, _HEADER_MAP[key]))
        else:
            logger.debug("Unrecognized attribute token: %r", raw)

    attrs = {}
    for side in ("L", "R"):
        labels, values = cols[side]
        labels.sort(key=lambda t: t[0])
        values.sort(key=lambda t: t[0])
        for (_ly, label), (_vy, value) in zip(labels, values):
            attrs[label] = value

    # Fallback: if the X split mis-bucketed labels and values into opposite
    # columns (nothing paired), pair globally by Y so we still return data.
    if not attrs and items:
        gl, gv = [], []
        for _x, y, raw, _c in items:
            s = raw.strip()
            if s.isdigit() and len(s) == 2:
                gv.append((y, s))
            else:
                key = s.replace(" ", "").upper()
                if key in _HEADER_MAP:
                    gl.append((y, _HEADER_MAP[key]))
        gl.sort(); gv.sort()
        attrs = dict(zip([l for _, l in gl], [v for _, v in gv]))

    return attrs, _mean_conf(confs)


def extract_star_rating(img, rois, scale: float = 1.0):
    return processor.get_star_rating(_crop(img, rois["star_rating"]), scale=scale)


def extract_gem_status(img, rois):
    return processor.detect_gem_status(_crop(img, rois["gem_icon"]))


_ABILITIES_TABLE = None


def _load_abilities_table():
    global _ABILITIES_TABLE
    if _ABILITIES_TABLE is None:
        path = Path(__file__).resolve().parents[2] / "config" / "presets" / "cfb26" / "abilities.json"
        _ABILITIES_TABLE = json.loads(path.read_text(encoding="utf-8"))
    return _ABILITIES_TABLE


def _get_expected_abilities(position: str, archetype: str) -> list[str]:
    table = _load_abilities_table()
    return table.get(position, {}).get(archetype, [])


def _fuzzy_match_ability(ocr_text: str, expected: list[str]) -> str:
    clean = ocr_text.strip()
    for name in expected:
        if clean.lower() == name.lower():
            return name
    matches = get_close_matches(clean, expected, n=1, cutoff=0.6)
    return matches[0] if matches else clean


def _group_by_y(items, threshold=25):
    if not items:
        return []
    sorted_items = sorted(items, key=lambda it: it[1])
    rows = [[sorted_items[0]]]
    for item in sorted_items[1:]:
        if abs(item[1] - rows[-1][0][1]) < threshold:
            rows[-1].append(item)
        else:
            rows.append([item])
    return rows


def _extract_icons_and_text(items, cropped, header_filter):
    """Shared extraction for abilities and mentals: pair icon colors with text."""
    items = [(x, y, text, conf) for x, y, text, conf in items
             if text.strip().upper() != header_filter]
    confs = [conf for _, _, _, conf in items]
    rows = _group_by_y(items, threshold=25)

    icon_right = max(1, int(max(min(x for x, _, _, _ in row)
                                   for row in rows) - 5)) if rows else 1

    results = {}
    for row_items in rows:

        text_tokens = sorted(row_items, key=lambda r: r[0])
        text = " ".join(t for _, _, t, _ in text_tokens)
        if not text.strip():
            continue

        avg_y = sum(it[1] for it in row_items) / len(row_items)
        band_top = max(0, int(avg_y - 15))
        band_bot = min(cropped.shape[0], int(avg_y + 25))
        icon_crop = cropped[band_top:band_bot, 0:icon_right]
        level = ""
        if icon_crop.size > 0:
            level = processor.detect_ability_level(icon_crop)

        results[text.strip()] = level

    return results, _mean_conf(confs)


def extract_abilities(ocr, img, rois, position: str, archetype: str):
    roi = rois.get("abilities")
    if roi is None:
        return {}, 0.0

    expected = _get_expected_abilities(position, archetype)
    items = _read_with_xy(ocr, img, roi)
    cropped = _crop(img, roi)

    abilities, conf = _extract_icons_and_text(items, cropped, "ABILITIES")

    if expected:
        abilities = {_fuzzy_match_ability(name, expected): level
                     for name, level in abilities.items()}

    return abilities, conf


def extract_mentals(ocr, img, rois):
    roi = rois.get("mentals")
    if roi is None:
        return {}, 0.0

    items = _read_with_xy(ocr, img, roi)
    cropped = _crop(img, roi)

    mentals, conf = _extract_icons_and_text(items, cropped, "MENTALS")

    mentals = {_fuzzy_match_ability(name, MENTAL_NAMES): level
               for name, level in mentals.items()}

    return mentals, conf


def extract_dev_trait(ocr, img, rois):
    pairs = _read(ocr, img, rois["dev_trait"])
    for text, conf in pairs:
        trait = _DEV_TRAIT_MAP.get(text.strip().lower())
        if trait:
            return trait, conf
    return "", 0.0


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
@register_profile
class RecruitsProfile(ScrapeProfile):
    key = "recruits"
    display_name = "Recruits"

    @property
    def roi_keys(self):
        return [
            "name", "position", "archetype", "recruit_class", "hometown",
            "height_weight", "abilities", "mentals", "attributes",
            "star_rating", "gem_icon", "dev_trait",
        ]

    @property
    def schema(self):
        return BASIC_INFO_HEADERS + ABILITY_HEADERS + MENTAL_HEADERS + ATTRIBUTE_HEADERS

    @property
    def dedupe_keys(self):
        return ["NAME", "POSITION"]

    def extract(self, img, rois, ocr, *, scale: float = 1.0) -> dict:
        conf = {}
        name, conf["NAME"] = extract_name(ocr, img, rois)
        position, conf["POSITION"] = extract_position(ocr, img, rois)
        archetype, conf["ARCHETYPE"] = extract_archetype(ocr, img, rois)
        recruit_class, conf["CLASS"] = extract_recruit_class(ocr, img, rois)
        hometown, conf["HOMETOWN"] = extract_hometown(ocr, img, rois)
        height, weight, hw_conf = extract_height_weight(ocr, img, rois)
        conf["HEIGHT"] = conf["WEIGHT"] = hw_conf
        abilities, conf["abilities"] = extract_abilities(ocr, img, rois, position, archetype)
        mentals, conf["mentals"] = extract_mentals(ocr, img, rois)
        attributes, conf["attributes"] = extract_attributes(ocr, img, rois)
        dev_trait, conf["DEV TRAIT"] = extract_dev_trait(ocr, img, rois)

        return {
            "NAME": name,
            "POSITION": position,
            "ARCHETYPE": archetype,
            "STARS": extract_star_rating(img, rois, scale=scale),
            "GEM": extract_gem_status(img, rois),
            "HEIGHT": height,
            "WEIGHT": weight,
            "CLASS": recruit_class,
            "HOMETOWN": hometown,
            "DEV TRAIT": dev_trait,
            "abilities": abilities,
            "mentals": mentals,
            "attributes": attributes,
            "_confidence": conf,
        }

    def validate(self, record) -> tuple[bool, list[str]]:
        missing = [k for k in _REQUIRED if record.get(k) in ("Error", "", None)]

        attrs = record.get("attributes", {})
        expected = POSITION_ATTRIBUTE_COUNT.get(record.get("POSITION"), 10)
        if len(attrs) != expected:
            missing.append(f"attributes({len(attrs)}/{expected})")

        stars = record.get("STARS")
        if not (isinstance(stars, int) and 1 <= stars <= 5):
            missing.append("STARS")

        return (not missing), missing

    def to_row(self, record) -> list:
        row = [record.get(h, "") for h in BASIC_INFO_HEADERS]
        ability_items = list(record.get("abilities", {}).items())
        for i in range(5):
            if i < len(ability_items):
                name, level = ability_items[i]
                row.extend([name, level])
            else:
                row.extend(["", ""])
        mental_items = list(record.get("mentals", {}).items())
        for i in range(3):
            if i < len(mental_items):
                name, level = mental_items[i]
                row.extend([name, level])
            else:
                row.extend(["", ""])
        attrs = record.get("attributes", {})
        for header in ATTRIBUTE_HEADERS:
            row.append(attrs.get(header.upper(), ""))
        return row
