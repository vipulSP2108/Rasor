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
    "deadpool": ["ryan reynolds", "marvel", "merc with a mouth"],
    "wolverine": ["x-men", "logan", "mutant", "marvel"],
    "venom": ["symbiote", "eddie brock", "marvel", "carnage"],
    # DC
    "batman": ["gotham", "dark knight", "bruce wayne", "joker", "dc"],
    "superman": ["clark kent", "krypton", "man of steel", "dc"],
    "wonder woman": ["diana prince", "amazon", "dc"],
    "flash": ["barry allen", "speedster", "central city", "dc"],
    # Anime
    "naruto": ["hidden leaf", "hokage", "sasuke", "kakashi", "anime", "shinobi"],
    "dragon ball": ["dbz", "goku", "vegeta", "saiyan", "anime"],
    "dbz": ["dragon ball", "goku", "vegeta", "saiyan", "anime"],
    "one piece": ["luffy", "straw hat", "zoro", "anime", "pirate"],
    "attack on titan": ["aot", "eren", "levi", "survey corps", "anime"],
    "jujutsu kaisen": ["jjk", "gojo", "itadori", "sukuna", "anime"],
    "demon slayer": ["tanjiro", "nezuko", "zenitsu", "anime"],
}

def preprocess_prompt(prompt: str) -> str:
    """Step 0: Normalize case, fix spelling, expand synonyms and knowledge graph before LLM or rules."""
    text = prompt.strip().lower()
    
    # Apply spell corrections (exact phrase matching)
    for typo, fix in _SPELL_CORRECTIONS.items():
        text = re.sub(rf"\b{re.escape(typo)}\b", fix, text)
    
    # Apply synonym expansion (exact phrase matching)
    for synonym, canonical in _SYNONYM_MAP.items():
        text = re.sub(rf"\b{re.escape(synonym)}\b", canonical, text)
        
    # Apply Fandom Knowledge Graph Expansion (append related terms for wider search net)
    expanded_terms = []
    for entity, related_keywords in _FANDOM_KNOWLEDGE_GRAPH.items():
        if re.search(rf"\b{re.escape(entity)}\b", text):
            expanded_terms.extend(related_keywords)
            
    # Append unique expanded terms to the end of the text
    if expanded_terms:
        # Deduplicate and append
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
        try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.primary_model}:generateContent?key={self.gemini_key}"
            )
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "systemInstruction": {"parts": [{"text": system}]},
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
            }
            resp = requests.post(url, json=payload, timeout=8)
            if resp.status_code == 200:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                self.last_model_used = f"Google {self.primary_model}"
                return text
            print(f"[Brain/Gemini] HTTP {resp.status_code}: {resp.text[:150]}")
        except Exception as e:
            print(f"[Brain/Gemini] Error: {e}")
        return None

    def _call_gemini_vision(self, prompt: str, image_url: str) -> Optional[str]:
        """Call Gemini Vision model to evaluate an image against a prompt."""
        if not self.gemini_key:
            return None
        try:
            # 1. Download image
            import base64
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
            }
            img_resp = requests.get(image_url, headers=headers, timeout=5)
            if img_resp.status_code != 200:
                print(f"[Brain/GeminiVision] Failed to download image {image_url} (HTTP {img_resp.status_code})")
                return None
            img_b64 = base64.b64encode(img_resp.content).decode("utf-8")
            
            # Determine mime type naively
            mime_type = "image/jpeg"
            if image_url.lower().endswith(".png"):
                mime_type = "image/png"
            elif image_url.lower().endswith(".webp"):
                mime_type = "image/webp"

            # 2. Call Gemini
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-1.5-flash:generateContent?key={self.gemini_key}"
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
            resp = requests.post(url, json=payload, timeout=12)
            if resp.status_code == 200:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                self.last_model_used = "Google gemini-1.5-flash (Vision)"
                return text
            print(f"[Brain/GeminiVision] HTTP {resp.status_code}: {resp.text[:150]}")
        except Exception as e:
            print(f"[Brain/GeminiVision] Error: {e}")
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

    def normalize_intent(self, user_prompt: str) -> Tuple[CanonicalShoppingQuery, str]:
        """Normalizes free-form prompt → canonical Pydantic enums.

        Steps:
          a) Spell-correct & synonym-expand the raw prompt.
          b) Call LLM for structured JSON extraction.
          c) Fall back to regex parser if LLM unavailable.
        """
        # Step a: Pre-process
        cleaned_prompt = preprocess_prompt(user_prompt)
        print(f"[Brain] Pre-processed: '{user_prompt}' → '{cleaned_prompt}'")

        system = (
            "You are a precision e-commerce intent extractor for an Indian fashion store (Bewakoof.com). "
            "Extract all shopping attributes from the user query into this exact JSON schema:\n"
            "{\n"
            '  "cleaned_keywords": string (core product keywords, stripped of noise and stripped of any highly specific visual descriptions),\n'
            '  "specific_visual_intent": string or null (ONLY use this if the user provides a very long/detailed description of a specific graphic, print, or image they want on the shirt. If they just say something like "L Black Panther t-shirts", leave this null. If populated, EXCLUDE these words from cleaned_keywords),\n'
            '  "gender": "men" | "women" | "unisex" | "all",\n'
            '  "category": "t-shirt" | "hoodie" | "joggers" | "jeans" | "shirt" | "sliders" | "footwear" | "vest" | "electronics" | "general",\n'
            '  "color": "Black" | "Blue" | "White" | "Red" | "Green" | "Orange" | "Grey" | "Yellow" | "Maroon" | "Beige" | "Brown" | "Navy" | "Any",\n'
            '  "design": "Solid" | "Graphic Print" | "Typography" | "All Over Print" | "Washed" | "Checked" | "Any",\n'
            '  "fit": "Oversized Fit" | "Regular Fit" | "Boyfriend Fit" | "Baggy Fit" | "Super Baggy Fit" | "Slim Fit" | "Any",\n'
            '  "sleeve": "Half Sleeve" | "Full Sleeve" | "Sleeveless" | "Any",\n'
            '  "fabric": "Cotton" | "Polyester" | "Blend" | "Fleece" | "Linen" | "Nylon" | "Any",\n'
            '  "neck": "Round Neck" | "V-Neck" | "Polo" | "Collar" | "Hood" | "Crew Neck" | "Any",\n'
            '  "occasion": "Party" | "Gym" | "Casual" | "Office" | "Any",\n'
            '  "fandom": string or "None",\n'
            '  "size": string or null (e.g. "L", "M", "XL", "2XL", "UK 9" for footwear),\n'
            '  "quantity": integer (default 1),\n'
            '  "max_price": float or null,\n'
            '  "min_rating": float or null,\n'
            '  "fast_shipping_requested": boolean (true if user wants fast/early delivery, else false),\n'
            '  "negative_keywords": [string] (list of explicit exclusions like "logo", "polo", "printed")\n'
            "}\n\n"
            "RULES:\n"
            "- 'plain', 'solid', 'basic', 'no print' → design: 'Solid'\n"
            "- 'printed', 'graphic', 'anime' → design: 'Graphic Print'\n"
            "- 'text', 'quote', 'slogan', 'typography' → design: 'Typography'\n"
            "- 'washed', 'acid wash', 'vintage' → design: 'Washed'\n"
            "- 'oversized', 'baggy', 'loose', 'relaxed' → fit: 'Oversized Fit'\n"
            "- 'cotton', 'polyester', 'blend' → fabric\n"
            "- 'round neck', 'v neck', 'polo' → neck\n"
            "- 'batman', 'joker', 'superman', 'dc' → fandom: 'DC'\n"
            "- 'spider man', 'iron man', 'marvel', 'deadpool', 'thor', 'avengers' → fandom: 'Marvel'\n"
            "- 'mickey', 'disney', 'minnie' → fandom: 'Disney'\n"
            "- 'slider', 'sandal', 'chappal', 'flip flop' → category: 'sliders'\n"
            "- 'full sleeve', 'long sleeve' → sleeve: 'Full Sleeve'\n"
            "- 'half sleeve', 'short sleeve' → sleeve: 'Half Sleeve'\n"
            "- 'club', 'party', 'clubbing', 'night out' → occasion: 'Party'\n"
            "- 'gym', 'workout', 'active', 'sports' → occasion: 'Gym'\n"
            "- 'casual', 'chill', 'street', 'everyday' → occasion: 'Casual'\n"
            "- 'office', 'work', 'formal', 'meeting' → occasion: 'Office'\n"
            "- 'fast', 'quick', 'urgent', 'express', 'rapid', 'early', 'soon' → fast_shipping_requested: true\n"
            "- IMPORTANT: If the user asks for 'batman with arms crossed and wearing a metal suit', cleaned_keywords = 'batman', specific_visual_intent = 'arms crossed and wearing a metal suit'.\n"
            "- Output ONLY valid JSON. No markdown, no extra text."
        )

        msg = f"User prompt (pre-processed): \"{cleaned_prompt}\"\nOriginal: \"{user_prompt}\""
        raw_json = self._call_llm(msg, system)

        if raw_json:
            data = self._extract_json(raw_json)
            if data:
                try:
                    data["original_prompt"] = user_prompt
                    # Validate enums — fall back to defaults on invalid value
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
                    canonical = CanonicalShoppingQuery(**data)
                    return canonical, f"🧠 Normalized by {self.last_model_used}"
                except Exception as e:
                    print(f"[Brain] Schema validation error: {e}")

        # Rule-based fallback
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
            fabric=FabricEnum.ANY, # fallback doesn't parse this yet
            neck=NeckEnum.ANY,
            occasion=OccasionEnum.ANY,
            fandom=safe_enum(FandomEnum, parsed_raw.fandom, FandomEnum.NONE),
            size=parsed_raw.size,
            quantity=parsed_raw.quantity or 1,
            max_price=parsed_raw.max_price,
            min_rating=parsed_raw.min_rating,
            fast_shipping_requested=parsed_raw.fast_shipping_requested
        )
        return canonical, "⚙️ Normalized by Fallback Rules"

    # ── Stage 3: Candidate Relevance Evaluation ───────────────────────────────

    def evaluate_candidates(
        self,
        user_prompt: str,
        candidates: List[Product],
        canonical: Optional["CanonicalShoppingQuery"] = None,
        vqa_strict_filter: bool = False,
        enable_vqa_scanner: bool = True
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

        if canonical and canonical.specific_visual_intent:
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
            "  - If the user asked for a specific character/theme (e.g. Batman), a shirt without any Batman reference scores <= 0.3.\n"
            "  - If the user's prompt mentions a specific design feature (e.g. 'logo', 'illustration', 'bold text'), "
            "score products that clearly match HIGHER and products that clearly DON'T match LOWER.\n"
            "  - If a product title/description contains a HARD NEGATION keyword listed below, it MUST score <= 0.15 and is_relevant=false.\n"
            "  - Broad queries (e.g. 'black t-shirt') should accept extras like oversized, graphic print — do NOT penalise them.\n\n"
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
                    if enable_vqa_scanner and canonical and canonical.specific_visual_intent:
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
                        
                        # Cap at 15 to avoid massive API delays
                        vqa_candidates = vqa_candidates[:15]
                        
                        for p in vqa_candidates:
                            img_url = p.specs.get("image_url") or p.specs.get("display_image")
                            if img_url:
                                vqa_raw = self._call_gemini_vision(vqa_prompt, img_url)
                                vqa_data = self._extract_json(vqa_raw)
                                if vqa_data:
                                    ev_data = eval_map[p.id]
                                    
                                    # VQA trumps text relevance
                                    is_vis = bool(vqa_data.get("is_visual_match", False))
                                    ev_data["is_relevant"] = is_vis
                                    
                                    # Blend scores, favoring vision heavily (70/30)
                                    text_score = float(ev_data.get("match_score", 0.5))
                                    vis_score = float(vqa_data.get("visual_score", 0.0))
                                    ev_data["match_score"] = (text_score * 0.3) + (vis_score * 0.7)
                                    
                                    vqa_reason = vqa_data.get("reason", "")
                                    ev_data["reason"] = f"[VQA: {is_vis}] {vqa_reason}"
                    
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

