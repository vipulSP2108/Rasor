"""Production-Grade Semantic Color & Relational Garment Pairing Engine.

Grounded in human perceptual color science (CIELAB / LCh) and seasonal color analysis.
Decouples:
1. Personalization Layer: User Monk Skin Tone (1-10) + Undertone -> Flattering Palette (Soft Boost).
2. Product Compatibility Layer: Pairing-Type Taxonomy with Config-Driven Weight Table
   over 5 Shared Base Perceptual Features.
3. Style Collision Matrix: Hard exclusion rules for incompatible/unrealistic pairings
   (e.g., formal shirt + gym shorts, heavyweight hoodie + summer shorts).
"""

import math
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 1. Canonical Perceptual Color Space (LCh: Lightness 0-100, Chroma 0-100+, Hue 0-360°)
# ---------------------------------------------------------------------------
# L* = Perceived Lightness (0 = black, 100 = pure white)
# C* = Perceived Chroma / Saturation
# h  = Perceptual Hue Angle on the continuous 360° circle
COLOR_PALETTE_LCH: Dict[str, Dict[str, Any]] = {
    "Black":        {"L": 12.0, "C": 2.0,   "h": 0.0,   "is_neutral": True,  "family": "neutral"},
    "White":        {"L": 96.0, "C": 2.0,   "h": 0.0,   "is_neutral": True,  "family": "neutral"},
    "Heather Grey": {"L": 68.0, "C": 4.0,   "h": 0.0,   "is_neutral": True,  "family": "neutral"},
    "Grey":         {"L": 55.0, "C": 4.0,   "h": 0.0,   "is_neutral": True,  "family": "neutral"},
    "Charcoal":     {"L": 28.0, "C": 5.0,   "h": 0.0,   "is_neutral": True,  "family": "neutral"},
    "Dark Navy":    {"L": 22.0, "C": 26.0,  "h": 265.0, "is_neutral": True,  "family": "cool"},
    "Navy":         {"L": 25.0, "C": 30.0,  "h": 265.0, "is_neutral": True,  "family": "cool"},
    "Blue":         {"L": 48.0, "C": 55.0,  "h": 250.0, "is_neutral": False, "family": "cool"},
    "Cyan":         {"L": 65.0, "C": 45.0,  "h": 200.0, "is_neutral": False, "family": "cool"},
    "Sand Beige":   {"L": 82.0, "C": 18.0,  "h": 85.0,  "is_neutral": True,  "family": "warm"},
    "Beige":        {"L": 80.0, "C": 20.0,  "h": 85.0,  "is_neutral": True,  "family": "warm"},
    "Brown":        {"L": 38.0, "C": 32.0,  "h": 45.0,  "is_neutral": True,  "family": "warm"},
    "Olive Green":  {"L": 45.0, "C": 32.0,  "h": 125.0, "is_neutral": False, "family": "warm"},
    "Green":        {"L": 52.0, "C": 50.0,  "h": 135.0, "is_neutral": False, "family": "warm"},
    "Deep Maroon":  {"L": 32.0, "C": 42.0,  "h": 15.0,  "is_neutral": False, "family": "warm"},
    "Maroon":       {"L": 35.0, "C": 44.0,  "h": 18.0,  "is_neutral": False, "family": "warm"},
    "Red":          {"L": 50.0, "C": 75.0,  "h": 25.0,  "is_neutral": False, "family": "warm"},
    "Orange":       {"L": 62.0, "C": 78.0,  "h": 45.0,  "is_neutral": False, "family": "warm"},
    "Yellow":       {"L": 85.0, "C": 80.0,  "h": 90.0,  "is_neutral": False, "family": "warm"},
    "Mustard":      {"L": 68.0, "C": 58.0,  "h": 75.0,  "is_neutral": False, "family": "warm"},
    "Cobalt Blue":  {"L": 42.0, "C": 65.0,  "h": 270.0, "is_neutral": False, "family": "cool"},
    "Multi":        {"L": 50.0, "C": 20.0,  "h": 0.0,   "is_neutral": True,  "family": "neutral"},
    "Any":          {"L": 50.0, "C": 10.0,  "h": 0.0,   "is_neutral": True,  "family": "neutral"},
}


def resolve_lch_color(color_name: Optional[str]) -> Dict[str, Any]:
    """Resolves arbitrary color string to nearest canonical LCh vector."""
    if not color_name:
        return COLOR_PALETTE_LCH["Black"]
    cleaned = str(color_name).strip().title()
    if cleaned in COLOR_PALETTE_LCH:
        return COLOR_PALETTE_LCH[cleaned]
    # Substring matching
    cl_lower = cleaned.lower()
    for name, data in COLOR_PALETTE_LCH.items():
        if name.lower() in cl_lower or cl_lower in name.lower():
            return data
    return COLOR_PALETTE_LCH["Black"]


