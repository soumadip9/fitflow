"""
Production occasion rules — 100-point additive scoring engine.

Score = Occasion (50) + Style Match (20) + Color Harmony (15) + Compatibility (15)
Hard constraints can zero the score entirely.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, Tuple

# ── YOLO model class names ──────────────────────────────────────────
YOLO_CLASSES = frozenset({
    "blazer", "boot", "cardigan", "casual", "dress", "formal_shirt",
    "heel", "hoodie", "jeans", "longsleeve", "pullover", "shorts",
    "skirt", "slide", "sneaker", "sport", "sweaters", "sweatshirt",
    "t-shirt", "top", "trousers", "vest",
})

# ── Category buckets ────────────────────────────────────────────────
TOPS: Set[str] = {
    "t-shirt", "formal_shirt", "hoodie", "cardigan", "pullover",
    "sweaters", "sweatshirt", "longsleeve", "blazer", "top", "vest",
}
BOTTOMS: Set[str] = {"jeans", "trousers", "shorts", "skirt"}
FOOTWEAR: Set[str] = {"sneaker", "boot", "heel", "slide"}
STYLE_TAGS: Set[str] = {"casual", "sport", "dress"}

# Map style tags to default slot
STYLE_TAG_SLOT: Dict[str, str] = {
    "casual": "top",
    "sport": "shoes",
    "dress": "top",
}

def _cls(item: Optional[Dict[str, Any]]) -> str:
    if not item:
        return ""
    return (item.get("category") or "").lower().strip()

def _color(item: Optional[Dict[str, Any]]) -> str:
    if not item:
        return ""
    return (item.get("color") or "").lower().strip()

def _slot_of(cls: str) -> str:
    if cls in TOPS:
        return "top"
    if cls in BOTTOMS:
        return "bottom"
    if cls in FOOTWEAR:
        return "shoes"
    if cls in STYLE_TAG_SLOT:
        return STYLE_TAG_SLOT[cls]
    return ""

# ── Formality levels (for style-match scoring) ──────────────────────
FORMALITY: Dict[str, int] = {
    "blazer": 5, "formal_shirt": 5, "vest": 4, "longsleeve": 4,
    "cardigan": 3, "sweaters": 3, "pullover": 3, "top": 3,
    "t-shirt": 2, "hoodie": 1, "sweatshirt": 1, "casual": 1,
    "trousers": 5, "skirt": 4, "jeans": 3, "shorts": 1,
    "heel": 5, "boot": 4, "sneaker": 2, "slide": 1, "sport": 1,
    "dress": 4,
}

OCCASION_FORMALITY: Dict[str, int] = {
    "formal_event": 5,
    "office": 4,
    "date_night": 4,
    "party": 3,
    "travel": 2,
    "casual_day": 2,
    "gym": 1,
}

# ── Color harmony ───────────────────────────────────────────────────
NEUTRALS = {"black", "white", "gray", "grey", "cream", "beige", "charcoal"}

COLOR_TO_BASE: Dict[str, str] = {
    "black": "black", "charcoal": "black",
    "white": "white", "cream": "white",
    "gray": "gray", "grey": "gray",
    "beige": "brown", "tan": "brown", "brown": "brown",
    "maroon": "red", "dark_red": "red", "red": "red", "pink": "red", "orange": "red",
    "yellow": "yellow",
    "olive": "green", "green": "green", "lime": "green", "teal": "green",
    "navy": "blue", "blue": "blue", "sky_blue": "blue", "purple": "blue", "violet": "blue",
}

COLOR_COMPAT: Dict[str, Set[str]] = {
    "black":  {"white", "gray", "red", "blue", "green", "brown", "yellow"},
    "white":  {"black", "blue", "green", "red", "brown", "gray"},
    "blue":   {"white", "black", "gray", "brown"},
    "red":    {"black", "white", "gray"},
    "green":  {"black", "white", "gray", "brown"},
    "brown":  {"white", "black", "blue", "green", "yellow"},
    "yellow": {"black", "blue", "gray"},
    "gray":   {"black", "white", "blue", "red", "green", "brown"},
}

def _base(c: str) -> str:
    return COLOR_TO_BASE.get(c, c)

# ── Compatibility matrix (good/bad combos) ──────────────────────────
GOOD_COMBOS: Dict[Tuple[str, str], int] = {
    ("blazer", "formal_shirt"): 15,
    ("formal_shirt", "blazer"): 15,
    ("t-shirt", "jeans"): 10,
    ("jeans", "t-shirt"): 10,
    ("hoodie", "sneaker"): 10,
    ("sneaker", "hoodie"): 10,
    ("hoodie", "jeans"): 8,
    ("jeans", "hoodie"): 8,
    ("blazer", "trousers"): 12,
    ("trousers", "blazer"): 12,
    ("formal_shirt", "trousers"): 12,
    ("trousers", "formal_shirt"): 12,
    ("t-shirt", "sneaker"): 8,
    ("sneaker", "t-shirt"): 8,
    ("dress", "heel"): 12,
    ("heel", "dress"): 12,
    ("sport", "shorts"): 10,
    ("shorts", "sport"): 10,
}

BAD_COMBOS: Dict[Tuple[str, str], int] = {
    ("blazer", "shorts"): -15,
    ("shorts", "blazer"): -15,
    ("formal_shirt", "slide"): -15,
    ("slide", "formal_shirt"): -15,
    ("hoodie", "heel"): -10,
    ("heel", "hoodie"): -10,
    ("blazer", "slide"): -12,
    ("slide", "blazer"): -12,
    ("formal_shirt", "shorts"): -12,
    ("shorts", "formal_shirt"): -12,
    ("hoodie", "trousers"): -5,
    ("trousers", "hoodie"): -5,
}

# ── Hard constraints (score = 0) ────────────────────────────────────
HARD_CONSTRAINTS: Dict[str, Set[str]] = {
    "gym":          {"blazer", "formal_shirt", "heel", "jeans", "trousers"},
    "formal_event": {"shorts", "slide", "hoodie", "sweatshirt", "casual"},
    "office":       {"slide", "shorts"},
}

# ── Forbidden YOLO classes per occasion (for wardrobe filtering) ────
FORBIDDEN_ANY_YOLO: Dict[str, Set[str]] = {
    "formal_event": {"t-shirt", "hoodie", "shorts", "sneaker", "sport", "slide", "casual", "sweatshirt"},
    "office":       {"shorts", "slide", "hoodie", "t-shirt", "sneaker", "sweatshirt"},
    "party":        {"slide", "shorts"},
    "date_night":   {"hoodie", "shorts", "slide", "sweatshirt"},
    "casual_day":   {"heel"},
    "gym":          {"jeans", "boot", "heel", "blazer", "formal_shirt"},
    "travel":       {"heel"},
}

# ── Occasion scoring tables (combo → points out of 50) ──────────────
def _occasion_score(occ: str, ct: str, cb: str, cs: str) -> Tuple[int, List[str]]:
    """Return (points_out_of_50, list_of_penalty_reasons)."""
    pts = 0
    penalties: List[str] = []

    if occ == "formal_event":
        if ct == "blazer" and cb == "trousers":
            pts = 50
        elif ct == "formal_shirt" and cb == "trousers":
            pts = 45
        elif ct == "formal_shirt":
            pts = 40
        elif ct in ("cardigan", "vest") and cb == "trousers":
            pts = 30
        elif ct in TOPS:
            pts = 15
        if cs == "sneaker" or cs == "sport":
            pts = max(0, pts - 30); penalties.append("Sneakers are not appropriate for formal events")
        if cb == "shorts":
            pts = max(0, pts - 40); penalties.append("Shorts are not allowed at formal events")
        if cs in ("heel", "boot"):
            pts = min(50, pts + 5)

    elif occ == "office":
        if ct == "formal_shirt" and cb == "trousers":
            pts = 45
        elif ct == "blazer" and cb == "jeans":
            pts = 35
        elif ct == "blazer" and cb == "trousers":
            pts = 45
        elif ct in ("formal_shirt", "longsleeve") and cb == "jeans":
            pts = 30
        elif ct in ("longsleeve", "cardigan", "sweaters", "pullover", "vest", "top") and cb == "trousers":
            pts = 35  # smart-casual office: collared/knit top with trousers
        elif ct == "t-shirt" and cb == "jeans":
            pts = 20
        elif ct in TOPS and cb in BOTTOMS:
            pts = 15
        if ct == "hoodie":
            pts = max(0, pts - 25); penalties.append("Hoodies are too casual for office")
        if cs == "slide":
            pts = max(0, pts - 30); penalties.append("Slides are not office-appropriate")

    elif occ == "casual_day":
        if ct == "t-shirt" and cb == "jeans" and cs == "sneaker":
            pts = 40
        elif ct in ("t-shirt", "casual") and cb == "jeans":
            pts = 35
        elif ct == "hoodie" and cb == "jeans":
            pts = 35
        elif ct in ("t-shirt", "casual") and cb == "shorts":
            pts = 25
        elif ct == "hoodie" and cb in ("jeans", "shorts", "trousers"):
            pts = 30
        elif ct in TOPS and cb in BOTTOMS:
            pts = 20
        # Penalty for overly formal
        if ct == "blazer" and cs == "heel":
            pts = max(0, pts - 10); penalties.append("Too formal for a casual day")

    elif occ == "party":
        if ct == "dress" and cs == "heel":
            pts = 50
        elif ct == "blazer" and cb in ("jeans", "trousers"):
            pts = 45
        elif ct == "dress":
            pts = 42
        elif ct in ("blazer", "vest") and cb == "trousers":
            pts = 40
        elif ct in ("formal_shirt", "longsleeve") and cb in ("jeans", "trousers"):
            pts = 35
        elif ct == "hoodie" and cb in ("jeans", "trousers"):
            pts = 30
        elif ct == "t-shirt" and cb == "jeans":
            pts = 20; penalties.append("Plain t-shirt + jeans is too basic for a party")
        elif ct in TOPS and cb in BOTTOMS:
            pts = 22

    elif occ == "date_night":
        if ct == "blazer" and cb == "trousers":
            pts = 50
        elif ct == "dress" and cs == "heel":
            pts = 48
        elif ct == "blazer" and cb == "jeans":
            pts = 45
        elif ct == "dress":
            pts = 43
        elif ct in ("formal_shirt", "longsleeve") and cb in ("jeans", "trousers"):
            pts = 40
        elif ct in ("cardigan", "sweaters", "pullover") and cb in ("jeans", "trousers"):
            pts = 35
        elif ct in TOPS and cb in BOTTOMS:
            pts = 20
        if cb == "shorts":
            pts = max(0, pts - 25); penalties.append("Shorts are too casual for date night")
        if cs == "slide":
            pts = max(0, pts - 30); penalties.append("Slides are not date-night appropriate")

    elif occ == "gym":
        if ct in ("sport", "t-shirt") and cb == "shorts" and cs in ("sneaker", "sport"):
            pts = 50
        elif ct == "t-shirt" and cb == "shorts":
            pts = 40
        elif ct == "t-shirt" and cb == "trousers" and cs in ("sneaker", "sport"):
            pts = 35
        elif ct in TOPS and cb in BOTTOMS:
            pts = 10
        if ct == "blazer":
            pts = 0; penalties.append("Blazer is completely wrong for gym")
        if cb == "jeans":
            pts = max(0, pts - 40); penalties.append("Jeans are restrictive for gym workouts")

    elif occ == "travel":
        if ct == "hoodie" and cb in ("jeans", "trousers"):
            pts = 45
        elif ct in ("t-shirt", "casual") and cb == "jeans" and cs in ("sneaker", "sport"):
            pts = 40
        elif ct == "sweatshirt" and cs in ("sneaker", "sport"):
            pts = 35
        elif ct in ("t-shirt", "hoodie", "sweatshirt") and cb in ("jeans", "trousers"):
            pts = 35
        elif ct in TOPS and cb in BOTTOMS:
            pts = 20
        if cs == "heel":
            pts = max(0, pts - 20); penalties.append("Heels are impractical for travel")

    return pts, penalties


def _style_match_score(occ: str, ct: str, cb: str, cs: str) -> int:
    """Score 0–20 based on formality alignment with occasion."""
    target = OCCASION_FORMALITY.get(occ, 3)
    pieces = [p for p in (ct, cb, cs) if p]
    if not pieces:
        return 0
    avg_formality = sum(FORMALITY.get(p, 3) for p in pieces) / len(pieces)
    diff = abs(target - avg_formality)
    if diff <= 0.5:
        return 20
    elif diff <= 1.0:
        return 15
    elif diff <= 1.5:
        return 10
    elif diff <= 2.5:
        return 5
    return 0


def _color_harmony_score(top_color: str, bottom_color: str, shoes_color: str) -> Tuple[int, List[str]]:
    """Score 0–15 for color harmony."""
    tc = _base(top_color)
    bc = _base(bottom_color)
    sc = _base(shoes_color)
    pts = 0
    notes: List[str] = []
    colors = [c for c in (tc, bc, sc) if c]

    if not colors or len(colors) < 2:
        return 5, []

    # Neutral combos bonus
    neutrals_used = sum(1 for c in colors if c in NEUTRALS)
    if neutrals_used >= 2:
        pts += 10
    elif neutrals_used == 1:
        pts += 5

    # Top-bottom harmony
    if tc and bc:
        if tc == bc:
            pts += 3  # monochrome OK
        elif bc in COLOR_COMPAT.get(tc, set()):
            pts += 5
        else:
            pts -= 8
            notes.append(f"Top ({top_color}) and bottom ({bottom_color}) colors may clash")

    # Bottom-shoes harmony
    if bc and sc:
        if sc in COLOR_COMPAT.get(bc, set()) or sc == bc:
            pts += 2
        else:
            pts -= 3
            notes.append(f"Shoes ({shoes_color}) could pair better with bottom ({bottom_color})")

    return max(0, min(15, pts)), notes


def _compatibility_score(ct: str, cb: str, cs: str) -> Tuple[int, List[str]]:
    """Score 0–15 from combo matrix."""
    pts = 0
    notes: List[str] = []
    pairs = [(ct, cb), (ct, cs), (cb, cs)]
    for a, b in pairs:
        if not a or not b:
            continue
        good = GOOD_COMBOS.get((a, b), 0)
        bad = BAD_COMBOS.get((a, b), 0)
        if good:
            pts += good
        if bad:
            pts += bad  # bad values are already negative
            notes.append(f"{a} + {b} is a poor combination")
    return max(0, min(15, pts)), notes


def _check_hard_constraints(occ: str, ct: str, cb: str, cs: str) -> Optional[str]:
    """Return reason string if hard constraint violated, else None."""
    forbidden = HARD_CONSTRAINTS.get(occ, set())
    for piece, role in ((ct, "top"), (cb, "bottom"), (cs, "shoes")):
        if piece and piece in forbidden:
            return f"{piece} is absolutely not allowed for {occ.replace('_', ' ')} — score zeroed"
    return None


# ── Wardrobe filtering ──────────────────────────────────────────────
_SUPPORTED_OCC = frozenset(
    {"formal_event", "office", "party", "date_night", "casual_day", "gym", "travel"}
)

def filter_wardrobe_for_occasion(
    wardrobe: List[Dict[str, Any]],
    occasion: str,
    gender: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Drop items that can never belong on this occasion."""
    occ = (occasion or "").lower()
    fb_yolo = FORBIDDEN_ANY_YOLO.get(occ, set())
    g = (gender or "").lower().strip()
    out: List[Dict[str, Any]] = []
    for item in wardrobe:
        if item.get("status") != "available":
            continue
        cat = _cls(item)
        if cat in fb_yolo:
            continue
        if occ == "formal_event" and g in ("male", "m", "man", "men") and cat == "heel":
            continue
        out.append(item)
    return out


