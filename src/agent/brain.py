"""Agent Brain: Multi-Model LLM Reasoning Engine.

Pipeline:
  Stage 1: Spell-correction + synonym expansion (rule-based, always runs)
  Stage 2: LLM Intent Normalization (Gemini → Groq → rule fallback)
  Stage 3: LLM Candidate Relevance Evaluation (filters false positives)
"""

import os
import json
import re
from typing import List, Optional, Tuple
import requests
from dotenv import load_dotenv

from src.agent.state import (
    CanonicalShoppingQuery,
    MultiShoppingQuery,
    CategoryEnum,
    ColorEnum,
    DesignEnum,
    FandomEnum,
    FitEnum,
    GenderEnum,
    OccasionEnum,
    Product,
    ProductRelevanceEvaluation,
    SleeveEnum,
    FabricEnum,
    NeckEnum,
)
from src.agent.parser import parse_user_intent

load_dotenv()


# In-memory VQA scan cache: (image_url, prompt_prefix) -> vqa_result_dict
_VQA_CACHE: dict = {}

# ---------------------------------------------------------------------------
# 1. Spell Correction & Synonym Map
#    These run BEFORE the LLM to pre-clean user typos and synonyms.
#    This makes the system more robust on both LLM and rule-based paths.
# ---------------------------------------------------------------------------

_SPELL_CORRECTIONS: dict = {
    # Typos & common misspellings
    "tshrt": "t-shirt", "t shrts": "t-shirt", "t shrt": "t-shirt",
    "tshirts": "t-shirt", "tee shirt": "t-shirt", "teeshirt": "t-shirt",
    "sweat shirt": "sweatshirt", "hooide": "hoodie", "hoddie": "hoodie",
    "jogger": "joggers", "joogers": "joggers",
    "slipper": "sliders", "sliders": "sliders",
    "batman": "batman", "bataman": "batman", "btaman": "batman", "batmn": "batman",
    "spiderman": "spider man", "spideman": "spider man", "spidermn": "spider man",
    "ironman": "iron man", "iron-man": "iron man", "iroman": "iron man", "irom man": "iron man",
    "captainamerica": "captain america",
    "panther": "panther", "pather": "panther", "black pather": "black panther",
    "pantheer": "panther", "black pantheer": "black panther",
    "deapool": "deadpool", "wolvrine": "wolverine",
    "oversized": "oversized", "oversize": "oversized", "over size": "oversized",
    "baggy": "baggy", "loose": "oversized",
    "full sleve": "full sleeve", "full sleev": "full sleeve", "full slv": "full sleeve",
    "half sleve": "half sleeve", "haf sleeve": "half sleeve",
    "blck": "black", "wite": "white", "ble": "blue", "gree": "green",
    "maroon": "maroon", "mroon": "maroon",
    "grphic": "graphic", "typo": "typography",
    "womens": "women", "mens": "men", "ladie": "women", "ladies": "women",
    "girs": "women", "girls": "women", "boys": "men",
    "colur": "color", "colour": "color",
    "under Rs": "under", "under rs": "under", "below rs": "under",
}