# ---------------------------------------------------------------------------
# 2. Perceptual Distance (CIEDE2000 Simplified Fast Formulation)
# ---------------------------------------------------------------------------

def ciede2000_distance(c1: Dict[str, Any], c2: Dict[str, Any]) -> float:
    """Computes perceptual color distance Delta-E (dE2000).
    A Delta-E <= 12 indicates highly perceptually harmonious or closely echoing colors.
    """
    dL = abs(c1["L"] - c2["L"])
    dC = abs(c1["C"] - c2["C"])
    
    # Hue difference on 360 circle
    dh = abs(c1["h"] - c2["h"])
    if dh > 180:
        dh = 360 - dh
    dh_rad = math.radians(dh)
    
    # Mean chroma
    c_mean = (c1["C"] + c2["C"]) / 2.0
    # Cylindrical Euclidean-distance with perceptual weighting
    dH2 = 2.0 * c1["C"] * c2["C"] * (1.0 - math.cos(dh_rad)) if c_mean > 0 else 0.0
    dH = math.sqrt(max(0.0, dH2))
    
    # Weight factors: lightness has high perceptual sensitivity
    sL = 1.0 + (0.015 * (c1["L"] - 50)**2) / math.sqrt(20 + (c1["L"] - 50)**2) if c1["L"] != 50 else 1.0
    sC = 1.0 + 0.045 * c_mean
    sH = 1.0 + 0.015 * c_mean
    
    de = math.sqrt((dL / sL)**2 + (dC / sC)**2 + (dH / sH)**2)
    return round(de, 2)


# ---------------------------------------------------------------------------
# 3. Category Zones & Pairing-Type Taxonomy
# ---------------------------------------------------------------------------

CATEGORY_ZONE_MAP: Dict[str, str] = {
    # Outerwear
    "hoodie": "outerwear",
    "sweatshirt": "outerwear",
    "jacket": "outerwear",
    "shrug": "outerwear",
    "overshirt": "outerwear",
    # Tops / Uppers
    "t-shirt": "top",
    "shirt": "top",
    "polo": "top",
    "vest": "top",
    "top": "top",
    # Bottoms / Lowers
    "joggers": "bottom",
    "jeans": "bottom",
    "trousers": "bottom",
    "pants": "bottom",
    "shorts": "bottom",
    "cargo pants": "bottom",
    # Footwear
    "sliders": "footwear",
    "footwear": "footwear",
    "sneakers": "footwear",
    "shoes": "footwear",
}


def derive_pairing_type(item1: Dict[str, Any], item2: Dict[str, Any]) -> str:
    """Derives pairing type: 'layering', 'top_bottom', 'solid_pattern', 'footwear_outfit'."""
    cat1 = str(item1.get("category", "")).lower()
    cat2 = str(item2.get("category", "")).lower()
    
    zone1 = CATEGORY_ZONE_MAP.get(cat1, "top")
    zone2 = CATEGORY_ZONE_MAP.get(cat2, "bottom")
    
    # Pattern check
    des1 = str(item1.get("design", "")).lower()
    des2 = str(item2.get("design", "")).lower()
    is_pattern1 = "print" in des1 or "graphic" in des1 or "washed" in des1
    is_pattern2 = "print" in des2 or "graphic" in des2 or "washed" in des2
    is_solid1 = "solid" in des1 or not is_pattern1
    is_solid2 = "solid" in des2 or not is_pattern2
    
    # Layering: Outerwear + Top (e.g. Hoodie over T-shirt)
    if (zone1 == "outerwear" and zone2 == "top") or (zone1 == "top" and zone2 == "outerwear"):
        return "layering"
        
    # Footwear pairing
    if zone1 == "footwear" or zone2 == "footwear":
        return "footwear_outfit"
        
    # Solid + Pattern check
    if (is_solid1 and is_pattern2) or (is_pattern1 and is_solid2):
        return "solid_pattern"
        
    # Default top-bottom coordination
    return "top_bottom"


# ---------------------------------------------------------------------------
# 4. Style Collision & Incompatibility Matrix (Hard Exclusions)
# ---------------------------------------------------------------------------
# Pairs that are fundamentally clashing in formality, lifestyle, or thermal function.

