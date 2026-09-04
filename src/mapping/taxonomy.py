"""
Centralized Taxonomy, Dictionaries, and Knowledge Graphs for Catalog Mapping.

Consolidates:
  - Spell corrections and typos
  - Synonym expansions (category, fit, design, fabric, neck, gender, fandom)
  - Fandom knowledge graph and character entity mappings
  - Aesthetic vibe mappings
  - Garment category taxonomy (macro vs micro)
  - Color family and hex anchor taxonomy
  - Bewakoof collection handle routing tables
  - Search noise word lists
"""

from typing import Any, Dict, List, Optional, Tuple


# ------------------------------------------------------------------------------
# 1. Spell Correction & Typo Normalization
# ------------------------------------------------------------------------------

SPELL_CORRECTIONS: Dict[str, str] = {
    # Garment typos
    "tshrt": "t-shirt", "t shrts": "t-shirt", "t shrt": "t-shirt",
    "tshirts": "t-shirt", "tee shirt": "t-shirt", "teeshirt": "t-shirt",
    "sweat shirt": "sweatshirt", "hooide": "hoodie", "hoddie": "hoodie",
    "jogger": "joggers", "joogers": "joggers",
    "slipper": "sliders", "sliders": "sliders",
    
    # Fandom typos
    "batman": "batman", "bataman": "batman", "btaman": "batman", "batmn": "batman",
    "spiderman": "spider man", "spideman": "spider man", "spidermn": "spider man",
    "ironman": "iron man", "iron-man": "iron man", "iroman": "iron man", "irom man": "iron man",
    "captainamerica": "captain america",
    "panther": "panther", "pather": "panther", "black pather": "black panther",
    "pantheer": "panther", "black pantheer": "black panther",
    "deapool": "deadpool", "wolvrine": "wolverine",
    
    # Fit & Style typos
    "oversized": "oversized", "oversize": "oversized", "over size": "oversized",
    "baggy": "baggy", "loose": "oversized",
    "full sleve": "full sleeve", "full sleev": "full sleeve", "full slv": "full sleeve",
    "half sleve": "half sleeve", "haf sleeve": "half sleeve",
    
    # Color typos
    "blck": "black", "wite": "white", "ble": "blue", "gree": "green",
    "maroon": "maroon", "mroon": "maroon",
    
    # Design & Gender typos
    "grphic": "graphic", "typo": "typography",
    "womens": "women", "mens": "men", "ladie": "women", "ladies": "women",
    "girs": "women", "girls": "women", "boys": "men",
    "colur": "color", "colour": "color",
    
    # Budget typos
    "under Rs": "under", "under rs": "under", "below rs": "under",
}


# ------------------------------------------------------------------------------
# 2. Canonical Synonym Map
# ------------------------------------------------------------------------------

SYNONYM_MAP: Dict[str, str] = {
    # Category synonyms
    "tee": "t-shirt", "top": "t-shirt", "topwear": "t-shirt", "uppers": "t-shirt", "upper": "t-shirt",
    "pullover": "hoodie", "jacket": "hoodie", "sweatshirt": "hoodie",
    "trackpants": "joggers", "track pants": "joggers", "sweatpants": "joggers",
    "lowers": "joggers", "lower": "joggers", "bottoms": "joggers", "bottom": "joggers", "bottomwear": "joggers",
    "denim": "jeans", "jeanss": "jeans",
    "sandal": "sliders", "flip flop": "sliders", "chappal": "sliders",
    "shoes": "footwear", "sneakers": "footwear",
    
    # Design synonyms
    "plain": "solid", "basic": "solid", "single color": "solid", "no print": "solid",
    "printed": "graphic print", "anime": "graphic print",
    "text": "typography", "quote": "typography", "slogan": "typography", "lettering": "typography",
    "vintage wash": "washed", "acid wash": "washed",
    
    # Fit synonyms
    "loose": "oversized", "relaxed": "oversized", "baggy": "oversized",
    "slim": "slim fit", "tight": "slim fit",
    "boyfriend": "boyfriend fit",
    
    # Neck & Fabric
    "v neck": "v-neck", "vneck": "v-neck",
    "crew neck": "round neck", "crew": "round neck", "round": "round neck",
    "collared": "collar", "polo neck": "polo",
    "poly": "polyester", "cotton blend": "blend", "poly cotton": "blend",
    
    # Gender synonyms
    "female": "women", "girl": "women", "lady": "women",
    "male": "men", "guy": "men", "boy": "men",
    
    # Fandom synonyms
    "dc comics": "dc", "dc universe": "dc", "justice league": "dc",
    "marvel universe": "marvel", "mcu": "marvel", "avengers": "marvel",
    "hp": "harry potter", "hogwarts": "harry potter",
    "mickey": "disney", "minnie": "disney",
    "looney": "looney tunes", "bugs bunny": "looney tunes",
    "tom and jerry": "tom and jerry", "tom & jerry": "tom and jerry",
}