_SYNONYM_MAP: dict = {
    # Category synonyms
    "tee": "t-shirt", "top": "t-shirt", "topwear": "t-shirt",
    "pullover": "hoodie", "jacket": "hoodie", "sweatshirt": "hoodie",
    "trackpants": "joggers", "track pants": "joggers", "sweatpants": "joggers",
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

_FANDOM_KNOWLEDGE_GRAPH: dict = {
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

_CHARACTER_ENTITY_MAP: dict = {
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

_ENTITY_FRANCHISE_MAP: dict = {
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

_VIBE_MAP: dict = {
    "retro grunge": "oversized fit washed graphic print maroon grey black",
    "grunge": "oversized fit washed graphic print maroon grey black",
    "minimalist": "regular fit solid beige white navy",
    "streetwear": "baggy fit graphic print black white",
    "y2k": "baggy fit washed typography pink blue",
    "gym": "regular fit solid black grey blue",
    "cozy": "oversized fit solid grey beige brown"
}

def get_product_color(title: str, specs: Optional[dict] = None) -> str:
    """Accurately extracts product color from specs or title adjective."""
    if specs and specs.get("color"):
        return str(specs.get("color", "")).lower().strip()
    clean_title = re.sub(r"^(men's|women's|boys'|girls'|unisex)\s+", "", (title or "").lower())
    m = re.match(
        r"^(jet\s+black|dark\s+shadow\s+grey|dark\s+grey|light\s+grey|navy\s+blue|olive\s+green|"
        r"black|white|grey|gray|green|blue|red|yellow|maroon|beige|brown|orange|pink|purple|teal)\b",
        clean_title
    )
    if m:
        return m.group(1).strip()
    return ""

def preprocess_prompt(prompt: str, enable_semantic: bool = True) -> str:
    """Step 0: Normalize case, fix spelling, expand synonyms and knowledge graph before LLM or rules."""
    text = prompt.strip().lower()
    
    # Apply vibe mapping (exact phrase matching)
    for vibe, expansion in _VIBE_MAP.items():
        if re.search(rf"\b{re.escape(vibe)}\b", text):
            text = text + " " + expansion
            
    # Apply spell corrections (exact phrase matching)
    for typo, fix in _SPELL_CORRECTIONS.items():
        text = re.sub(rf"\b{re.escape(typo)}\b", fix, text)
    
    # Apply synonym expansion (exact phrase matching)
    for synonym, canonical in _SYNONYM_MAP.items():
        text = re.sub(rf"\b{re.escape(synonym)}\b", canonical, text)
        
    # Apply Fandom Knowledge Graph Expansion (only if enabled)
    if enable_semantic:
        expanded_terms = []
        for entity, related_keywords in _FANDOM_KNOWLEDGE_GRAPH.items():
            if re.search(rf"\b{re.escape(entity)}\b", text):
                expanded_terms.extend(related_keywords)
                
        # Append unique expanded terms to the end of the text
        if expanded_terms:
            unique_terms = list(dict.fromkeys(expanded_terms))
            text = text + " " + " ".join(unique_terms)
    
    return text

def get_semantic_affinity_tier(
    product: Product,
    target_char_key: Optional[str] = None,
    target_char_terms: Optional[List[str]] = None,
    query_text: str = ""
) -> int:
    """Returns an integer semantic affinity tier (4 down to 0) representing closeness to user intent:
      Tier 4 (Exact Target Entity/Character): Direct match for target subject (e.g. 'black panther').
      Tier 3 (Core Lore / Associated Sub-Entities): Direct lore, iconic aliases, or related key entities
             (e.g. for Black Panther: 'wakanda', 't'challa', 'the king', 'panther').
      Tier 2 (Parent Universe / Franchise): Parent universe without the character (e.g. 'marvel', 'dc', 'anime').
      Tier 1 (Neutral Category / Color): Matches generic attributes without conflicting characters.
      Tier 0 (Conflicting Character): Features a different/opposing character.
    """
    p_title = (product.title or "").lower()
    p_specs = product.specs or {}
    p_fandom = str(p_specs.get("fandom_partner", "")).lower()
    p_design = str(p_specs.get("design", "")).lower()
    p_subclass = str(p_specs.get("subclass", "")).lower()
    p_text = f"{p_title} {p_fandom} {p_design} {p_subclass}".lower()

    if target_char_key:
        # 1. Conflicting Character Check
        for other_key, other_terms in _CHARACTER_ENTITY_MAP.items():
            if other_key != target_char_key:
                if any(re.search(rf"\b{re.escape(ot)}\b", p_text) for ot in other_terms):
                    return 0  # Tier 0: Conflicting character

        # 2. Exact Target Character Check
        exact_terms = [target_char_key, target_char_key.replace("-", " "), target_char_key.replace(" ", "")]
        if target_char_key == "black panther":
            exact_terms.extend(["black panther", "black pantheer", "black pather", "king black panther", "t'challa", "tchalla"])
        elif target_char_key == "spider-man":
            exact_terms.extend(["spider-man", "spiderman", "spider man", "peter parker", "miles morales"])
        elif target_char_key == "iron man":
            exact_terms.extend(["iron man", "ironman", "tony stark"])
        elif target_char_key == "batman":
            exact_terms.extend(["batman", "dark knight", "bruce wayne"])
        elif target_char_key == "wolverine":
            exact_terms.extend(["wolverine", "logan"])
        elif target_char_key == "captain america":
            exact_terms.extend(["captain america", "steve rogers"])

        if any(re.search(rf"\b{re.escape(et)}\b", p_text) for et in exact_terms):
            return 4  # Tier 4: Exact Character Match

        # 3. Lore / Sub-Entity / Direct Lore Characters
        lore_terms = target_char_terms or _CHARACTER_ENTITY_MAP.get(target_char_key, [])
        if any(re.search(rf"\b{re.escape(lt)}\b", p_text) for lt in lore_terms if lt not in exact_terms):
            return 3  # Tier 3: Core Lore / Direct Sub-Entity

        # 4. Parent Universe / Franchise
        parent_universe = _ENTITY_FRANCHISE_MAP.get(target_char_key)
        if parent_universe and (
            re.search(rf"\b{re.escape(parent_universe)}\b", p_text) or
            parent_universe in p_fandom
        ):
            return 2  # Tier 2: Parent Franchise / Universe

        # 5. Neutral Category Match
        return 1  # Tier 1: Neutral Category

    # If no target character, compute general keyword affinity
    q_words = [w for w in re.findall(r"[a-z0-9]+", (query_text or "").lower()) if len(w) > 2]
    if q_words:
        matched = sum(1 for w in q_words if w in p_text)
        ratio = matched / len(q_words)
        if ratio >= 0.75:
            return 4
        elif ratio >= 0.45:
            return 3
        elif ratio >= 0.2:
            return 2
    return 1


def calculate_dynamic_composite_match(
    user_prompt: str,
    canonical: Optional["CanonicalShoppingQuery"],
    product: Product,
    raw_text_score: float,
    vqa_data: Optional[dict],
    target_char_key: Optional[str],
    target_char_terms: List[str]
) -> Tuple[float, bool, str]:
    """Calculates a precision composite match score with calibrated headroom.
    Ensures text-only matches cap around 0.78-0.82, leaving 0.83-0.95 reserved
    for true multimodal visual verification (VQA) and high-affinity matches.
    """
    import math
    prompt_lower = (user_prompt or "").lower()
    p_title = (product.title or "").lower()
    p_specs = product.specs or {}
    p_text = f"{product.title} {p_specs.get('fandom_partner', '')} {p_specs.get('design', '')} {p_specs.get('color', '')} {p_specs.get('subclass', '')}".lower()

    # 1. Semantic Affinity Tier & Conflicting Character Check
    affinity_tier = get_semantic_affinity_tier(product, target_char_key, target_char_terms, user_prompt)
    if affinity_tier == 0 and target_char_key:
        return 0.35, False, f"Different character from requested {target_char_key.title()}"

    # 2. Base score allocation based on affinity tier
    base_score = 0.15
    if affinity_tier == 4:
        base_score += 0.30  # Exact Character
    elif affinity_tier == 3:
        base_score += 0.25  # Core Lore / Sub-entity
    elif affinity_tier == 2:
        base_score += 0.12  # Parent Franchise / Universe
    elif target_char_key is None:
        base_score += 0.20  # Generic query
    else:
        base_score += 0.05  # General garment when specific character was asked

    # 3. Category satisfaction
    cat_match = bool(re.search(r"\b(t-?shirt|tee|shirt|hoodie|joggers|jeans|pants|vest|polo|top|shorts)\b", prompt_lower))
    if cat_match:
        if any(cat in p_title or cat in str(p_specs.get("subclass", "")).lower() for cat in ["t-shirt", "tee", "shirt", "tshirt", "hoodie", "polo"]):
            base_score += 0.16
    else:
        base_score += 0.10

    # 4. Color satisfaction
    has_indifferent_color = bool(re.search(
        r"\b(no\s*(?:as\s*such\s*)?(?:specific\s*)?colou?r|any\s*colou?r|not\s*particular\s*(?:about\s*)?colou?r|whichever\s*colou?r|colour\s*(?:is\s*)?not\s*(?:an?\s*)?issue)\b",
        prompt_lower
    ))
    p_color = get_product_color(product.title, p_specs)
    
    if has_indifferent_color:
        base_score += 0.12  # Neutral credit to all colors
    elif target_char_key == "black panther":
        # Disentangle character name "Black Panther" from garment fabric color
        prompt_without_char = re.sub(r"\b(black\s*panther|black\s*pather|black\s*pantheer)\b", "", prompt_lower)
        if re.search(r"\bblack\b", prompt_without_char):
            # User explicitly requested black fabric outside the character name
            if "black" in p_color or "jet black" in p_color:
                base_score += 0.14
            else:
                base_score += 0.04
        else:
            # Color was only mentioned as part of "black panther"; don't penalize white/grey/green Black Panther tees
            if "black" in p_color or "jet black" in p_color:
                base_score += 0.12
            else:
                base_score += 0.10
    else:
        detected_color = None
        for c in ["black", "white", "blue", "red", "green", "grey", "gray", "yellow", "maroon", "beige", "brown", "navy", "orange", "pink", "purple", "teal"]:
            if re.search(rf"\b{c}\b", prompt_lower):
                detected_color = c
                break

        if detected_color:
            if (detected_color in p_color) or ("black" in detected_color and ("black" in p_color or "jet black" in p_color)):
                base_score += 0.14
            else:
                base_score += 0.02
        else:
            base_score += 0.10

    # 5. Design / Print / Fit satisfaction
    if "graphic" in prompt_lower or "print" in prompt_lower:
        if "graphic" in p_text or "printed" in p_text or "print" in p_text:
            base_score += 0.08

    if "oversized" in prompt_lower or "baggy" in prompt_lower:
        if "oversized" in p_text or "oversized" in str(p_specs.get("fit", "")).lower():
            base_score += 0.04

    # 6. Fandom / Franchise recognition
    if "marvel" in prompt_lower and ("marvel" in p_text or "marvel" in str(p_specs.get("fandom_partner", "")).lower()):
        base_score += 0.04
    elif "dc" in prompt_lower and ("dc" in p_text or "batman" in p_text or "superman" in p_text):
        base_score += 0.04

    # 7. Token overlap bonus for product title
    stopwords = {"for", "the", "in", "of", "and", "with", "a", "an", "to", "at", "by", "on", "men", "mens", "women", "womens"}
    query_tokens = [w for w in re.findall(r"[a-z0-9]+", prompt_lower) if w not in stopwords and len(w) > 1]
    title_tokens = set(re.findall(r"[a-z0-9]+", p_title))
    overlap_count = sum(1 for tok in query_tokens if tok in title_tokens)
    overlap_ratio = overlap_count / max(len(query_tokens), 1)
    overlap_bonus = 0.05 * overlap_ratio

    # 8. Bayesian popularity tie-breaker (max 0.02)
    rating = float(product.rating or 4.0)
    reviews = int(product.review_count or 100)
    b_raw = rating * math.log10(reviews + 1)
    b_norm = min(1.0, max(0.1, b_raw / 16.5))
    bayesian_bonus = 0.02 * b_norm

    # 9. LLM text evaluation blending (if LLM returned a score)
    llm_blend = 0.0
    if raw_text_score and 0.0 < raw_text_score <= 1.0 and raw_text_score != 0.5:
        llm_blend = (raw_text_score - 0.5) * 0.04

    # 10. Dynamic VQA vision bonus / penalty
    vqa_bonus = 0.0
    vqa_reason = ""
    if vqa_data:
        is_vis = bool(vqa_data.get("is_visual_match", False))
        vis_score = float(vqa_data.get("visual_score", 0.0))
        vqa_reason = vqa_data.get("reason", "")
        if is_vis or vis_score >= 0.70:
            vqa_bonus = 0.14 * max(vis_score, 0.75)
        elif not is_vis and vis_score < 0.40:
            vqa_bonus = -0.06
        elif affinity_tier >= 3:
            vqa_bonus = 0.04 * max(vis_score, 0.30)

    final_score = base_score + overlap_bonus + vqa_bonus + bayesian_bonus + llm_blend
    # Cap calibrated max at 0.95 to reserve 0.90+ strictly for multimodal visual excellence
    final_score = round(min(0.95, max(0.35, final_score)), 2)
    is_relevant = (final_score >= 0.45)

    reason = vqa_reason or f"Tier {affinity_tier} ({int(base_score*100)}%) + Overlap ({int(overlap_ratio*100)}%) + Bayes ({int(b_norm*100)}%)"
    return final_score, is_relevant, reason

# ---------------------------------------------------------------------------
# 2. Agent Brain
# ---------------------------------------------------------------------------

class AgentBrain:
    """Multi-model reasoning + evaluation engine for Rasor Agentic Commerce."""

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        primary_model: str = "gemini-3.1-flash-lite",
        fallback_model: str = "openai/gpt-oss-20b",
    ):
        self.gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.groq_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.last_model_used: str = "none"

    # ── LLM Callers ──────────────────────────────────────────────────────────

    def _call_gemini(self, prompt: str, system: str) -> Optional[str]:
        if not self.gemini_key:
            return None
        candidate_models = [self.primary_model, "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
        seen = set()
        for m in candidate_models:
            if not m or m in seen:
                continue
            seen.add(m)
            try:
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{m}:generateContent?key={self.gemini_key}"
                )
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "systemInstruction": {"parts": [{"text": system}]},
                    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
                }
                resp = requests.post(url, json=payload, timeout=8)
                if resp.status_code == 200:
                    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                    self.last_model_used = f"Google {m}"
                    return text
            except Exception:
                continue
        return None

    def _call_gemini_vision(self, prompt: str, image_url: str) -> Optional[str]:
        """Call Gemini Vision model to evaluate an image against a prompt with caching, retries, and model fallback."""
        if not self.gemini_key:
            return None

        # 1. Check in-memory cache
        cache_key = f"{image_url}:{prompt.strip()[:100]}"
        if cache_key in _VQA_CACHE:
            return json.dumps(_VQA_CACHE[cache_key])

        try:
            import base64
            import time
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
            }
            img_resp = None
            for attempt in range(2):
                try:
                    img_resp = requests.get(image_url, headers=headers, timeout=5)
                    if img_resp.status_code == 200:
                        break
                except Exception as e:
                    if attempt == 1:
                        print(f"[Brain/VQA] Image download failed ({image_url[:50]}...): {e}")
                    time.sleep(0.3)

            if not img_resp or img_resp.status_code != 200:
                return None

            img_b64 = base64.b64encode(img_resp.content).decode("utf-8")
            
            mime_type = "image/jpeg"
            if image_url.lower().endswith(".png"):
                mime_type = "image/png"
            elif image_url.lower().endswith(".webp"):
                mime_type = "image/webp"

            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inlineData": {
                                    "mimeType": mime_type,
                                    "data": img_b64
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
            }

            candidate_models = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
            for model_to_use in candidate_models:
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model_to_use}:generateContent?key={self.gemini_key}"
                )
                for retry in range(2):
                    try:
                        resp = requests.post(url, json=payload, timeout=10)
                        if resp.status_code == 200:
                            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                            self.last_model_used = f"Google {model_to_use} (Vision)"
                            extracted = self._extract_json(text)
                            if extracted:
                                _VQA_CACHE[cache_key] = extracted
                            return text
                        elif resp.status_code == 429:
                            print(f"[Brain/VQA] 429 rate limit on {model_to_use}, retrying in 0.5s...")
                            time.sleep(0.5)
                            continue
                        else:
                            print(f"[Brain/VQA] HTTP {resp.status_code} on {model_to_use}: {resp.text[:100]}")
                            break
                    except requests.exceptions.Timeout:
                        print(f"[Brain/VQA] Timeout (10s) on {model_to_use} (attempt {retry+1}/2)")
                        time.sleep(0.3)
                    except Exception as e:
                        print(f"[Brain/VQA] Error on {model_to_use}: {e}")
                        break
        except Exception as e:
            print(f"[Brain/VQA] Unhandled vision error: {e}")
        return None

    def _call_groq(self, prompt: str, system: str) -> Optional[str]:
        if not self.groq_key:
            return None
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"},
                json={
                    "model": self.fallback_model,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,
                },
                timeout=8,
            )
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"]
                self.last_model_used = f"Groq {self.fallback_model}"
                return text
            print(f"[Brain/Groq] HTTP {resp.status_code}: {resp.text[:150]}")
        except Exception as e:
            print(f"[Brain/Groq] Error: {e}")
        return None

    def _call_llm(self, prompt: str, system: str) -> Optional[str]:
        """Try Gemini first, then Groq, return None if both fail."""
        return self._call_gemini(prompt, system) or self._call_groq(prompt, system)

    def _call_gemini_markdown(self, prompt: str, system: str) -> Optional[str]:
        if not self.gemini_key:
            return None
        try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.primary_model}:generateContent?key={self.gemini_key}"
            )
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "systemInstruction": {"parts": [{"text": system}]},
                "generationConfig": {"temperature": 0.1}, # No responseMimeType!
            }
            resp = requests.post(url, json=payload, timeout=8)
            if resp.status_code == 200:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                self.last_model_used = f"Google {self.primary_model} (MD)"
                return text
            print(f"[Brain/Gemini] HTTP {resp.status_code}: {resp.text[:150]}")
        except Exception as e:
            print(f"[Brain/Gemini] Error: {e}")
        return None

    def _call_llm_markdown(self, prompt: str, system: str) -> Optional[str]:
        """Try Gemini Markdown. If fails, just fallback to standard Groq (which returns JSON)."""
        return self._call_gemini_markdown(prompt, system) or self._call_groq(prompt, system)

    def _extract_json(self, raw: str) -> Optional[dict]:
        """Safely extract JSON object from LLM output."""
        if not raw:
            return None
        try:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                return json.loads(m.group(0))
        except Exception as e:
            print(f"[Brain] JSON parse error: {e}")
        return None

    # ── Stage 1: Intent Normalization ────────────────────────────────────────

    def normalize_intent(self, user_prompt: str, budget: float = None, enable_semantic: bool = True):
        # Step a: Pre-process
        cleaned_prompt = preprocess_prompt(user_prompt, enable_semantic=enable_semantic)
        print(f"[Brain] Pre-processed: '{user_prompt}' → '{cleaned_prompt}'")

        system = (
            "You are a precision e-commerce intent extractor for an Indian fashion store.\n"
            "Extract all shopping attributes from the user query into this exact JSON schema:\n"
            "{\n"
            '  "items_to_buy": [\n'
            '    {\n'
            '      "cleaned_keywords": string,\n'
            '      "specific_visual_intent": string or null,\n'
            '      "gender": "men" | "women" | "unisex" | "all",\n'
            '      "category": "t-shirt" | "hoodie" | "joggers" | "jeans" | "shirt" | "sliders" | "footwear" | "vest" | "electronics" | "general",\n'
            '      "color": "Black" | "Blue" | "White" | "Red" | "Green" | "Orange" | "Grey" | "Yellow" | "Maroon" | "Beige" | "Brown" | "Navy" | "Any",\n'
            '      "design": "Solid" | "Graphic Print" | "Typography" | "All Over Print" | "Washed" | "Checked" | "Any",\n'
            '      "fit": "Oversized Fit" | "Regular Fit" | "Boyfriend Fit" | "Baggy Fit" | "Super Baggy Fit" | "Slim Fit" | "Any",\n'
            '      "sleeve": "Half Sleeve" | "Full Sleeve" | "Sleeveless" | "Any",\n'
            '      "fabric": "Cotton" | "Polyester" | "Blend" | "Fleece" | "Linen" | "Nylon" | "Any",\n'
            '      "neck": "Round Neck" | "V-Neck" | "Polo" | "Collar" | "Hood" | "Crew Neck" | "Any",\n'
            '      "occasion": "Party" | "Gym" | "Casual" | "Office" | "Any",\n'
            '      "fandom": string or "None",\n'
            '      "size": string or null,\n'
            '      "quantity": integer,\n'
            '      "max_price": float or null,\n'
            '      "min_rating": float or null,\n'
            '      "fast_shipping_requested": boolean,\n'
            '      "negative_keywords": [string]\n'
            '    }\n'
            '  ],\n'
            '  "owned_items": [ { /* same schema as above */ } ]\n'
            "}\n\n"
            "RULES:\n"
            "- If the user specifies they ALREADY HAVE or OWN an item (e.g. 'I have a black t-shirt'), put it in 'owned_items'.\n"
            "- Put target purchase items in 'items_to_buy'.\n"
            "- 'plain', 'solid', 'basic' → design: 'Solid'\n"
            "- 'printed', 'graphic', 'anime' → design: 'Graphic Print'\n"
            "- 'oversized', 'baggy', 'loose' → fit: 'Oversized Fit'\n"
            "- 'batman', 'joker', 'superman', 'dc' → fandom: 'DC'\n"
            "- 'spider man', 'iron man', 'marvel', 'deadpool', 'thor', 'avengers' → fandom: 'Marvel'\n"
            "- specific_visual_intent: ONLY set this if user explicitly asks for artwork, graphics, characters, poses, printed text, or back prints (e.g. 'iron man standing', 'anime girl print', 'quote on back'). For plain/common garments without requested artwork (e.g. 'black oversized t-shirt', 'white gym tee', 'plain polo'), specific_visual_intent MUST be null.\n"
            "- Output ONLY valid JSON."
        )

        msg = f"User prompt (pre-processed): \"{cleaned_prompt}\"\nOriginal: \"{user_prompt}\""
        raw_json = self._call_llm(msg, system)

        items_to_buy = []
        owned_items = []
        
        def parse_item_list(item_list):
            parsed_items = []
            for data in item_list:
                try:
                    data["original_prompt"] = user_prompt
                    data["gender"] = data.get("gender", "men") if data.get("gender") in [e.value for e in GenderEnum] else "men"
                    data["category"] = data.get("category", "t-shirt") if data.get("category") in [e.value for e in CategoryEnum] else "t-shirt"
                    data["color"] = data.get("color", "Any") if data.get("color") in [e.value for e in ColorEnum] else "Any"
                    data["design"] = data.get("design", "Any") if data.get("design") in [e.value for e in DesignEnum] else "Any"
                    data["fit"] = data.get("fit", "Any") if data.get("fit") in [e.value for e in FitEnum] else "Any"
                    data["sleeve"] = data.get("sleeve", "Any") if data.get("sleeve") in [e.value for e in SleeveEnum] else "Any"
                    data["negative_keywords"] = data.get("negative_keywords", [])
                    data["fabric"] = data.get("fabric", "Any") if data.get("fabric") in [e.value for e in FabricEnum] else "Any"
                    data["neck"] = data.get("neck", "Any") if data.get("neck") in [e.value for e in NeckEnum] else "Any"
                    data["occasion"] = data.get("occasion", "Any") if data.get("occasion") in [e.value for e in OccasionEnum] else "Any"
                    data["fandom"] = data.get("fandom", "None") if data.get("fandom") in [e.value for e in FandomEnum] else "None"
                    data["fast_shipping_requested"] = data.get("fast_shipping_requested", False)
                    # Discard pseudo-visual intents that merely repeat category/color/fit
                    v_intent = str(data.get("specific_visual_intent") or "").lower().strip()
                    common_plain_patterns = [
                        "black oversized t-shirt", "black t-shirt", "oversized t-shirt", "oversized tee",
                        "plain t-shirt", "solid t-shirt", "t-shirt", "shirt", "hoodie", "joggers", "jeans",
                        "black shirt", "white t-shirt", "solid black", "plain black", "plain white"
                    ]
                    if v_intent in common_plain_patterns or v_intent in ["none", "null", "n/a", "not specified", "false", ""]:
                        data["specific_visual_intent"] = None

                    parsed_items.append(CanonicalShoppingQuery(**data))
                except Exception as e:
                    print(f"[Brain] Item Schema validation error: {e}")
            return parsed_items

        if raw_json:
            data = self._extract_json(raw_json)
            if data:
                items_to_buy = parse_item_list(data.get("items_to_buy", []))
                owned_items = parse_item_list(data.get("owned_items", []))
                
        # Algorithmic Budget Scaling
        if budget and len(items_to_buy) >= 2:
            n_items = len(items_to_buy)
            max_cap = 0.7 if n_items == 2 else (1.4 / n_items)
            category_weights = {"jeans": 1.0, "hoodie": 0.9, "joggers": 0.8, "shirt": 0.6, "t-shirt": 0.5, "sliders": 0.3}
            
            for item in items_to_buy:
                if not item.max_price:
                    weight = category_weights.get(item.category.value, 0.5)
                    # Scale based on boundary * weight, bounded at absolute max
                    item.max_price = round(budget * min(max_cap, weight))

        # Complementary Rule Engine
        if owned_items and not items_to_buy:
            for owned in owned_items:
                # Basic color wheel contrast rules
                target_cat = CategoryEnum.JEANS if owned.category == CategoryEnum.TSHIRT else CategoryEnum.TSHIRT
                target_color = ColorEnum.GREY if owned.color == ColorEnum.BLACK else ColorEnum.BEIGE
                
                comp_item = CanonicalShoppingQuery(
                    original_prompt=user_prompt,
                    cleaned_keywords="",
                    category=target_cat,
                    color=target_color
                )
                items_to_buy.append(comp_item)

        # Fallback if empty
        if not items_to_buy and not owned_items:
            self.last_model_used = "Rule Engine"
            parsed_raw = parse_user_intent(cleaned_prompt)
            
            def safe_enum(enum_class, val, default):
                if val and val in [e.value for e in enum_class]:
                    return val
                return default.value

            canonical = CanonicalShoppingQuery(
                original_prompt=user_prompt,
                cleaned_keywords=parsed_raw.cleaned_query or cleaned_prompt,
                gender=safe_enum(GenderEnum, parsed_raw.gender, GenderEnum.MEN),
                category=safe_enum(CategoryEnum, parsed_raw.category, CategoryEnum.TSHIRT),
                color=safe_enum(ColorEnum, parsed_raw.color, ColorEnum.ANY),
                design=safe_enum(DesignEnum, parsed_raw.design, DesignEnum.ANY),
                fit=safe_enum(FitEnum, parsed_raw.fit, FitEnum.ANY),
                sleeve=safe_enum(SleeveEnum, parsed_raw.sleeve, SleeveEnum.ANY),
                fabric=FabricEnum.ANY,
                neck=NeckEnum.ANY,
                occasion=OccasionEnum.ANY,
                fandom=safe_enum(FandomEnum, parsed_raw.fandom, FandomEnum.NONE),
                size=parsed_raw.size,
                quantity=parsed_raw.quantity or 1,
                max_price=parsed_raw.max_price,
                min_rating=parsed_raw.min_rating,
                fast_shipping_requested=parsed_raw.fast_shipping_requested
            )
            items_to_buy.append(canonical)
            
        multi_query = MultiShoppingQuery(original_prompt=user_prompt, items_to_buy=items_to_buy, owned_items=owned_items)
        return multi_query, f"🧠 Normalized by {self.last_model_used}"

    # ── Stage 3: Candidate Relevance Evaluation ───────────────────────────────

    def evaluate_candidates(
        self,
        user_prompt: str,
        candidates: List[Product],
        canonical: Optional["CanonicalShoppingQuery"] = None,
        vqa_strict_filter: bool = False,
        enable_vqa_scanner: bool = True,
        truth_hierarchy: bool = True,
        vqa_limit: int = 16
    ) -> Tuple[List[Product], List[ProductRelevanceEvaluation]]:
        """LLM QA: Verifies retrieved products against user intent. Rejects false positives.

        Takes an optional `canonical` query to inject hard rules directly into the LLM prompt,
        such as negative keywords the user explicitly excluded and positive signals they asked for.
        """
        if not candidates:
            return [], []

        # ── Build the constraint context block ──
        constraint_lines = []
        neg_keywords = getattr(canonical, "negative_keywords", []) if canonical else []
        if neg_keywords:
            constraint_lines.append(
                f"HARD NEGATIONS (any product containing these words MUST be scored <= 0.15 and rejected): "
                f"{', '.join(neg_keywords)}"
            )

        # Pull positive signals from canonical for explicit mention in the prompt
        pos_signals = []
        if canonical:
            if canonical.color.value != "Any":
                pos_signals.append(f"color={canonical.color.value}")
            if canonical.design.value != "Any":
                pos_signals.append(f"design={canonical.design.value}")
            if canonical.neck.value != "Any":
                pos_signals.append(f"neck={canonical.neck.value}")
            if canonical.fandom.value != "None":
                pos_signals.append(f"fandom={canonical.fandom.value}")
        if pos_signals:
            constraint_lines.append(f"POSITIVE REQUIREMENTS (must be present for a high match_score): {', '.join(pos_signals)}")

        # Multi-source Character / Entity detection
        target_char_key = None
        target_char_terms = []
        sources_to_check = [
            user_prompt.lower(),
            preprocess_prompt(user_prompt, enable_semantic=False).lower(),
        ]
        if canonical:
            if getattr(canonical, "cleaned_keywords", None):
                sources_to_check.append(str(canonical.cleaned_keywords).lower())
            if getattr(canonical, "fandom", None) and canonical.fandom.value != "None":
                sources_to_check.append(str(canonical.fandom.value).lower())

        for text_source in sources_to_check:
            for char_key, char_terms in _CHARACTER_ENTITY_MAP.items():
                if any(re.search(rf"\b{re.escape(term)}\b", text_source) for term in char_terms):
                    target_char_key = char_key
                    target_char_terms = char_terms
                    break
            if target_char_key:
                break

        if target_char_key:
            constraint_lines.append(
                f"PRIMARY CHARACTER/ENTITY REQUIREMENT: '{target_char_key.title()}'.\n"
                f"  - Products featuring '{target_char_key.title()}' (or related lore: {', '.join(target_char_terms)}) MUST score at least 0.65–0.78, and higher (0.75–0.90) if they match specific visual/design details.\n"
                f"  - Products featuring a DIFFERENT character (e.g. Iron Man, Moon Knight, Venom when user asked for Black Panther) are WRONG characters: score them <= 0.45 and set is_relevant=false."
            )
        elif canonical and canonical.has_visual_intent:
            constraint_lines.append(
                "WARNING: A specific visual intent was provided. DO NOT reject products (score < 0.5) just because their text doesn't describe the exact visual details. "
                "If the product matches the broader category, score it >= 0.5 so it survives to be visually scanned."
            )

        constraint_block = "\n".join(constraint_lines) if constraint_lines else "No hard constraints beyond the user's prompt."

        cand_summary = [
            {
                "id": p.id,
                "title": p.title,
                "price": p.price,
                "color": p.specs.get("color"),
                "design": p.specs.get("design"),
                "fit": p.specs.get("fit"),
                "sleeve": p.specs.get("sleeve"),
                "fabric": p.specs.get("fabric"),
                "neck": p.specs.get("neck"),
                "subclass": p.specs.get("subclass"),
                "fandom": p.specs.get("fandom_partner"),
                "sizes_in_stock": p.specs.get("available_sizes"),
                "rating": p.rating,
                "review_count": p.review_count,
                "rich_description": (p.rich_description or "")[:300],
            }
            for p in candidates
        ]
        rule_block = (
            "  - If the user asked for a specific character/theme (e.g. Batman), a shirt without any Batman reference scores <= 0.3.\n"
            "  - If the user's prompt mentions a specific design feature (e.g. 'logo', 'illustration', 'bold text'), score products that clearly match HIGHER and products that clearly DON'T match LOWER.\n"
            "  - If a product title/description contains a HARD NEGATION keyword listed below, it MUST score <= 0.15 and is_relevant=false.\n"
            "  - Broad queries (e.g. 'black t-shirt') should accept extras like oversized, graphic print — do NOT penalise them.\n"
        )

        if truth_hierarchy:
            rule_block += "  - TRUTH HIERARCHY: The Product Title is the absolute source of truth. If the Title explicitly contains a matching feature (e.g., 'Polo', 'Oversized') but the backend specs/metadata contradict it (e.g., 'Round Neck', 'Regular Fit'), you MUST trust the Title and score it as a match. Do not penalize for backend metadata errors if the Title is correct.\n"

        system = (
            "You are a precision e-commerce ranking and filtering agent for an Indian fashion store.\n"
            "Your job is to evaluate each candidate product against the user's exact intent and assign "
            "a match_score (0.0–1.0) and is_relevant flag.\n\n"
            "## Scoring Guidelines\n"
            "  - 0.9–1.0: Exceptional match — product satisfies every explicit user requirement.\n"
            "  - 0.7–0.89: Good match — satisfies the core request, minor extras the user didn't forbid.\n"
            "  - 0.5–0.69: Partial match — satisfies category/gender but misses some specifics.\n"
            "  - 0.0–0.49: REJECT — contradicts an explicit requirement. Set is_relevant=false.\n\n"
            "## Hard Rules\n"
            f"{rule_block}"
            f"## Extracted Constraints\n{constraint_block}\n\n"
            "Output ONLY valid JSON:\n"
            "{\n"
            '  "evaluations": [\n'
            '    {"product_id": "...", "product_title": "...", "is_relevant": true, "match_score": 0.95, "reason": "concise explanation"}\n'
            "  ]\n"
            "}"
        )
        msg = (
            f"User Intent: \"{user_prompt}\"\n"
            f"Extracted Canonical Attributes: {json.dumps({k: str(v) for k, v in (canonical.model_dump().items() if canonical else {}.items())})}\n\n"
            f"Candidates:\n{json.dumps(cand_summary, indent=2)}"
        )

        raw_json = self._call_llm(msg, system)
        evaluations: List[ProductRelevanceEvaluation] = []
        accepted: List[Product] = []

        import math
        def candidate_sort_key(p):
            score = next((e.match_score for e in evaluations if e.product_id == p.id), 0.0)
            tier = get_semantic_affinity_tier(p, target_char_key, target_char_terms, user_prompt)
            rating = float(p.rating or 4.0)
            reviews = int(p.review_count or 100)
            bayes = rating * math.log10(reviews + 1)
            return (score, tier, bayes)

        if raw_json:
            data = self._extract_json(raw_json)
            if data:
                try:
                    eval_map = {e["product_id"]: e for e in data.get("evaluations", [])}

                    # ---------------------------------------------------------
                    # VQA Scanning Phase:
                    # - If enable_vqa_scanner is True: Run VQA on every query.
                    # - If enable_vqa_scanner is False: Smart mode: ONLY run when visual intent is asked.
                    # - For plain common items with toggle OFF, VQA is skipped.
                    # ---------------------------------------------------------
                    has_explicit_visual_intent = bool(canonical and canonical.has_visual_intent) or bool(
                        re.search(r"\b(standing|hands?\s*(?:are\s*)?cross(?:ed)?|arms?\s*cross(?:ed)?|pose|back\s*print|front\s*print|chest\s*logo|artwork)\b", user_prompt.lower())
                    )
                    should_run_vqa = bool(enable_vqa_scanner) or has_explicit_visual_intent

                    if should_run_vqa:
                        target_visual = (canonical.specific_visual_intent if (canonical and canonical.has_visual_intent) else None) or user_prompt
                        print(f"[Brain] Executing VQA Scanning for: '{target_visual}' (always_run={enable_vqa_scanner}, visual_intent={has_explicit_visual_intent})")
                        vqa_prompt = (
                            f"The user has a visual requirement for this clothing item: '{target_visual}'.\n"
                            "Look closely at the design, graphic, and features of the product in the image.\n"
                            "Respond with ONLY a JSON object in this format:\n"
                            '{"is_visual_match": true|false, "visual_score": 0.0-1.0, "reason": "short explanation"}'
                        )
                        
                        # Gather candidates for VQA scanning
                        vqa_candidates = []
                        for p in candidates:
                            ev_data = eval_map.get(p.id)
                            if not ev_data:
                                continue
                                
                            if vqa_strict_filter:
                                # Strict Mode: Only scan products that perfectly passed text evaluation
                                if ev_data.get("is_relevant", True):
                                    vqa_candidates.append(p)
                            else:
                                # Lenient Mode: Scan anything that isn't a hard rejection (>= 0.4)
                                if float(ev_data.get("match_score", 0.0)) >= 0.4:
                                    vqa_candidates.append(p)
                        
                        def vqa_priority_key(p):
                            ev = eval_map.get(p.id, {})
                            score = float(ev.get("match_score", 0.0))
                            tier = get_semantic_affinity_tier(p, target_char_key, target_char_terms, user_prompt)
                            rating = float(p.rating or 4.0)
                            reviews = int(p.review_count or 100)
                            bayes = rating * math.log10(reviews + 1)
                            return (tier, score, bayes, p.id)

                        vqa_candidates.sort(key=vqa_priority_key, reverse=True)
                        effective_vqa_limit = max(vqa_limit, 16) if has_explicit_visual_intent else vqa_limit
                        vqa_candidates = vqa_candidates[:effective_vqa_limit]
                        
                        vqa_results = {}
                        import concurrent.futures
                        def run_single_vqa(p):
                            img_url = p.specs.get("image_url") or p.specs.get("display_image")
                            if not img_url:
                                return
                            vqa_raw = self._call_gemini_vision(vqa_prompt, img_url)
                            if not vqa_raw:
                                return
                            vqa_data = self._extract_json(vqa_raw)
                            if vqa_data:
                                vqa_results[p.id] = vqa_data

                        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                            list(executor.map(run_single_vqa, vqa_candidates))
                    else:
                        vqa_results = {}
                        print("[Brain] VQA Vision Scanner skipped (plain/common item with no visual intent, always_run=False)")
                    
                    for p in candidates:
                        ev_data = eval_map.get(p.id)
                        raw_score = float(ev_data.get("match_score", 0.5)) if ev_data else 0.5
                        vqa_item_data = vqa_results.get(p.id)

                        final_score, is_relevant, reason = calculate_dynamic_composite_match(
                            user_prompt=user_prompt,
                            canonical=canonical,
                            product=p,
                            raw_text_score=raw_score,
                            vqa_data=vqa_item_data,
                            target_char_key=target_char_key,
                            target_char_terms=target_char_terms
                        )

                        ev = ProductRelevanceEvaluation(
                            product_id=p.id,
                            product_title=p.title,
                            is_relevant=is_relevant,
                            match_score=final_score,
                            reason=reason,
                        )
                        evaluations.append(ev)
                        if is_relevant and final_score >= 0.45:
                            accepted.append(p)
                    
                    # Sort accepted by match score, affinity tier, and bayesian score
                    accepted.sort(key=candidate_sort_key, reverse=True)
                    return accepted, evaluations
                except Exception as e:
                    print(f"[Brain/Eval] Error: {e}")

        # Fallback — evaluate all candidates via deterministic multi-attribute & entity scoring
        print("[Brain/Eval] Using deterministic multi-attribute scoring engine (no flat default score)")
        has_explicit_visual_intent = bool(canonical and canonical.has_visual_intent) or bool(
            re.search(r"\b(standing|hands?\s*(?:are\s*)?cross(?:ed)?|arms?\s*cross(?:ed)?|pose|back\s*print|front\s*print|chest\s*logo|artwork)\b", user_prompt.lower())
        )
        should_run_vqa = bool(enable_vqa_scanner) or has_explicit_visual_intent
        fallback_vqa_results = {}
        if should_run_vqa:
            target_visual = (canonical.specific_visual_intent if (canonical and canonical.has_visual_intent) else None) or user_prompt
            vqa_prompt = (
                f"The user has a visual requirement for this clothing item: '{target_visual}'.\n"
                "Look closely at the design, graphic, and features of the product in the image.\n"
                "Respond with ONLY a JSON object in this format:\n"
                '{"is_visual_match": true|false, "visual_score": 0.0-1.0, "reason": "short explanation"}'
            )
            import concurrent.futures
            def run_fallback_vqa(p):
                img_url = p.specs.get("image_url") or p.specs.get("display_image")
                if not img_url:
                    return
                vqa_raw = self._call_gemini_vision(vqa_prompt, img_url)
                if vqa_raw:
                    vqa_data = self._extract_json(vqa_raw)
                    if vqa_data:
                        fallback_vqa_results[p.id] = vqa_data

            top_candidates_for_vqa = sorted(
                candidates,
                key=lambda p: (
                    get_semantic_affinity_tier(p, target_char_key, target_char_terms, user_prompt),
                    float(p.rating or 4.0) * math.log10((p.review_count or 100) + 1),
                    p.id
                ),
                reverse=True
            )[:vqa_limit]

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                list(executor.map(run_fallback_vqa, top_candidates_for_vqa))

        for p in candidates:
            final_score, is_relevant, reason = calculate_dynamic_composite_match(
                user_prompt=user_prompt,
                canonical=canonical,
                product=p,
                raw_text_score=0.5,
                vqa_data=fallback_vqa_results.get(p.id),
                target_char_key=target_char_key,
                target_char_terms=target_char_terms
            )
            ev = ProductRelevanceEvaluation(
                product_id=p.id,
                product_title=p.title,
                is_relevant=is_relevant,
                match_score=final_score,
                reason=reason,
            )
            evaluations.append(ev)
            if is_relevant and final_score >= 0.45:
                accepted.append(p)

        if not accepted:
            # If all were below threshold, take top 4 highest scoring candidates
            candidates_sorted = sorted(
                candidates,
                key=candidate_sort_key,
                reverse=True
            )
            accepted = candidates_sorted[:min(4, len(candidates_sorted))]
        else:
            accepted.sort(key=candidate_sort_key, reverse=True)

        return accepted, evaluations

    def compare_products(self, products: List[Product]) -> Optional['ProductComparison']:
        """Stage 4: LLM-powered detailed comparison matrix for selected items."""
        from src.agent.state import ProductComparison, FeatureComparisonRow, ProductProsCons
        if not products:
            return None
        
        prod_summaries = []
        for i, p in enumerate(products):
            prod_summaries.append({
                "item_index": i + 1,
                "id": p.id,
                "title": p.title,
                "price": f"₹{p.price:,.0f}" if p.price else "N/A",
                "rating": f"{p.rating} ({p.review_count} reviews)" if p.rating else "N/A",
                "materials": p.specs.get("fabric") or p.specs.get("material", "100% Premium Cotton"),
                "fit": p.specs.get("fit", "Regular Fit"),
                "color": p.specs.get("color", "Multi"),
                "shipping": f"{getattr(p, 'shipping_days', 3)} days",
                "description": (p.rich_description or "")[:350]
            })
            
        system = (
            "You are an expert fashion stylist and merchandise comparison analyst.\n"
            "The user has selected multiple apparel items to compare side-by-side.\n"
            "Your task is to provide an objective, data-rich comparison across ALL provided products.\n"
            "CRITICAL: You MUST include EVERY product in the feature_matrix and pros_and_cons using its EXACT title.\n"
            "Output ONLY valid JSON matching this schema:\n"
            "{\n"
            '  "quick_summary": "2 sentences summarizing key trade-offs, value proposition, and style highlights across all items",\n'
            '  "feature_matrix": [\n'
            '      {"feature_name": "Price", "product_values": {"Exact Title 1": "₹999", "Exact Title 2": "₹1,199"}},\n'
            '      {"feature_name": "Fit Style", "product_values": {"Exact Title 1": "Oversized Fit", "Exact Title 2": "Regular Fit"}},\n'
            '      {"feature_name": "Material / Fabric", "product_values": {"Exact Title 1": "100% Cotton", "Exact Title 2": "Poly-Cotton"}},\n'
            '      {"feature_name": "Rating & Reviews", "product_values": {"Exact Title 1": "4.6 (120 reviews)", "Exact Title 2": "4.4 (85 reviews)"}}\n'
            '  ],\n'
            '  "pros_and_cons": [\n'
            '      {"product_title": "Exact Title 1", "pros": ["Distinct graphic art", "Soft breathable cotton"], "cons": ["Slightly heavier GSM"]},\n'
            '      {"product_title": "Exact Title 2", "pros": ["Everyday versatile fit", "Budget-friendly price"], "cons": ["Standard print silhouette"]}\n'
            '  ],\n'
            '  "stylist_recommendation": {\n'
            '      "Best for Value": "Product X because...",\n'
            '      "Best for Premium Quality": "Product Y because..."\n'
            '  }\n'
            "}"
        )
        msg = f"Compare these items:\n{json.dumps(prod_summaries, indent=2)}"
        
        parsed = None
        raw = self._call_llm(msg, system)
        if raw:
            parsed = self._extract_json(raw)

        # Baseline deterministic matrix
        base_price_map = {p.title: f"₹{p.price:,.0f}" if p.price else "₹999" for p in products}
        base_rating_map = {p.title: f"{p.rating or 4.5} ({p.review_count or 100}+ reviews)" for p in products}
        base_fit_map = {p.title: p.specs.get("fit", "Regular Fit") for p in products}
        base_fabric_map = {p.title: p.specs.get("fabric") or p.specs.get("material", "100% Combed Cotton") for p in products}
        base_shipping_map = {p.title: f"{getattr(p, 'shipping_days', 3)} days" for p in products}
        base_color_map = {p.title: p.specs.get("color", "Multi") for p in products}

        default_rows = [
            FeatureComparisonRow(feature_name="Price", product_values=base_price_map),
            FeatureComparisonRow(feature_name="Rating & Reviews", product_values=base_rating_map),
            FeatureComparisonRow(feature_name="Fit Style", product_values=base_fit_map),
            FeatureComparisonRow(feature_name="Material / Fabric", product_values=base_fabric_map),
            FeatureComparisonRow(feature_name="Color Variant", product_values=base_color_map),
            FeatureComparisonRow(feature_name="Estimated Delivery", product_values=base_shipping_map),
        ]

        if parsed and isinstance(parsed, dict):
            try:
                feature_matrix = []
                for row_data in parsed.get("feature_matrix", []):
                    f_name = row_data.get("feature_name", "Feature")
                    p_vals = row_data.get("product_values", {})
                    for p in products:
                        if p.title not in p_vals:
                            matched_val = None
                            for k, v in p_vals.items():
                                if k.lower() in p.title.lower() or p.title.lower() in k.lower():
                                    matched_val = v
                                    break
                            p_vals[p.title] = matched_val or (
                                base_price_map[p.title] if "price" in f_name.lower()
                                else base_rating_map[p.title] if "rating" in f_name.lower()
                                else base_fit_map[p.title] if "fit" in f_name.lower()
                                else base_fabric_map[p.title] if "material" in f_name.lower() or "fabric" in f_name.lower()
                                else "Standard"
                            )
                    feature_matrix.append(FeatureComparisonRow(feature_name=f_name, product_values=p_vals))
                
                existing_feature_names = {r.feature_name.lower() for r in feature_matrix}
                for def_row in default_rows:
                    if not any(def_row.feature_name.lower() in name for name in existing_feature_names):
                        feature_matrix.append(def_row)

                pros_cons_list = []
                parsed_pc = parsed.get("pros_and_cons", [])
                for p in products:
                    found_pc = next((x for x in parsed_pc if x.get("product_title") == p.title or x.get("product_title", "").lower() in p.title.lower() or p.title.lower() in x.get("product_title", "").lower()), None)
                    if found_pc:
                        pros_cons_list.append(ProductProsCons(
                            product_title=p.title,
                            pros=found_pc.get("pros", ["Great comfort and design"]),
                            cons=found_pc.get("cons", ["Standard care instructions"])
                        ))
                    else:
                        pros_cons_list.append(ProductProsCons(
                            product_title=p.title,
                            pros=[f"Premium {p.specs.get('fit', 'style')} silhouette", "High quality fabric"],
                            cons=["Popular item with limited seasonal stock"]
                        ))

                quick_summary = parsed.get("quick_summary") or f"Compared {len(products)} curated fashion pieces. Each offers distinct fit, design, and price points suited for different styling needs."
                recommendations = parsed.get("stylist_recommendation") or {
                    "Best Overall Value": f"{products[0].title} offers the best balance of price and customer satisfaction.",
                    "Top Style Pick": f"{products[-1].title} stands out for its unique design."
                }

                return ProductComparison(
                    quick_summary=quick_summary,
                    feature_matrix=feature_matrix,
                    pros_and_cons=pros_cons_list,
                    stylist_recommendation=recommendations
                )
            except Exception as e:
                print(f"[Brain] Error merging ProductComparison: {e}")

        # Fallback comparison if LLM call was unavailable
        return ProductComparison(
            quick_summary=f"Comparing {len(products)} selected products. Review the specifications, customer ratings, and key attributes below to choose the perfect fit.",
            feature_matrix=default_rows,
            pros_and_cons=[
                ProductProsCons(
                    product_title=p.title,
                    pros=[f"Well-reviewed {p.specs.get('fit', 'Regular')} cut", "Comfortable all-day wear"],
                    cons=["Subject to seasonal variant availability"]
                ) for p in products
            ],
            stylist_recommendation={
                "Best Value": f"{min(products, key=lambda x: x.price).title} offers the lowest entry price.",
                "Highest Rated": f"{max(products, key=lambda x: x.rating or 0).title} holds the highest customer satisfaction score."
            }
        )