BANNED_STYLE_COLLISIONS: List[Tuple[str, str, str]] = [
    # (Category 1, Category 2, Reason)
    ("shirt", "shorts", "Formality Clash: Crisp button-down shirts do not pair with athletic gym shorts."),
    ("hoodie", "shorts", "Seasonal/Thermal Clash: Heavyweight winter fleece upper with bare summer legs."),
    ("shirt", "sliders", "Formality Clash: Tailored smart-casual top with casual beach sliders."),
    ("vest", "trousers", "Occasion Clash: Workout athletic tank with tailored dress trousers."),
    ("shirt", "joggers", "Fabric Clash: Formal woven button-down with athletic fleece sweatpants."),
]


def check_style_collision(cat1: str, cat2: str, design1: str = "", design2: str = "") -> Optional[str]:
    """Returns ban reason if pair is fundamentally incompatible, else None."""
    c1 = cat1.lower().strip()
    c2 = cat2.lower().strip()
    
    def is_cat(target: str, cat_str: str) -> bool:
        if target == "shirt":
            return "shirt" in cat_str and "t-shirt" not in cat_str and "tshirt" not in cat_str and "tee" not in cat_str
        return target in cat_str

    for b1, b2, reason in BANNED_STYLE_COLLISIONS:
        if (is_cat(b1, c1) and is_cat(b2, c2)) or (is_cat(b2, c1) and is_cat(b1, c2)):
            # Exception: Linen/casual shirts can pair with tailored chino shorts, but formal/oxford shirts cannot
            if "shorts" in (c1 + c2):
                if "linen" in (design1 + design2).lower():
                    continue
            return reason
            
    return None


# ---------------------------------------------------------------------------
# 5. Shared Base Perceptual Features (0.0 to 1.0)
# ---------------------------------------------------------------------------

def compute_hue_harmony(c1: Dict[str, Any], c2: Dict[str, Any]) -> float:
    """Evaluates LCh hue angle distance. Rewards complementary and analogous hues."""
    if c1["is_neutral"] or c2["is_neutral"]:
        return 1.0  # Neutrals harmonize universally
        
    dh = abs(c1["h"] - c2["h"])
    if dh > 180:
        dh = 360 - dh
        
    # Analogous (<= 50 degrees): Peaceful, cohesive
    if dh <= 50:
        return 1.0
    # Complementary (150 to 180 degrees): Bold contrast
    elif 150 <= dh <= 180:
        return 0.95
    # Split-Complementary / Triadic (110 to 140 degrees)
    elif 110 <= dh <= 140:
        return 0.80
    # Awkward clash zone between two saturated non-neutrals (60 to 100 degrees)
    else:
        return 0.20


def compute_value_contrast(c1: Dict[str, Any], c2: Dict[str, Any]) -> float:
    """Absolute Lightness contrast / 100. High contrast creates clean visual separation."""
    return round(abs(c1["L"] - c2["L"]) / 100.0, 3)


def compute_chroma_compatibility(c1: Dict[str, Any], c2: Dict[str, Any]) -> float:
    """Evaluates saturation. Two bold, high-chroma colors fight; bold + muted works great."""
    if c1["C"] > 45 and c2["C"] > 45 and not (c1["is_neutral"] or c2["is_neutral"]):
        return 0.20  # Clash penalty for two competing neon/loud colors
    return 1.0


def compute_neutral_bonus(c1: Dict[str, Any], c2: Dict[str, Any]) -> float:
    """1.0 if either piece is a recognized neutral anchor."""
    return 1.0 if (c1["is_neutral"] or c2["is_neutral"]) else 0.0


def compute_pattern_echo(item1: Dict[str, Any], item2: Dict[str, Any], c1: Dict[str, Any], c2: Dict[str, Any]) -> float:
    """Checks whether a solid item's color echoes in the pattern's palette."""
    de = ciede2000_distance(c1, c2)
    if de <= 12.0:
        return 1.0
    elif de <= 20.0:
        return 0.70
    return 0.30


# ---------------------------------------------------------------------------
# 6. Config-Driven Pairing Weight Table
# ---------------------------------------------------------------------------

