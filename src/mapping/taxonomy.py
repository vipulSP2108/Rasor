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

NOTE (see README.md "Changelog" section for full detail): the entries below
were audited against a live `shopify_import.csv` catalog export (4,610
products / 16,032 variants) so that categories, colors, fits, designs and
fandom partners actually present in the store are represented here. Where a
value below is annotated "catalog-verified: N products", that count comes
directly from that export.
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
    "trackpant": "track pants", "trak pant": "track pants",
    "pajama": "pyjama", "pajamas": "pyjama", "pyjamas": "pyjama", "pj": "pyjama", "pjs": "pyjama",
    "boxers": "boxer", "nightsuit": "pyjama", "night suit": "pyjama",
    "mobilecover": "mobile cover", "mobilecase": "mobile cover", "phonecase": "mobile cover",
    "phonecover": "mobile cover", "phone case": "mobile cover", "phone cover": "mobile cover",
    "back cover": "mobile cover", "cellphone cover": "mobile cover",
    "coord": "co-ord", "coords": "co-ord", "coordset": "co-ord", "co ord": "co-ord",
    "duffle bag": "duffel bag", "gymbag": "duffel bag", "gym bag": "duffel bag",

    # Fandom typos
    "batman": "batman", "bataman": "batman", "btaman": "batman", "batmn": "batman",
    "spiderman": "spider man", "spideman": "spider man", "spidermn": "spider man",
    "ironman": "iron man", "iron-man": "iron man", "iroman": "iron man", "irom man": "iron man",
    "captainamerica": "captain america",
    "panther": "panther", "pather": "panther", "black pather": "black panther",
    "pantheer": "panther", "black pantheer": "black panther",
    "deapool": "deadpool", "wolvrine": "wolverine",
    "garfeild": "garfield", "garfeld": "garfield",
    "snoopie": "snoopy", "snoopy": "snoopy",
    "squidgame": "squid game", "squid-game": "squid game",
    "nasa": "nasa",
    "narutoo": "naruto", "narudo": "naruto",
    "rick n morty": "rick and morty", "rick & morty": "rick and morty",
    "strangerthings": "stranger things",
    "minion": "minions",
    "tmnt": "tmnt", "ninja turtles": "tmnt", "teenage mutant ninja turtles": "tmnt",
    "transformer": "transformers",
    "got": "house of the dragon", "hotd": "house of the dragon",

    # Fit & Style typos
    "oversized": "oversized", "oversize": "oversized", "over size": "oversized",
    "baggy": "baggy", "loose": "oversized",
    "full sleve": "full sleeve", "full sleev": "full sleeve", "full slv": "full sleeve",
    "half sleve": "half sleeve", "haf sleeve": "half sleeve",
    "skiny fit": "skinny fit", "skinny": "skinny fit",
    "bootcut": "bootcut", "boot cut": "bootcut",
    "wideleg": "wide leg", "wide-leg": "wide leg",
    "boxy": "boxy fit",

    # Color typos
    "blck": "black", "wite": "white", "ble": "blue", "gree": "green",
    "maroon": "maroon", "mroon": "maroon",
    "offwhite": "off white", "off-white": "off white",
    "multicolour": "multicolor", "multi colour": "multicolor",
    "multi color": "multicolor", "multi-color": "multicolor", "multicoloured": "multicolor",

    # Design & Gender typos
    "grphic": "graphic", "typo": "typography",
    "womens": "women", "mens": "men", "ladie": "women", "ladies": "women",
    "girs": "women", "girls": "women", "boys": "men",
    "colur": "color", "colour": "color",
    "plussize": "plus size", "plus-size": "plus size",

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
    "trackpants": "joggers", "track pants": "joggers", "track pant": "joggers", "sweatpants": "joggers",
    "lowers": "joggers", "lower": "joggers", "bottoms": "joggers", "bottom": "joggers", "bottomwear": "joggers",
    "denim": "jeans", "jeanss": "jeans",
    "sandal": "sliders", "flip flop": "sliders", "chappal": "sliders", "flip flops": "sliders",
    "shoes": "footwear", "sneakers": "footwear", "casual shoes": "footwear", "sneaker": "footwear",
    "clog": "clogs", "crocs": "clogs",
    "mobile cover": "mobile cover", "phone case": "mobile cover", "phone cover": "mobile cover",
    "back cover": "mobile cover", "mobile case": "mobile cover", "phone covers": "mobile cover",
    "mobile covers": "mobile cover", "cellphone case": "mobile cover",
    "pyjama": "pyjama", "night suit": "pyjama", "sleepwear": "pyjama", "nightwear": "pyjama",
    "boxers": "boxer", "underwear": "boxer", "boxer shorts": "boxer",
    "sweaters": "sweater", "knitwear": "sweater",
    "dresses": "dress", "one piece dress": "dress",
    "duffle bag": "duffel bag", "gym bag": "duffel bag", "bags": "duffel bag", "bag": "duffel bag",
    "backpack": "duffel bag",
    "cap": "cap", "caps": "cap", "hat": "cap", "baseball cap": "cap",
    "co-ord": "co-ord", "co-ords": "co-ord", "coordinate set": "co-ord", "coordinates": "co-ord",
    "matching set": "co-ord",

    # Design synonyms
    "plain": "solid", "basic": "solid", "single color": "solid", "no print": "solid",
    "printed": "graphic print", "anime": "graphic print",
    "text": "typography", "quote": "typography", "slogan": "typography", "lettering": "typography",
    "vintage wash": "washed", "acid wash": "washed",
    "aop": "all over print", "all-over print": "all over print",
    "camo": "camouflage", "tie dye": "tie & dye", "tie-dye": "tie & dye",
    "colorblock": "color block", "colour block": "color block",
    "self-design": "self design",

    # Fit synonyms
    "loose": "oversized", "relaxed": "oversized", "baggy": "oversized",
    "slim": "slim fit", "tight": "slim fit",
    "boyfriend": "boyfriend fit",
    "skinny": "skinny fit", "wide leg": "wide leg", "bootcut": "bootcut",
    "straight": "straight fit", "boxy": "boxy fit",
    "super loose": "super loose fit", "super baggy": "super baggy fit",

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
    "snoopy": "peanuts", "charlie brown": "peanuts", "woodstock": "peanuts",
    "rick & morty": "rick and morty",
    "ninja turtles": "tmnt", "teenage mutant ninja turtles": "tmnt",
    "world cup": "fifa", "football": "fifa",
    "smiley world": "smiley", "s.w.smiley": "smiley",
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
    "naruto": ["hidden leaf", "hokage", "sasuke", "kakashi", "anime", "shinobi", "akatsuki", "shikamaru", "madara"],
    "dragon ball": ["dbz", "goku", "vegeta", "saiyan", "anime"],
    "dbz": ["dragon ball", "goku", "vegeta", "saiyan", "anime"],
    "goku": ["dragon ball", "saiyan", "kamehameha", "anime"],
    "one piece": ["luffy", "straw hat", "zoro", "anime", "pirate"],
    "luffy": ["one piece", "straw hat", "pirate", "anime"],
    "attack on titan": ["aot", "eren", "levi", "survey corps", "anime"],
    "aot": ["attack on titan", "eren", "levi", "anime"],
    "jujutsu kaisen": ["jjk", "gojo", "itadori", "sukuna", "anime"],
    "jjk": ["jujutsu kaisen", "gojo", "itadori", "anime"],
    "demon slayer": ["tanjiro", "nezuko", "zenitsu", "anime", "kimetsu", "hashira", "gyomei", "rengoku"],
    "my hero academia": ["mha", "deku", "plus ultra", "anime", "izuku"],
    "mha": ["my hero academia", "deku", "all might", "anime"],
    "bleach": ["ichigo", "soul reaper", "anime", "zanpakuto"],
    "hunter x hunter": ["hxh", "gon", "killua", "nen", "anime"],

    # Disney / Pop Culture
    "mickey mouse": ["disney", "mickey", "classic"],
    "star wars": ["darth vader", "yoda", "jedi", "sith", "force", "galaxy", "storm trooper", "mandalorian"],
    "darth vader": ["star wars", "sith", "dark side", "force"],
    "mandalorian": ["star wars", "mando", "baby yoda", "grogu"],

    # New: catalog-verified fandom partners (see README changelog)
    "garfield": ["odie", "jon arbuckle", "nermal", "lasagna", "monday blues"],
    "peanuts": ["snoopy", "charlie brown", "woodstock"],
    "snoopy": ["peanuts", "charlie brown", "woodstock"],
    "squid game": ["dalgona", "red light green light", "front man", "456"],
    "tom and jerry": ["tom and jerry", "tom & jerry", "tom", "jerry", "looney tunes"],
    "nasa": ["astronaut", "space", "apollo", "galaxy", "spaceship"],
    "rick and morty": ["rick sanchez", "morty smith", "portal gun", "pickle rick", "interdimensional"],
    "stranger things": ["eleven", "hawkins", "demogorgon", "upside down", "hellfire club", "mind flayer"],
    "cartoon network": ["johnny bravo", "dexter", "ed edd n eddy", "powerpuff girls", "courage"],
    "minions": ["minion", "despicable me", "gru"],
    "smiley": ["smiley world", "smiley face"],
    "fifa": ["world cup", "football", "soccer"],
    "house of the dragon": ["targaryen", "westeros", "khaleesi", "got"],
    "kung fu panda": ["po", "master shifu", "dragon warrior"],
    "tmnt": ["leonardo", "raphael", "michelangelo", "donatello", "turtle warriors"],
    "transformers": ["megatron", "decepticons", "optimus prime", "autobots"],
    "monopoly": ["mr monopoly", "board game"],
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
    "naruto": ["naruto", "sasuke", "kakashi", "hokage", "akatsuki", "shikamaru", "madara"],
    "dragon ball": ["goku", "vegeta", "dbz", "dragon ball"],
    "one piece": ["luffy", "zoro", "one piece"],
    "jujutsu kaisen": ["gojo", "sukuna", "itadori", "jjk"],
    "demon slayer": ["tanjiro", "nezuko", "zenitsu", "hashira", "gyomei", "rengoku", "demon slayer"],
    "star wars": ["star wars", "darth vader", "storm trooper", "mandalorian", "yoda"],

    # New: catalog-verified fandom partners (see README changelog)
    "garfield": ["garfield", "odie", "jon arbuckle", "nermal"],
    "peanuts": ["peanuts", "snoopy", "charlie brown", "woodstock"],
    "squid game": ["squid game", "front man", "dalgona", "red light green light"],
    "tom and jerry": ["tom and jerry", "tom & jerry", "tom", "jerry"],
    "nasa": ["nasa", "astronaut", "space explorer"],
    "rick and morty": ["rick and morty", "rick sanchez", "morty smith", "rick", "morty"],
    "stranger things": ["stranger things", "eleven", "hawkins", "demogorgon", "upside down"],
    "cartoon network": ["cartoon network", "johnny bravo", "dexter", "ed edd n eddy", "powerpuff girls", "courage"],
    "minions": ["minions", "minion", "despicable me", "gru"],
    "smiley": ["smiley", "smiley world", "s.w.smiley", "smiley face"],
    "fifa": ["fifa", "world cup", "football"],
    "house of the dragon": ["house of the dragon", "targaryen", "westeros", "khaleesi"],
    "kung fu panda": ["kung fu panda", "po", "master shifu", "dragon warrior"],
    "tmnt": ["tmnt", "teenage mutant ninja turtles", "turtle warriors", "leonardo", "raphael", "michelangelo", "donatello"],
    "transformers": ["transformers", "megatron", "decepticons", "optimus prime", "autobots"],
    "monopoly": ["monopoly", "mr monopoly"],
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
    "demon slayer": "anime",
    "star wars": "star wars",

    # New: catalog-verified fandom partners (see README changelog).
    # "avatar" is deliberately NOT auto-triggered from free text here: it's an
    # extremely common generic word (profile picture, gaming, etc.) and would
    # cause frequent false-positive fandom detection. It is still routed
    # correctly via FANDOM_HANDLE_MAP when passed as an explicit `fandom` field.
    "garfield": "garfield",
    "peanuts": "peanuts",
    "snoopy": "peanuts",
    "squid game": "squid game",
    "tom and jerry": "tom and jerry",
    "tom & jerry": "tom and jerry",
    "tom": "tom and jerry",
    "jerry": "tom and jerry",
    "nasa": "nasa",
    "rick and morty": "rick and morty",
    "stranger things": "stranger things",
    "cartoon network": "cartoon network",
    "johnny bravo": "cartoon network",
    "minions": "minions",
    "smiley": "smiley",
    "fifa": "fifa",
    "house of the dragon": "house of the dragon",
    "kung fu panda": "kung fu panda",
    "tmnt": "tmnt",
    "transformers": "transformers",
    "monopoly": "monopoly",
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
    def __init__(
        self,
        canonical_name: str,
        macro: str,
        synonyms: List[str],
        bewakoof_subclass: str,
        shopify_product_type: str,
    ):
        self.canonical_name = canonical_name
        self.macro = macro
        self.synonyms = synonyms
        self.bewakoof_subclass = bewakoof_subclass
        # Primary/display Shopify product_type (kept for backwards compatibility -
        # callers that only read `.shopify_product_type` still get a sensible
        # single value). For the *actual* filter sent to Shopify, prefer
        # CATEGORY_SHOPIFY_TYPE_ALIASES[canonical_name], which can list more
        # than one real `Type` value from the store (see README changelog -
        # several categories map to more than one literal Shopify Type).
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
        synonyms=["hoodie", "hoody", "pullover", "hooded sweatshirt", "zip hoodie", "zip-up", "zipper hoodie"],
        bewakoof_subclass="Hoodies & Sweatshirts",
        shopify_product_type="Hoodies"  # NOTE: catalog literal Type is "Hoodies" (plural), not "Hoodie" - see README changelog
    ),
    "sweatshirt": CategoryDefinition(
        canonical_name="sweatshirt",
        macro="outerwear",
        synonyms=["sweatshirt", "crewneck", "crew neck sweatshirt"],
        bewakoof_subclass="Hoodies & Sweatshirts",
        shopify_product_type="Sweatshirt"
    ),
    "sweater": CategoryDefinition(
        canonical_name="sweater",
        macro="outerwear",
        synonyms=["sweater", "sweaters", "knitwear", "pullover sweater"],
        bewakoof_subclass="Sweater",
        shopify_product_type="Sweater"
    ),
    "joggers": CategoryDefinition(
        canonical_name="joggers",
        macro="lower",
        synonyms=["joggers", "trackpants", "track pants", "track pant", "sweatpants", "lowers", "lower", "bottoms", "bottomwear"],
        bewakoof_subclass="Joggers",
        shopify_product_type="Joggers"  # NOTE: catalog also has a separate "Track Pant" Type - see CATEGORY_SHOPIFY_TYPE_ALIASES
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
    "dress": CategoryDefinition(
        canonical_name="dress",
        macro="dress",
        synonyms=["dress", "dresses", "one piece dress", "hoodie dress", "shirt dress"],
        bewakoof_subclass="Dress",
        shopify_product_type="Dress"
    ),
    "pyjama": CategoryDefinition(
        canonical_name="pyjama",
        macro="loungewear",
        synonyms=["pyjama", "pyjamas", "pajama", "pajamas", "pj", "pjs", "night suit", "sleepwear", "nightwear"],
        bewakoof_subclass="Pyjama",
        shopify_product_type="Pyjama"
    ),
    "boxer": CategoryDefinition(
        canonical_name="boxer",
        macro="innerwear",
        synonyms=["boxer", "boxers", "boxer shorts", "underwear"],
        bewakoof_subclass="Boxer",
        shopify_product_type="Boxer"
    ),
    "sliders": CategoryDefinition(
        canonical_name="sliders",
        macro="footwear",
        synonyms=["sliders", "slides", "sandals", "slippers", "chappal", "flip flop", "flip flops"],
        bewakoof_subclass="Sliders",
        shopify_product_type="Sliders"  # NOTE: was "Footwear", which matches no real catalog Type - see README changelog
    ),
    "clogs": CategoryDefinition(
        canonical_name="clogs",
        macro="footwear",
        synonyms=["clogs", "clog", "crocs"],
        bewakoof_subclass="Clogs",
        shopify_product_type="Clogs"
    ),
    "footwear": CategoryDefinition(
        canonical_name="footwear",
        macro="footwear",
        synonyms=["footwear", "shoes", "sneakers", "kicks", "casual shoes", "sneaker"],
        bewakoof_subclass="Casual Shoes",
        shopify_product_type="Casual Shoes"  # NOTE: was "Footwear", which matches no real catalog Type - see README changelog
    ),
    "mobile-cover": CategoryDefinition(
        canonical_name="mobile-cover",
        macro="accessories",
        synonyms=[
            "mobile cover", "mobile covers", "phone case", "phone cases", "phone cover",
            "phone covers", "mobile case", "back cover", "cellphone case", "cellphone cover",
        ],
        bewakoof_subclass="Mobile Cover",
        shopify_product_type="Mobile Covers"
    ),
    "duffel-bag": CategoryDefinition(
        canonical_name="duffel-bag",
        macro="accessories",
        synonyms=["duffel bag", "duffle bag", "gym bag", "bag", "bags", "backpack"],
        bewakoof_subclass="Bag",
        shopify_product_type="Duffel Bag"
    ),
    "cap": CategoryDefinition(
        canonical_name="cap",
        macro="accessories",
        synonyms=["cap", "caps", "hat", "baseball cap"],
        bewakoof_subclass="Cap",
        shopify_product_type="Caps"
    ),
    "co-ord": CategoryDefinition(
        canonical_name="co-ord",
        macro="general",
        synonyms=["co-ord", "co-ords", "coord", "coords", "coordinate set", "coordinates", "matching set"],
        bewakoof_subclass="Co-ordinates",
        shopify_product_type="Co-ordinates"
    ),
    "general": CategoryDefinition(
        canonical_name="general",
        macro="general",
        synonyms=["clothing", "apparel", "wear", "items"],
        bewakoof_subclass="Clothing",
        shopify_product_type=""  # Intentionally blank: no real product_type should be forced for an unclassified query - see README changelog
    )
}