# ── Priority-ordered suggestions ────────────────────────────────────
# Occasion → {slot: set of ideal classes}
IDEAL_CLASSES: Dict[str, Dict[str, Set[str]]] = {
    "formal_event": {
        "top": {"blazer", "formal_shirt", "vest"},
        "bottom": {"trousers", "skirt", "dress"},
        "shoes": {"boot", "heel"},
    },
    "office": {
        "top": {"formal_shirt", "longsleeve", "blazer", "cardigan", "vest"},
        "bottom": {"trousers", "skirt"},
        "shoes": {"boot", "heel"},
    },
    "casual_day": {
        "top": {"t-shirt", "hoodie", "sweatshirt", "pullover", "sweaters", "cardigan", "top", "longsleeve"},
        "bottom": {"jeans", "shorts"},
        "shoes": {"sneaker", "slide"},
    },
    "party": {
        "top": {"blazer", "formal_shirt", "dress", "vest", "longsleeve", "t-shirt", "cardigan"},
        "bottom": {"jeans", "trousers", "skirt"},
        "shoes": {"boot", "sneaker", "heel"},
    },
    "date_night": {
        "top": {"blazer", "formal_shirt", "longsleeve", "cardigan", "sweaters", "vest", "pullover", "dress", "t-shirt"},
        "bottom": {"jeans", "trousers", "skirt"},
        "shoes": {"boot", "heel", "sneaker"},
    },
    "gym": {
        "top": {"t-shirt", "sport", "sweatshirt", "hoodie"},
        "bottom": {"shorts"},
        "shoes": {"sneaker"},
    },
    "travel": {
        "top": {"t-shirt", "hoodie", "sweatshirt", "cardigan", "pullover"},
        "bottom": {"jeans", "shorts"},
        "shoes": {"sneaker", "slide"},
    },
}