PAIRING_WEIGHT_CONFIG: Dict[str, Dict[str, float]] = {
    # Layering (Hoodie over T-shirt): Collar/hem light-dark contrast and neutral bonus dominate
    "layering": {
        "hue_harmony": 0.20,
        "value_contrast": 0.35,
        "chroma_comp": 0.15,
        "neutral_bonus": 0.30,
        "pattern_echo": 0.00,
    },
    # Top + Bottom: 60-30-10 rule. Value contrast & hue harmony drive overall balance
    "top_bottom": {
        "hue_harmony": 0.30,
        "value_contrast": 0.30,
        "chroma_comp": 0.20,
        "neutral_bonus": 0.20,
        "pattern_echo": 0.00,
    },
    # Solid + Pattern: Echoing an accent color inside the print is the #1 style driver
    "solid_pattern": {
        "hue_harmony": 0.10,
        "value_contrast": 0.15,
        "chroma_comp": 0.15,
        "neutral_bonus": 0.10,
        "pattern_echo": 0.50,
    },
    # Footwear + Outfit: Neutral grounding or echoing top piece
    "footwear_outfit": {
        "hue_harmony": 0.25,
        "value_contrast": 0.20,
        "chroma_comp": 0.15,
        "neutral_bonus": 0.40,
        "pattern_echo": 0.00,
    }
}


# ---------------------------------------------------------------------------
# 7. Personalization Layer: Monk Skin Tone & Flattering Palette Soft Boost
# ---------------------------------------------------------------------------

def evaluate_skin_tone_boost(
    top_color_name: str,
    skin_depth: Optional[int] = None,
    undertone: Optional[str] = None
) -> float:
    """Computes a gentle positive score boost (+0.0 to +0.15) for top piece closest to face.
    Completely optional; returns 0.0 if user has not set a skin profile.
    """
    if not skin_depth and (not undertone or str(undertone).lower() in ["none", "any", "skip", "null"]):
        return 0.0
        
    c = resolve_lch_color(top_color_name)
    color_fam = c.get("family", "neutral")
    depth = skin_depth
    ut = str(undertone or "").lower()
    
    boost = 0.0
    
    # 1. Undertone affinity (only if specified and not any/none)
    if ut and ut not in ["none", "any", "skip", "null"]:
        if "warm" in ut:
            if color_fam == "warm" or top_color_name in ["Olive Green", "Mustard", "Sand Beige", "Deep Maroon", "White"]:
                boost += 0.08
        elif "cool" in ut:
            if color_fam == "cool" or top_color_name in ["Dark Navy", "Cobalt Blue", "Deep Maroon", "Charcoal", "White"]:
                boost += 0.08
        else:  # Neutral / Olive
            if top_color_name in ["Olive Green", "Dark Navy", "Sand Beige", "Charcoal", "Heather Grey", "White"]:
                boost += 0.08
            
    # 2. Depth value contrast
    # Deep skin (MST 8-10) thrives in high lightness vibrancy
    if depth >= 8 and c["L"] >= 75:
        boost += 0.07
    # Fair skin (MST 1-3) thrives in anchoring deep tones
    elif depth <= 3 and c["L"] <= 45 and c["C"] >= 20:
        boost += 0.07
    # Medium skin (MST 4-7) thrives in balanced earth tones
    elif 4 <= depth <= 7 and (25 <= c["L"] <= 85):
        boost += 0.05
        
    return min(0.15, round(boost, 3))


# ---------------------------------------------------------------------------
# 8. Full Garment Pair Scorer (Returns Total + Explainable Sub-Scores)
# ---------------------------------------------------------------------------

def score_garment_pairing(
    item1: Dict[str, Any],
    item2: Dict[str, Any],
    user_skin_depth: Optional[int] = None,
    user_undertone: Optional[str] = None
) -> Dict[str, Any]:
    """Scores compatibility between item1 and item2 using the perceptual framework.
    Returns:
      - is_compatible: bool (False if hard style collision detected)
      - collision_reason: Optional[str]
      - total_score: float (0.0 to 1.0)
      - pairing_type: str ('layering', 'top_bottom', 'solid_pattern', 'footwear_outfit')
      - sub_scores: Dict[str, float]
    """
    cat1 = str(item1.get("category", "")).lower()
    cat2 = str(item2.get("category", "")).lower()
    des1 = str(item1.get("design", ""))
    des2 = str(item2.get("design", ""))
    
    # Check Style Collision
    collision = check_style_collision(cat1, cat2, des1, des2)
    if collision:
        return {
            "is_compatible": False,
            "collision_reason": collision,
            "total_score": 0.0,
            "pairing_type": "incompatible",
            "sub_scores": {}
        }
        
    pairing_type = derive_pairing_type(item1, item2)
    weights = PAIRING_WEIGHT_CONFIG.get(pairing_type, PAIRING_WEIGHT_CONFIG["top_bottom"])
    
    c1 = resolve_lch_color(item1.get("color"))
    c2 = resolve_lch_color(item2.get("color"))
    
    hue_harm = compute_hue_harmony(c1, c2)
    val_cont = compute_value_contrast(c1, c2)
    chroma = compute_chroma_compatibility(c1, c2)
    neutral = compute_neutral_bonus(c1, c2)
    echo = compute_pattern_echo(item1, item2, c1, c2)
    
    base_score = (
        weights["hue_harmony"] * hue_harm +
        weights["value_contrast"] * val_cont +
        weights["chroma_comp"] * chroma +
        weights["neutral_bonus"] * neutral +
        weights["pattern_echo"] * echo
    )
    
    # Personalization boost applied to top piece
    top_color = item1.get("color") if CATEGORY_ZONE_MAP.get(cat1) in ["outerwear", "top"] else item2.get("color")
    skin_boost = evaluate_skin_tone_boost(top_color, user_skin_depth, user_undertone)
    
    total_score = min(1.0, round(base_score + skin_boost, 3))
    
    return {
        "is_compatible": True,
        "collision_reason": None,
        "total_score": total_score,
        "pairing_type": pairing_type,
        "sub_scores": {
            "hue_harmony": round(hue_harm, 2),
            "value_contrast": round(val_cont, 2),
            "chroma_comp": round(chroma, 2),
            "neutral_bonus": round(neutral, 2),
            "pattern_echo": round(echo, 2),
            "skin_boost": round(skin_boost, 2)
        }
    }