# Map of canonical category -> ALL real Shopify `Type` column values that
# should satisfy it. Several canonical categories legitimately span more
# than one literal catalog Type (e.g. "joggers" also covers "Track Pant";
# "sliders" also covers "Flip Flops & Sliders"). ShopifyCompiler builds an
# OR-grouped `product_type:` clause from this list instead of the single
# CategoryDefinition.shopify_product_type value. An empty list means "do not
# filter by product_type" (used for the "general"/unclassified bucket, since
# forcing a non-existent product_type like the old "Clothing" placeholder
# guaranteed zero results - see README changelog).
CATEGORY_SHOPIFY_TYPE_ALIASES: Dict[str, List[str]] = {
    "t-shirt": ["T-Shirt", "Top"],  # "Top" (9 products): women's short graphic tops, same silhouette family as t-shirt
    "shirt": ["Shirt"],
    "hoodie": ["Hoodies"],
    "sweatshirt": ["Sweatshirt"],
    "sweater": ["Sweater"],
    "joggers": ["Joggers", "Track Pant"],
    "jeans": ["Jeans"],
    "vest": ["Vest"],
    "dress": ["Dress"],
    "pyjama": ["Pyjama"],
    "boxer": ["Boxer"],
    "sliders": ["Sliders", "Flip Flops & Sliders"],
    "clogs": ["Clogs"],
    "footwear": ["Casual Shoes"],
    "mobile-cover": ["Mobile Covers"],
    "duffel-bag": ["Duffel Bag"],
    "cap": ["Caps"],
    "co-ord": ["Co-ordinates"],
    "general": [],
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
    "outerwear": ["hoodie", "sweatshirt", "sweater"],
    "footwear": ["sliders", "clogs", "footwear"],
    "accessories": ["mobile-cover", "duffel-bag", "cap"],
    "loungewear": ["pyjama"],
    "innerwear": ["boxer"],
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
    "white": ColorProfile("White", "White", "#FFFFFF", ["white", "snow white", "ivory", "pearl", "off white", "off-white"]),
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
    # New: catalog-verified colors (see README changelog). "Pink" (148 products)
    # and "Multicolor" (769 products - the *second most common* single color
    # tag in the whole catalog) had no entry at all before this pass, meaning
    # any query mentioning them could never resolve a color match.
    "pink": ColorProfile("Pink", "Pink", "#FF69B4", ["pink", "hot pink", "baby pink", "blush", "rose"]),
    "multicolor": ColorProfile("Multicolor", "Multicolor", "#CCCCCC", ["multicolor", "multi color", "multicolour", "multi-colour", "rainbow"]),
    "silver": ColorProfile("Silver", "Grey", "#C0C0C0", ["silver", "metallic silver", "chrome", "gunmetal"]),
}