def _build_priority_suggestions(
    occ: str, ct: str, cb: str, cs: str, has_acc: bool,
) -> List[str]:
    """
    Build suggestions in strict priority: Top → Bottom → Shoes → Accessory.
    Only suggest for slots that DON'T already match the occasion.
    """
    ideal = IDEAL_CLASSES.get(occ, {})
    suggestions: List[str] = []
    label = occ.replace("_", " ").title()

    # 1. Top
    ideal_tops = ideal.get("top", set())
    if not ct:
        suggestions.append(f"Add a top for {label}: try {', '.join(sorted(ideal_tops)[:3])}")
    elif ideal_tops and ct not in ideal_tops:
        suggestions.append(f"Replace {ct} with {' or '.join(sorted(ideal_tops)[:2])} for {label}")

    # 2. Bottom
    ideal_bottoms = ideal.get("bottom", set())
    if not cb:
        suggestions.append(f"Add a bottom for {label}: try {', '.join(sorted(ideal_bottoms)[:3])}")
    elif ideal_bottoms and cb not in ideal_bottoms:
        suggestions.append(f"Replace {cb} with {' or '.join(sorted(ideal_bottoms)[:2])} for {label}")

    # 3. Shoes
    ideal_shoes = ideal.get("shoes", set())
    if not cs:
        suggestions.append(f"Add footwear for {label}: try {', '.join(sorted(ideal_shoes)[:3])}")
    elif ideal_shoes and cs not in ideal_shoes:
        suggestions.append(f"Replace {cs} with {' or '.join(sorted(ideal_shoes)[:2])} for {label}")

    # 4. Accessory (only for occasions that benefit)
    if occ in ("party", "date_night", "formal_event") and not has_acc:
        suggestions.append(f"Add an accessory (watch or belt) to complete the {label} look")

    return suggestions