# ------------------------------------------------------------------------------
# 3. Fandom Knowledge Graph & Entity Relationships
# ------------------------------------------------------------------------------

FANDOM_KNOWLEDGE_GRAPH: Dict[str, List[str]] = {
    # Marvel
    "black panther": ["wakanda", "t'challa", "vibranium", "marvel"],
    "panther": ["wakanda", "t'challa", "vibranium", "marvel"],
    "spiderman": ["spider-man", "peter parker", "miles morales", "web", "marvel"],
    "spider-man": ["spider", "peter parker", "miles morales", "web", "marvel"],
    "ironman": ["iron man", "tony stark", "stark industries", "arc reactor", "marvel"],
    "iron man": ["tony stark", "stark industries", "arc reactor", "marvel"],
    "captain america": ["steve rogers", "shield", "first avenger", "marvel"],
    "thor": ["mjolnir", "asgard", "god of thunder", "marvel"],
    "deadpool": ["ryan reynolds", "marvel", "merc with a mouth", "wade wilson"],
    "wolverine": ["x-men", "logan", "mutant", "marvel", "adamantium"],
    "venom": ["symbiote", "eddie brock", "marvel", "carnage"],
    "hulk": ["bruce banner", "avengers", "marvel", "smash"],
    "guardians": ["groot", "rocket", "star-lord", "marvel", "galaxy"],
    "groot": ["guardians", "galaxy", "marvel", "i am groot"],
    "thanos": ["infinity", "gauntlet", "marvel", "avengers"],
    "loki": ["asgard", "god of mischief", "marvel"],
    "hawkeye": ["clint barton", "avengers", "marvel", "arrow"],
    "antman": ["scott lang", "quantum", "marvel", "pym"],
    "doctor strange": ["sorcerer supreme", "marvel", "multiversal"],
    
    # DC
    "batman": ["gotham", "dark knight", "bruce wayne", "joker", "dc"],
    "superman": ["clark kent", "krypton", "man of steel", "dc"],
    "wonder woman": ["diana prince", "amazon", "dc"],
    "flash": ["barry allen", "speedster", "central city", "dc"],
    "aquaman": ["arthur curry", "atlantis", "dc", "ocean"],
    "joker": ["gotham", "dc", "villain", "batman"],
    "harley quinn": ["dc", "joker", "gotham", "villain"],
    "green lantern": ["dc", "hal jordan", "ring"],
    
    # Anime
    "naruto": ["hidden leaf", "hokage", "sasuke", "kakashi", "anime", "shinobi"],
    "dragon ball": ["dbz", "goku", "vegeta", "saiyan", "anime"],
    "dbz": ["dragon ball", "goku", "vegeta", "saiyan", "anime"],
    "goku": ["dragon ball", "saiyan", "kamehameha", "anime"],
    "one piece": ["luffy", "straw hat", "zoro", "anime", "pirate"],
    "luffy": ["one piece", "straw hat", "pirate", "anime"],
    "attack on titan": ["aot", "eren", "levi", "survey corps", "anime"],
    "aot": ["attack on titan", "eren", "levi", "anime"],
    "jujutsu kaisen": ["jjk", "gojo", "itadori", "sukuna", "anime"],
    "jjk": ["jujutsu kaisen", "gojo", "itadori", "anime"],
    "demon slayer": ["tanjiro", "nezuko", "zenitsu", "anime", "kimetsu"],
    "my hero academia": ["mha", "deku", "plus ultra", "anime", "izuku"],
    "mha": ["my hero academia", "deku", "all might", "anime"],
    "bleach": ["ichigo", "soul reaper", "anime", "zanpakuto"],
    "hunter x hunter": ["hxh", "gon", "killua", "nen", "anime"],
    
    # Disney / Pop Culture
    "mickey mouse": ["disney", "mickey", "classic"],
    "star wars": ["darth vader", "yoda", "jedi", "sith", "force", "galaxy"],
    "darth vader": ["star wars", "sith", "dark side", "force"],
    "mandalorian": ["star wars", "mando", "baby yoda", "grogu"],
}