# ------------------------------------------------------------------------------
# 7. Bewakoof Handle Routing Tables
# ------------------------------------------------------------------------------

# CAUTION: handles marked "(inferred)" below follow this file's existing
# "<fandom>-merchandise" naming convention but were NOT individually verified
# against the live Bewakoof HandleRegistry (out of scope for this taxonomy
# pass - see README changelog). Confirm against bewakoof_api.py's
# HandleRegistry before relying on them for a live storefront call; if wrong,
# BewakoofCompiler will still route the request without raising an error, it
# will just fetch the wrong (or an empty) collection.
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

    # Previously present in FANDOM_KNOWLEDGE_GRAPH / CHARACTER_ENTITY_MAP but
    # had NO handle at all, so a "naruto tee" or "star wars hoodie" query
    # could never route to the right collection and fell through to the
    # generic men/women-clothing bucket. anime-collection was confirmed live;
    # the rest are inferred (see caution note above).
    "anime":         "anime-collection",
    "naruto":        "naruto-merchandise",
    "one piece":     "one-piece-merchandise",       # (inferred)
    "demon slayer":  "demon-slayer-merchandise",    # (inferred)
    "star wars":     "star-wars-merchandise",       # (inferred)

    # New: catalog-verified fandom partners (see README changelog). All
    # "(inferred)" per the caution note above.
    "garfield":            "garfield-merchandise",            # (inferred)
    "peanuts":             "peanuts-merchandise",              # (inferred)
    "squid game":          "squid-game-collection",           # confirmed live handle (HTTP 200 on api-prod.bewakoof.com)
    "nasa":                "nasa-merchandise",                 # (inferred)
    "rick and morty":      "rick-and-morty-merchandise",       # (inferred)
    "stranger things":     "stranger-things-merchandise",      # (inferred)
    "cartoon network":     "cartoon-network-merchandise",      # (inferred)
    "minions":             "minions-merchandise",              # (inferred)
    "smiley":              "smiley-merchandise",               # (inferred)
    "fifa":                "fifa-merchandise",                 # (inferred)
    "house of the dragon": "house-of-the-dragon-merchandise",  # (inferred)
    "kung fu panda":       "kung-fu-panda-merchandise",        # (inferred)
    "tmnt":                "tmnt-merchandise",                 # (inferred)
    "teenage mutant ninja turtles": "tmnt-merchandise",        # (inferred) catalog literal is the full name, not the acronym
    "transformers":        "transformers-merchandise",         # (inferred)
    "avatar":              "avatar-merchandise",               # (inferred) - not auto-detected from free text, see ENTITY_FRANCHISE_MAP note
    "monopoly":            "monopoly-merchandise",             # (inferred)
}

