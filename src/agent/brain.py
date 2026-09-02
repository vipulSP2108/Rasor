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
    "batman": "batman", "bataman": "batman", "btaman": "batman",
    "spiderman": "spider man", "spiderman": "spider man",
    "ironman": "iron man", "iron-man": "iron man",
    "captainamerica": "captain america",
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
    "black panther": ["wakanda", "forever", "t'challa", "vibranium", "marvel"],
    "panther": ["wakanda", "forever", "t'challa", "vibranium", "marvel"],
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

_VIBE_MAP: dict = {
    "retro grunge": "oversized fit washed graphic print maroon grey black",
    "grunge": "oversized fit washed graphic print maroon grey black",
    "minimalist": "regular fit solid beige white navy",
    "streetwear": "baggy fit graphic print black white",
    "y2k": "baggy fit washed typography pink blue",
    "gym": "regular fit solid black grey blue",
    "cozy": "oversized fit solid grey beige brown"
}

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
        """Call Gemini Vision model to evaluate an image against a prompt."""
        if not self.gemini_key:
            return None
        try:
            # 1. Download image with strict timeout
            import base64
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
            }
            img_resp = requests.get(image_url, headers=headers, timeout=3)
            if img_resp.status_code != 200:
                return None
            img_b64 = base64.b64encode(img_resp.content).decode("utf-8")
            
            mime_type = "image/jpeg"
            if image_url.lower().endswith(".png"):
                mime_type = "image/png"
            elif image_url.lower().endswith(".webp"):
                mime_type = "image/webp"

            # 2. Call Gemini with ultra-fast vision model
            model_to_use = "gemini-3.1-flash-lite"
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model_to_use}:generateContent?key={self.gemini_key}"
            )
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
                "generationConfig": {"temperature": 0.1},
            }
            resp = requests.post(url, json=payload, timeout=6)
            if resp.status_code == 200:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                self.last_model_used = f"Google {model_to_use} (Vision)"
                return text
        except Exception:
            pass
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
        truth_hierarchy: bool = True
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
            if canonical.fit.value != "Any":
                pos_signals.append(f"fit={canonical.fit.value}")
            if canonical.neck.value != "Any":
                pos_signals.append(f"neck={canonical.neck.value}")
            if canonical.fandom.value != "None":
                pos_signals.append(f"fandom={canonical.fandom.value}")
        if pos_signals:
            constraint_lines.append(f"POSITIVE REQUIREMENTS (must be present for a high match_score): {', '.join(pos_signals)}")

        if canonical and canonical.has_visual_intent:
            constraint_lines.append(
                "WARNING: A specific visual intent was provided. DO NOT reject products (score < 0.5) just because their text doesn't describe the exact visual details. "
                "If the product matches the broader category/fandom, score it >= 0.5 so it survives to be visually scanned."
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

        if raw_json:
            data = self._extract_json(raw_json)
            if data:
                try:
                    eval_map = {e["product_id"]: e for e in data.get("evaluations", [])}

                    # ---------------------------------------------------------
                    # VQA Scanning Phase (if visual intent is provided)
                    # ---------------------------------------------------------
                    if enable_vqa_scanner and canonical and canonical.has_visual_intent:
                        print(f"[Brain] Executing Exhaustive VQA Scanning for: {canonical.specific_visual_intent}")
                        vqa_prompt = (
                            f"The user has a highly specific visual requirement for this clothing item: '{canonical.specific_visual_intent}'.\n"
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
                        
                        if not vqa_strict_filter:
                            # Sort by text score to scan the most likely candidates first
                            vqa_candidates.sort(key=lambda x: float(eval_map.get(x.id, {}).get("match_score", 0.0)), reverse=True)
                        
                        # Cap at 6 to keep response latency ultra-fast
                        vqa_candidates = vqa_candidates[:6]
                        
                        import concurrent.futures
                        def run_single_vqa(p):
                            img_url = p.specs.get("image_url") or p.specs.get("display_image")
                            if not img_url:
                                return
                            vqa_raw = self._call_gemini_vision(vqa_prompt, img_url)
                            if not vqa_raw:
                                return
                            vqa_data = self._extract_json(vqa_raw)
                            if vqa_data and p.id in eval_map:
                                ev_data = eval_map[p.id]
                                is_vis = bool(vqa_data.get("is_visual_match", False))
                                ev_data["is_relevant"] = is_vis
                                text_score = float(ev_data.get("match_score", 0.5))
                                vis_score = float(vqa_data.get("visual_score", 0.0))
                                ev_data["match_score"] = (text_score * 0.3) + (vis_score * 0.7)
                                vqa_reason = vqa_data.get("reason", "")
                                ev_data["reason"] = f"[VQA: {is_vis}] {vqa_reason}"

                        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                            list(executor.map(run_single_vqa, vqa_candidates))
                    
                    for p in candidates:
                        ev_data = eval_map.get(p.id)
                        if ev_data:
                            ev = ProductRelevanceEvaluation(
                                product_id=p.id,
                                product_title=p.title,
                                is_relevant=bool(ev_data.get("is_relevant", True)),
                                match_score=float(ev_data.get("match_score", 0.7)),
                                reason=str(ev_data.get("reason", "Passed LLM evaluation")),
                            )
                            evaluations.append(ev)
                            if ev.is_relevant and ev.match_score >= 0.5:
                                accepted.append(p)
                        else:
                            # Product not evaluated by LLM — assign neutral score, keep it
                            evaluations.append(ProductRelevanceEvaluation(
                                product_id=p.id,
                                product_title=p.title,
                                is_relevant=True,
                                match_score=0.6,
                                reason="Not evaluated — kept as neutral candidate",
                            ))
                            accepted.append(p)
                    
                    # Sort accepted by match score
                    accepted.sort(key=lambda x: next((e.match_score for e in evaluations if e.product_id == x.id), 0), reverse=True)
                    return accepted, evaluations
                except Exception as e:
                    print(f"[Brain/Eval] Error: {e}")

        # Fallback — accept all with default score
        for p in candidates:
            evaluations.append(ProductRelevanceEvaluation(
                product_id=p.id,
                product_title=p.title,
                is_relevant=True,
                match_score=0.6,
                reason="LLM unavailable — passed attribute pre-filters",
            ))
        return candidates, evaluations

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