CHARACTER_ENTITY_MAP: Dict[str, List[str]] = {
    "black panther": ["black panther", "black pantheer", "black pather", "pather", "wakanda", "t'challa", "tchalla", "shuri", "killmonger", "the king", "king black panther", "panther"],
    "iron man": ["iron man", "ironman", "tony stark", "arc reactor", "war machine"],
    "spider-man": ["spider-man", "spiderman", "peter parker", "miles morales", "spider punk", "spider-punk", "brand new day"],
    "venom": ["venom", "symbiote", "carnage", "eddie brock"],
    "moon knight": ["moon knight", "marc spector"],
    "batman": ["batman", "dark knight", "bruce wayne", "gotham"],
    "deadpool": ["deadpool", "wade wilson"],
    "captain america": ["captain america", "steve rogers"],
    "thor": ["thor", "mjolnir", "odinson"],
    "hulk": ["hulk", "bruce banner"],
    "wolverine": ["wolverine", "logan"],
    "joker": ["joker"],
    "superman": ["superman", "clark kent"],
    "ghost rider": ["ghost rider", "spirit of vengeance", "johnny blaze"],
    "fantastic four": ["the four", "fantastic four", "mr fantastic", "human torch", "invisible woman"],
    "punisher": ["punisher", "frank castle"],
    "daredevil": ["daredevil", "matt murdock"],
    "naruto": ["naruto", "sasuke", "kakashi", "hokage"],
    "dragon ball": ["goku", "vegeta", "dbz", "dragon ball"],
    "one piece": ["luffy", "zoro", "one piece"],
    "jujutsu kaisen": ["gojo", "sukuna", "itadori", "jjk"],
}

ENTITY_FRANCHISE_MAP: Dict[str, str] = {
    "black panther": "marvel",
    "iron man": "marvel",
    "spider-man": "marvel",
    "venom": "marvel",
    "moon knight": "marvel",
    "deadpool": "marvel",
    "captain america": "marvel",
    "thor": "marvel",
    "hulk": "marvel",
    "wolverine": "marvel",
    "ghost rider": "marvel",
    "fantastic four": "marvel",
    "punisher": "marvel",
    "daredevil": "marvel",
    "batman": "dc",
    "joker": "dc",
    "superman": "dc",
    "naruto": "anime",
    "dragon ball": "anime",
    "one piece": "anime",
    "jujutsu kaisen": "anime",
}


# ------------------------------------------------------------------------------
# 4. Aesthetic Vibe Taxonomy
# ------------------------------------------------------------------------------

VIBE_MAP: Dict[str, str] = {
    "retro grunge": "oversized fit washed graphic print maroon grey black",
    "grunge": "oversized fit washed graphic print maroon grey black",
    "minimalist": "regular fit solid beige white navy",
    "streetwear": "baggy fit graphic print black white",
    "y2k": "baggy fit washed typography pink blue",
    "gym": "regular fit solid black grey blue",
    "cozy": "oversized fit solid grey beige brown",
    "cyberpunk": "oversized fit graphic print neon black cyan",
    "old money": "regular fit solid beige white navy polo",
}


# ------------------------------------------------------------------------------
# 5. Garment Category Taxonomy & Macro Mapping
# ------------------------------------------------------------------------------

class CategoryDefinition:
    def __init__(self, canonical_name: str, macro: str, synonyms: List[str], bewakoof_subclass: str, shopify_product_type: str):
        self.canonical_name = canonical_name
        self.macro = macro
        self.synonyms = synonyms
        self.bewakoof_subclass = bewakoof_subclass
        self.shopify_product_type = shopify_product_type