DESIGN_HANDLE_MAP: Dict[str, str] = {
    "typography":   "typography-t-shirts",
    "oversized":    "oversized-t-shirts",
    "printed":      "printed-t-shirts",
    "graphic print":"printed-t-shirts",
    "acid wash":    "acid-wash-t-shirts",
    "washed":       "acid-wash-t-shirts",
    # Catalog-verified design themes mapped to active Bewakoof collections:
    "checked":      "men-check-shirts",       # confirmed live handle (HTTP 200 on api-prod.bewakoof.com)
    "all over print": "all-over-printed-t-shirts",  # (inferred) catalog-verified: 188 products
    "color block":  "color-block-t-shirts",   # (inferred) catalog-verified: 69 products
    "striped":      "striped-t-shirts",       # (inferred) catalog-verified: 55 products
    "embroidered":  "embroidered-t-shirts",   # (inferred) catalog-verified: 55 products
    "self design":  "self-design-t-shirts",   # (inferred) catalog-verified: 54 products
    "applique":     "applique-t-shirts",      # (inferred) catalog-verified: 48 products
    "camouflage":   "camouflage-t-shirts",    # (inferred) catalog-verified: 8 products
    "ombre":        "ombre-t-shirts",         # (inferred) catalog-verified: 10 products
    "tie & dye":    "tie-dye-t-shirts",       # (inferred) catalog-verified: 10 products
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
    ("men",   "sweater", None):      "men-sweaters",       # (inferred)
    ("women", "sweater", None):      "women-sweaters",     # (inferred)
    ("men",   "joggers", None):      "men-joggers",
    ("women", "joggers", None):      "women-joggers",
    ("men",   "sliders", None):      "men-sliders",
    ("men",   "sandals", None):      "men-sliders",
    ("women", "sliders", None):      "women-sliders",      # (inferred)
    ("men",   "clogs", None):        "men-clogs",           # (inferred)
    ("women", "clogs", None):        "women-clogs",         # (inferred)
    ("men",   "footwear", None):     "men-footwear",
    ("women", "footwear", None):     "women-footwear",
    ("men",   "jeans",   None):      "jeans-for-men",
    ("women", "jeans",   None):      "jeans-for-women",
    ("men",   "shirt",   None):      "men-shirts",
    ("women", "shirt",   None):      "women-shirts",
    ("women", "dress",   None):      "women-dresses",       # (inferred) catalog-verified: 25 products, all Women's
    ("men",   "pyjama",  None):      "pyjamas",             # confirmed live handle (HTTP 200 on api-prod.bewakoof.com)
    ("women", "pyjama",  None):      "pyjamas",             # confirmed live handle (HTTP 200 on api-prod.bewakoof.com)
    ("men",   "boxer",   None):      "men-boxers",          # (inferred)
    ("men",   "mobile-cover", None): "mobile-covers-india", # confirmed live handle (base collection; site further splits by phone brand/model)
    ("women", "mobile-cover", None): "mobile-covers-india", # same base collection - accessory category is not gender-split on the live site
    ("men",   "duffel-bag", None):   "bags",                # (inferred)
    ("women", "duffel-bag", None):   "bags",                # (inferred)
    ("men",   "cap",     None):      "caps",                # (inferred)
    ("women", "cap",     None):      "caps",                # (inferred)
    ("men",   "co-ord",  None):      "men-co-ords",         # (inferred)
    ("women", "co-ord",  None):      "women-co-ords",       # (inferred)
}

