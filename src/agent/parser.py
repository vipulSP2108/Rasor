"""Intent parsing and entity extraction engine for Agentic Commerce.

Extracts: Gender, Category, Color, Size, Price, Design Pattern, Pop-Culture Fandom, Fit, Sleeve, and Neck styles.
"""

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

_KNOWN_COLORS = [
    "black", "blue", "white", "red", "green", "grey", "gray", "yellow",
    "orange", "maroon", "beige", "brown", "purple", "pink", "navy", "olive", "lavender", "cyan"
]

_KNOWN_CATEGORIES = {
    "t-shirt": ["t-shirt", "tshirt", "tee", "topwear", "vest"],
    "hoodie": ["hoodie", "sweatshirt", "jacket", "pullover"],
    "joggers": ["joggers", "trackpants", "sweatpants", "pajamas"],
    "jeans": ["jeans", "denim", "pants"],
    "shirt": ["shirt", "button up", "formal shirt", "casual shirt"],
    "footwear": ["shoes", "sneakers", "running shoes", "footwear", "sandals"],
    "headphones": ["headphones", "earphones", "earbuds", "audio", "airpods"],
    "monitor": ["monitor", "display", "screen", "4k monitor"]
}

_KNOWN_DESIGNS = {
    "Graphic Print": ["graphic", "printed", "print", "anime", "art print", "graphic print"],
    "Typography": ["typography", "text", "quotes", "slogan", "lettering"],
    "Solid": ["solid", "plain", "basic", "single color", "simple"],
    "Washed": ["washed", "acid wash", "vintage wash", "distressed"],
    "Checked": ["checked", "plaid", "check"],
    "All Over Print": ["all over print", "aop", "patterned"]
}

_KNOWN_FANDOMS = {
    "Marvel": ["marvel", "avengers", "iron man", "spider man", "spiderman", "captain america", "thor", "deadpool"],
    "DC": ["dc", "batman", "dark knight", "superman", "joker", "flash", "gotham"],
    "Harry Potter": ["harry potter", "hogwarts", "gryffindor", "slytherin"],
    "Disney": ["disney", "mickey", "mickey mouse", "donald duck"],
    "Anime / Cartoons": ["anime", "naruto", "dragon ball", "tom and jerry", "tom & jerry", "garfield", "looney tunes", "cartoon"]
}

_KNOWN_FITS = {
    "Oversized Fit": ["oversized", "loose", "baggy", "super baggy", "relaxed"],
    "Boyfriend Fit": ["boyfriend", "boyfriend fit"],
    "Slim Fit": ["slim", "tight"],
    "Regular Fit": ["regular", "standard fit"]
}

_KNOWN_SLEEVES = {
    "Half Sleeve": ["half sleeve", "short sleeve", "half sleeves"],
    "Full Sleeve": ["full sleeve", "long sleeve", "full sleeves"],
    "Sleeveless": ["sleeveless", "vest", "tank top", "tank"]
}

_KNOWN_SIZES = ["3XL", "2XL", "XL", "L", "M", "S", "XS", "10", "9", "8", "11"]


class ParsedShoppingIntent(BaseModel):
    """Structured entity representations parsed from raw user natural language prompts."""
    raw_prompt: str
    cleaned_query: str
    gender: Optional[str] = Field(default=None, description="Target gender (men, women, unisex)")
    category: Optional[str] = Field(default=None, description="Primary product category")
    color: Optional[str] = Field(default=None, description="Target color variant")
    size: Optional[str] = Field(default=None, description="Requested garment or shoe size")
    quantity: Optional[int] = Field(default=None, description="Quantity of items requested")
    max_price: Optional[float] = Field(default=None, description="Budget cap extracted from prompt")
    min_rating: Optional[float] = Field(default=None, description="Minimum review rating requested")
    design: Optional[str] = Field(default=None, description="Design pattern (Graphic Print, Typography, Solid, Washed)")
    fandom: Optional[str] = Field(default=None, description="Merchandise partner / Pop-culture theme (Marvel, DC, Anime, Disney)")
    fit: Optional[str] = Field(default=None, description="Fit preference (Oversized Fit, Regular Fit, Boyfriend Fit)")
    sleeve: Optional[str] = Field(default=None, description="Sleeve type (Half Sleeve, Full Sleeve, Sleeveless)")
    fast_shipping_requested: bool = Field(default=False, description="True if the user requested fast, express, or urgent delivery")
    negative_keywords: List[str] = Field(default_factory=list, description="Keywords explicitly excluded by user")