CATEGORY_TAXONOMY: Dict[str, CategoryDefinition] = {
    "t-shirt": CategoryDefinition(
        canonical_name="t-shirt",
        macro="upper",
        synonyms=["tshirt", "t-shirt", "tee", "top", "topwear", "uppers", "upper"],
        bewakoof_subclass="T-Shirt",
        shopify_product_type="T-Shirt"
    ),
    "shirt": CategoryDefinition(
        canonical_name="shirt",
        macro="upper",
        synonyms=["shirt", "casual shirt", "formal shirt", "button down"],
        bewakoof_subclass="Shirt",
        shopify_product_type="Shirt"
    ),
    "hoodie": CategoryDefinition(
        canonical_name="hoodie",
        macro="outerwear",
        synonyms=["hoodie", "hoody", "pullover", "hooded sweatshirt"],
        bewakoof_subclass="Hoodies & Sweatshirts",
        shopify_product_type="Hoodie"
    ),
    "sweatshirt": CategoryDefinition(
        canonical_name="sweatshirt",
        macro="outerwear",
        synonyms=["sweatshirt", "crewneck", "crew neck sweatshirt"],
        bewakoof_subclass="Hoodies & Sweatshirts",
        shopify_product_type="Sweatshirt"
    ),
    "joggers": CategoryDefinition(
        canonical_name="joggers",
        macro="lower",
        synonyms=["joggers", "trackpants", "track pants", "sweatpants", "lowers", "lower", "bottoms", "bottomwear"],
        bewakoof_subclass="Joggers",
        shopify_product_type="Joggers"
    ),
    "jeans": CategoryDefinition(
        canonical_name="jeans",
        macro="lower",
        synonyms=["jeans", "denim", "denim pants"],
        bewakoof_subclass="Jeans",
        shopify_product_type="Jeans"
    ),
    "vest": CategoryDefinition(
        canonical_name="vest",
        macro="upper",
        synonyms=["vest", "sleeveless tee", "gym vest", "tank top", "tank"],
        bewakoof_subclass="Vest",
        shopify_product_type="Vest"
    ),
    "sliders": CategoryDefinition(
        canonical_name="sliders",
        macro="footwear",
        synonyms=["sliders", "slides", "sandals", "slippers", "chappal", "flip flop"],
        bewakoof_subclass="Sliders",
        shopify_product_type="Footwear"
    ),
    "footwear": CategoryDefinition(
        canonical_name="footwear",
        macro="footwear",
        synonyms=["footwear", "shoes", "sneakers", "kicks"],
        bewakoof_subclass="Footwear",
        shopify_product_type="Footwear"
    ),
    "general": CategoryDefinition(
        canonical_name="general",
        macro="general",
        synonyms=["clothing", "apparel", "wear", "items"],
        bewakoof_subclass="Clothing",
        shopify_product_type="Clothing"
    )
}

# Macro category aliases
MACRO_CATEGORY_EXPANSIONS: Dict[str, List[str]] = {
    "upper": ["t-shirt", "shirt", "hoodie", "sweatshirt", "vest"],
    "uppers": ["t-shirt", "shirt", "hoodie", "sweatshirt", "vest"],
    "top": ["t-shirt", "shirt", "hoodie", "sweatshirt", "vest"],
    "topwear": ["t-shirt", "shirt", "hoodie", "sweatshirt", "vest"],
    "lower": ["joggers", "jeans"],
    "lowers": ["joggers", "jeans"],
    "bottom": ["joggers", "jeans"],
    "bottoms": ["joggers", "jeans"],
    "bottomwear": ["joggers", "jeans"],
    "outerwear": ["hoodie", "sweatshirt"],
    "footwear": ["sliders", "footwear"],
}


# ------------------------------------------------------------------------------
# 6. Color Taxonomy & Hex Anchors
# ------------------------------------------------------------------------------

class ColorProfile:
    def __init__(self, canonical_name: str, family: str, hex_anchor: str, aliases: List[str]):
        self.canonical_name = canonical_name
        self.family = family
        self.hex_anchor = hex_anchor
        self.aliases = aliases