GENDER_FALLBACK_MAP: Dict[str, str] = {
    "men":    "men-clothing",
    "women":  "women-clothing",
    "unisex": "men-clothing",
    "all":    "men-clothing",
}


# ------------------------------------------------------------------------------
# 8. Fit Canonicalization (catalog-verified real Fit spec values)
# ------------------------------------------------------------------------------

# Every literal `Fit` value seen in the catalog export now maps to a stable,
# title-cased canonical form. Previously only Oversized/Regular/Slim/
# Boyfriend/Relaxed were covered; the remaining ~190 products across Jeans,
# Track Pants and Vests (Straight Fit, Skinny Fit, Wide Leg, Bootcut, Boxy
# Fit, etc.) fell back to a generic `.title()` call with no synonym
# awareness, so e.g. a user asking for "skinny jeans" would not be recognized
# as the same thing as the catalog's "Slim Fit"/"Skinny Fit" jeans. See
# README changelog for full per-fit product counts.
FIT_CANONICAL_MAP: Dict[str, str] = {
    "oversized": "Oversized Fit",
    "oversized fit": "Oversized Fit",
    "baggy": "Oversized Fit",
    "baggy fit": "Oversized Fit",
    "loose": "Oversized Fit",
    "regular": "Regular Fit",
    "regular fit": "Regular Fit",
    "slim": "Slim Fit",
    "slim fit": "Slim Fit",
    "skinny": "Skinny Fit",
    "skinny fit": "Skinny Fit",
    "relaxed": "Oversized Fit",
    "relaxed fit": "Oversized Fit",
    "boyfriend": "Boyfriend Fit",
    "boyfriend fit": "Boyfriend Fit",
    # New: catalog-verified fit values (see README changelog)
    "straight": "Straight Fit",
    "straight fit": "Straight Fit",
    "slim straight": "Slim Straight Fit",
    "slim straight fit": "Slim Straight Fit",
    "wide leg": "Wide Leg",
    "bootcut": "Bootcut",
    "boxy": "Boxy Fit",
    "boxy fit": "Boxy Fit",
    "square": "Square Fit",
    "square fit": "Square Fit",
    "super loose": "Super Loose Fit",
    "super loose fit": "Super Loose Fit",
    "super baggy": "Super Baggy Fit",
    "super baggy fit": "Super Baggy Fit",
    "flared": "Flared",
    "barrel": "Barrel Fit",
    "barrel fit": "Barrel Fit",
    "tapered": "Tapered Fit",
    "tapered fit": "Tapered Fit",
    "unisex fit": "Unisex Fit",
}