def parse_user_intent(prompt: str) -> ParsedShoppingIntent:
    """Extracts structured commerce parameters across 10+ dimensions from natural language text."""
    p_lower = prompt.lower()
    
    # 1. Gender Extraction
    gender = None
    if re.search(r"\b(women|woman|ladies|girls|female)\b", p_lower):
        gender = "women"
    elif re.search(r"\b(men|man|guys|boys|male)\b", p_lower):
        gender = "men"
    elif re.search(r"\b(unisex)\b", p_lower):
        gender = "unisex"

    # 2. Color Extraction
    color = None
    for c in _KNOWN_COLORS:
        if re.search(rf"\b{c}\b", p_lower):
            color = c.title()
            break

    # 3. Category Extraction
    category = None
    for cat_name, synonyms in _KNOWN_CATEGORIES.items():
        if any(re.search(rf"\b{syn}\b", p_lower) for syn in synonyms):
            category = cat_name
            break

    # 4. Design Pattern Extraction (Graphic, Typography, Solid/Plain, Washed)
    design = None
    for des_name, synonyms in _KNOWN_DESIGNS.items():
        if any(re.search(rf"\b{syn}\b", p_lower) for syn in synonyms):
            design = des_name
            break

    # 5. Pop-Culture Fandom & Collaboration
    fandom = None
    for fan_name, keywords in _KNOWN_FANDOMS.items():
        if any(re.search(rf"\b{k}\b", p_lower) for k in keywords):
            fandom = fan_name
            break

    # 6. Fit Extraction
    fit = None
    for fit_name, synonyms in _KNOWN_FITS.items():
        if any(re.search(rf"\b{syn}\b", p_lower) for syn in synonyms):
            fit = fit_name
            break

    # 7. Sleeve Extraction
    sleeve = None
    for slv_name, synonyms in _KNOWN_SLEEVES.items():
        if any(re.search(rf"\b{syn}\b", p_lower) for syn in synonyms):
            sleeve = slv_name
            break

    # 8. Size Extraction
    size = None
    for s in _KNOWN_SIZES:
        if re.search(rf"\b(size\s*[:=]?\s*{s}|in\s+{s}|{s}\s+size)\b", prompt, re.IGNORECASE):
            size = s
            break

    # 9. Price Extraction
    max_price = None
    price_match = re.search(r"(?:under|below|less than|within|<|<=)\s*(?:rs\.?|inr|\$)?\s*(\d+(?:,\d+)?(?:\.\d+)?)", p_lower)
    if price_match:
        try:
            max_price = float(price_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # 10. Rating Extraction
    min_rating = None
    rating_match = re.search(r"(?:rating|stars?|rated)\s*(?:above|>|>=)?\s*(\d(?:\.\d)?)", p_lower)
    if rating_match:
        try:
            min_rating = float(rating_match.group(1))
        except ValueError:
            pass

    # 11. Fast Shipping Extraction
    fast_shipping_requested = bool(re.search(r"\b(fast|quick|urgent|express|rapid|early|soon)\b", p_lower))

    # 11.5 Negative Keywords Extraction
    negative_keywords = []
    neg_matches = re.findall(r"\b(?:not|no|without|except|non|minus)\s+([a-zA-Z0-9]+)\b", p_lower)
    if neg_matches:
        negative_keywords = list(set(neg_matches))

    # 12. Clean keyword query
    stop_words = [
        "find", "me", "buy", "get", "search", "for", "in", "under", "below",
        "less", "than", "within", "size", "color", "rating", "star", "stars",
        "men", "women", "man", "woman", "boys", "girls", "plain", "solid",
        "printed", "graphic", "typography", "oversized", "regular", "half", "sleeve",
        "fast", "quick", "urgent", "express", "rapid",
        "not", "no", "without", "except", "non", "minus"
    ]
    if color:
        stop_words.append(color.lower())
    
    words = [w for w in re.findall(r"\w+", p_lower) if w not in stop_words and not w.isdigit()]
    cleaned_query = " ".join(words) if words else (category or prompt)

    # 13. Quantity Extraction
    quantity = None
    qty_match = re.search(r"\b(give me|i want|buy|order|add|get)\s+(\d+)\b", p_lower)
    if qty_match:
        quantity = int(qty_match.group(2))
    elif re.search(r"\b(two)\b", p_lower):
        quantity = 2
    elif re.search(r"\b(three)\b", p_lower):
        quantity = 3
    elif re.search(r"\b(four)\b", p_lower):
        quantity = 4

    return ParsedShoppingIntent(
        raw_prompt=prompt,
        cleaned_query=cleaned_query.strip(),
        gender=gender,
        category=category,
        color=color,
        size=size,
        quantity=quantity,
        max_price=max_price,
        min_rating=min_rating,
        design=design,
        fandom=fandom,
        fit=fit,
        sleeve=sleeve,
        fast_shipping_requested=fast_shipping_requested,
        negative_keywords=negative_keywords
    )