COLOR_TAXONOMY: Dict[str, ColorProfile] = {
    "black": ColorProfile("Black", "Black", "#111111", ["jet black", "black", "onyx", "coal", "dark shadow"]),
    "white": ColorProfile("White", "White", "#FFFFFF", ["white", "snow white", "ivory", "pearl"]),
    "blue": ColorProfile("Blue", "Blue", "#0044CC", ["blue", "royal blue", "sky blue", "cyan", "baby blue"]),
    "navy": ColorProfile("Navy", "Blue", "#001F3F", ["navy", "navy blue", "dark blue"]),
    "green": ColorProfile("Green", "Green", "#2ECC40", ["green", "emerald", "lime", "mint"]),
    "olive": ColorProfile("Olive", "Green", "#556B2F", ["olive", "olive green", "army green", "sage", "military green"]),
    "red": ColorProfile("Red", "Red", "#FF4136", ["red", "scarlet", "ruby"]),
    "maroon": ColorProfile("Maroon", "Red", "#800000", ["maroon", "burgundy", "wine", "crimson"]),
    "grey": ColorProfile("Grey", "Grey", "#AAAAAA", ["grey", "gray", "dark grey", "light grey", "charcoal", "slate", "heather grey"]),
    "beige": ColorProfile("Beige", "Beige", "#F5F5DC", ["beige", "cream", "sand", "khaki", "tan", "ecru", "oatmeal"]),
    "brown": ColorProfile("Brown", "Brown", "#8B4513", ["brown", "coffee", "chocolate", "mocha"]),
    "yellow": ColorProfile("Yellow", "Yellow", "#FFDC00", ["yellow", "mustard", "lemon", "ochre"]),
    "orange": ColorProfile("Orange", "Orange", "#FF851B", ["orange", "rust", "tangerine", "peach"]),
    "purple": ColorProfile("Purple", "Purple", "#B10DC9", ["purple", "violet", "lavender", "lilac"]),
}


# ------------------------------------------------------------------------------
# 7. Bewakoof Handle Routing Tables
# ------------------------------------------------------------------------------

FANDOM_HANDLE_MAP: Dict[str, str] = {
    "marvel":       "marvel",
    "dc":           "batman-merchandise",
    "batman":       "batman-merchandise",
    "harry potter": "harry-potter-merchandise",
    "hogwarts":     "harry-potter-merchandise",
    "disney":       "disney-merchandise",
    "looney tunes": "looney-tunes-merchandise",
    "tom and jerry":"looney-tunes-merchandise",
    "scooby doo":   "scooby-doo-merchandise",
    "friends":      "friends-merchandise",
}

DESIGN_HANDLE_MAP: Dict[str, str] = {
    "typography":   "typography-t-shirts",
    "oversized":    "oversized-t-shirts",
    "printed":      "printed-t-shirts",
    "graphic print":"printed-t-shirts",
    "acid wash":    "acid-wash-t-shirts",
    "washed":       "acid-wash-t-shirts",
}

CATEGORY_SLEEVE_HANDLE_MAP: Dict[Tuple[str, str, Optional[str]], str] = {
    ("men",   "t-shirt", "full"):    "men-full-sleeve-t-shirts",
    ("women", "t-shirt", "full"):    "women-full-sleeve-t-shirts",
    ("men",   "t-shirt", "half"):    "men-t-shirts",
    ("women", "t-shirt", "half"):    "women-t-shirts",
    ("men",   "t-shirt", None):      "men-t-shirts",
    ("women", "t-shirt", None):      "women-t-shirts",
    ("men",   "hoodie",  None):      "men-hoodies-sweatshirts",
    ("women", "hoodie",  None):      "women-hoodies-sweatshirts",
    ("men",   "sweatshirt", None):   "men-hoodies-sweatshirts",
    ("women", "sweatshirt", None):   "women-hoodies-sweatshirts",
    ("men",   "joggers", None):      "men-joggers",
    ("women", "joggers", None):      "women-joggers",
    ("men",   "sliders", None):      "men-sliders",
    ("men",   "sandals", None):      "men-sliders",
    ("men",   "footwear", None):     "men-footwear",
    ("women", "footwear", None):     "women-footwear",
    ("men",   "jeans",   None):      "jeans-for-men",
    ("women", "jeans",   None):      "jeans-for-women",
    ("men",   "shirt",   None):      "men-shirts",
    ("women", "shirt",   None):      "women-shirts",
}

GENDER_FALLBACK_MAP: Dict[str, str] = {
    "men":    "men-clothing",
    "women":  "women-clothing",
    "unisex": "men-clothing",
    "all":    "men-clothing",
}


# ------------------------------------------------------------------------------
# 8. Noise Words for Clean Keyword Extraction
# ------------------------------------------------------------------------------

NOISE_WORDS = {
    "a", "an", "the", "in", "on", "at", "for", "with", "by", "of", "to",
    "and", "or", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "i", "me", "my", "we",
    "you", "your", "he", "him", "she", "her", "they", "them", "it",
    "this", "that", "these", "those", "want", "looking", "need", "give",
    "show", "find", "get", "search", "buy", "purchase", "order",
    "please", "can", "could", "would", "like", "under", "below", "rs",
    "inr", "rupees", "budget", "price", "cheap", "best", "good", "cool",
    "nice", "style", "styles", "outfit", "look", "combo", "pair",
}