# ── Main scoring function ───────────────────────────────────────────
def validate_and_score(
    occasion: str,
    outfit: Dict[str, Any],
    gender: Optional[str] = None,
) -> Tuple[List[str], List[str], float, Dict[str, Any]]:
    """
    100-point scoring → returned as 0–10 scale.
    Returns (issues, suggestions, score_out_of_10, debug_meta).
    """
    occ = (occasion or "casual_day").lower()
    if occ not in _SUPPORTED_OCC:
        return (
            [f"Unknown occasion {occasion}"],
            ["Pick a supported occasion"],
            0.0,
            {"unsupported": True},
        )

    top = outfit.get("top")
    bottom = outfit.get("bottom")
    shoes = outfit.get("shoes")
    acc = outfit.get("accessory")

    ct, cb, cs = _cls(top), _cls(bottom), _cls(shoes)
    tc, bc, sc = _color(top), _color(bottom), _color(shoes)
    has_acc = bool(acc and _cls(acc))

    issues: List[str] = []

    # ── Hard constraints check ──
    hard = _check_hard_constraints(occ, ct, cb, cs)
    if hard:
        suggestions = _build_priority_suggestions(occ, ct, cb, cs, has_acc)
        return [hard], suggestions, 0.0, {
            "hard_constraint": True,
            "occasion_pts": 0, "style_pts": 0,
            "color_pts": 0, "compat_pts": 0, "total_100": 0,
        }

    # ── Empty outfit ──
    if not ct and not cb and not cs:
        return (
            ["No outfit provided"],
            _build_priority_suggestions(occ, "", "", "", False),
            0.0,
            {"empty": True, "total_100": 0},
        )

    # ── 1. Occasion score (0–50) ──
    occ_pts, occ_penalties = _occasion_score(occ, ct, cb, cs)
    issues.extend(occ_penalties)

    # Missing slot penalties within occasion scoring
    if not ct:
        occ_pts = max(0, occ_pts - 15)
        issues.append(f"Missing top for {occ.replace('_', ' ').title()}")
    if not cb and ct != "dress":
        occ_pts = max(0, occ_pts - 15)
        issues.append(f"Missing bottom for {occ.replace('_', ' ').title()}")
    if not cs:
        occ_pts = max(0, occ_pts - 10)
        issues.append(f"Missing shoes for {occ.replace('_', ' ').title()}")

    # ── 2. Style match (0–20) ──
    style_pts = _style_match_score(occ, ct, cb, cs)

    # ── 3. Color harmony (0–15) ──
    color_pts, color_notes = _color_harmony_score(tc, bc, sc)
    issues.extend(color_notes)

    # ── 4. Compatibility (0–15) ──
    compat_pts, compat_notes = _compatibility_score(ct, cb, cs)
    issues.extend(compat_notes)

    # ── Total ──
    total_100 = occ_pts + style_pts + color_pts + compat_pts
    total_100 = max(0, min(100, total_100))

    # Scale to 0–10
    score_10 = round(total_100 / 10.0, 1)

    # Priority-ordered suggestions
    suggestions = _build_priority_suggestions(occ, ct, cb, cs, has_acc)

    meta = {
        "occasion_pts": occ_pts,
        "style_pts": style_pts,
        "color_pts": color_pts,
        "compat_pts": compat_pts,
        "total_100": total_100,
    }
    return issues, suggestions, score_10, meta