# ---------------------------------------------------------------------------
# 9. Plain-Text Stylist Rationale Generator
# ---------------------------------------------------------------------------

def _extract_display_color(item: Dict[str, Any], default: str = "Tonal") -> str:
    """Extracts human-readable color from item metadata or title."""
    c = item.get("color")
    if c and str(c).lower() not in ["neutral", "any", "none", ""]:
        return str(c).title()
    specs = item.get("specs") or {}
    if specs.get("color") and str(specs["color"]).lower() not in ["neutral", "any", "none", ""]:
        return str(specs["color"]).title()
    title = str(item.get("title") or item.get("name") or "").lower()
    for col in ["olive green", "dark navy", "navy blue", "jet black", "charcoal grey", "heather grey", "off-white", "light blue", "sand beige", "black", "white", "grey", "olive", "navy", "beige", "maroon", "charcoal", "brown", "blue", "indigo"]:
        if col in title:
            return col.title()
    return default


def generate_stylist_rationale(
    item1: Dict[str, Any],
    item2: Dict[str, Any],
    eval_result: Dict[str, Any]
) -> str:
    """Generates natural, articulate plain-text stylist rationale based on sub-scores."""
    if not eval_result.get("is_compatible", True):
        return f"Styling Clash: {eval_result.get('collision_reason', 'Incompatible categories')}."
        
    sub = eval_result.get("sub_scores", {})
    p_type = eval_result.get("pairing_type", "top_bottom")
    c1_name = _extract_display_color(item1)
    c2_name = _extract_display_color(item2)
    cat1 = item1.get("category", "upper")
    cat2 = item2.get("category", "lower")
    
    reasons = []
    
    # 1. Layering specifics
    if p_type == "layering":
        if sub.get("value_contrast", 0) >= 0.45:
            reasons.append(f"The inner {c2_name} tee creates a crisp, intentional contrast peek beneath the {c1_name} {cat1}")
        else:
            reasons.append(f"Creates a cohesive, relaxed tonal layering silhouette between {c1_name} and {c2_name}")
            
    # 2. Solid + Pattern specifics
    elif p_type == "solid_pattern":
        reasons.append(f"The solid {c1_name} {cat1} anchors the graphic artwork on the {c2_name} piece without visual clutter")
        
    # 3. Top-Bottom specifics
    else:
        c1_lch = resolve_lch_color(c1_name)
        c2_lch = resolve_lch_color(c2_name)
        if sub.get("value_contrast", 0) >= 0.38:
            reasons.append(f"High-contrast balance: {c1_name} upper is neatly anchored by the deep {c2_name} {cat2}")
        elif c1_lch["is_neutral"] or c2_lch["is_neutral"]:
            neutral_col = c1_name if c1_lch["is_neutral"] else c2_name
            accent_col = c2_name if c1_lch["is_neutral"] else c1_name
            reasons.append(f"{neutral_col} neutral foundation allows the {accent_col} piece to stand out naturally")
        else:
            reasons.append(f"Harmonious {c1_name} and {c2_name} color pairing calibrated for modern streetwear balance")
            
    # 4. Skin Tone enhancement note
    if sub.get("skin_boost", 0) > 0:
        reasons.append("Flattering affinity with your personal undertone palette")
        
    return " · ".join(reasons) + "."