# ------------------------------------------------------------------------------
# 9. Sleeve Canonicalization (catalog-verified real Sleeve spec values)
# ------------------------------------------------------------------------------

# Previously only "full"/"half" were recognized (via substring check in
# intent_catalog_mapper); Raglan/Extended/3-4/Elbow sleeve products (14
# combined - small but real) had no canonical form at all.
SLEEVE_CANONICAL_MAP: Dict[str, str] = {
    "full": "Full Sleeve",
    "full sleeve": "Full Sleeve",
    "half": "Half Sleeve",
    "half sleeve": "Half Sleeve",
    "short sleeve": "Half Sleeve",
    "sleeveless": "Sleeveless",
    "raglan": "Raglan Sleeve",
    "raglan sleeve": "Raglan Sleeve",
    "extended": "Extended Sleeve",
    "extended sleeve": "Extended Sleeve",
    "3/4": "3/4 Sleeve",
    "3/4 sleeve": "3/4 Sleeve",
    "three quarter sleeve": "3/4 Sleeve",
    "elbow": "Elbow Sleeve",
    "elbow sleeve": "Elbow Sleeve",
}


# ------------------------------------------------------------------------------
# 10. Plus Size Detection (catalog-verified: 299 products carry "Plus Size" in title)
# ------------------------------------------------------------------------------

# "Plus Size" was not modeled anywhere in the mapping subsystem at all before
# this pass, despite being a real, frequently-used qualifier across ~6.5% of
# the catalog (299 of 4,610 products - concentrated in T-Shirts and Hoodies).
# A query like "plus size oversized tee" previously had the words "plus" and
# "size" silently dropped as noise/unrecognized tokens. See README changelog.
PLUS_SIZE_KEYWORDS = {"plus size", "plus-size", "plussize", "plus sized"}


# ------------------------------------------------------------------------------
# 11. Noise Words for Clean Keyword Extraction
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
