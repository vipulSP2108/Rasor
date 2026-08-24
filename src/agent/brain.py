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


def preprocess_prompt(prompt: str) -> str:
    """Step 0: Normalize case, fix spelling, expand synonyms before LLM or rules."""
    text = prompt.strip().lower()
    
    # Apply spell corrections (exact phrase matching)
    for typo, fix in _SPELL_CORRECTIONS.items():
        text = re.sub(rf"\b{re.escape(typo)}\b", fix, text)
    
    # Apply synonym expansion (exact phrase matching)
    for synonym, canonical in _SYNONYM_MAP.items():
        text = re.sub(rf"\b{re.escape(synonym)}\b", canonical, text)
    
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
            '  "cleaned_keywords": string (core product keywords, stripped of noise),\n'
            '  "gender": "men" | "women" | "unisex" | "all",\n'
            '  "category": "t-shirt" | "hoodie" | "joggers" | "jeans" | "shirt" | "sliders" | "footwear" | "vest" | "electronics" | "general",\n'
            '  "color": "Black" | "Blue" | "White" | "Red" | "Green" | "Orange" | "Grey" | "Yellow" | "Maroon" | "Beige" | "Brown" | "Navy" | "Any",\n'
            '  "design": "Solid" | "Graphic Print" | "Typography" | "All Over Print" | "Washed" | "Checked" | "Any",\n'
            '  "fit": "Oversized Fit" | "Regular Fit" | "Boyfriend Fit" | "Baggy Fit" | "Super Baggy Fit" | "Slim Fit" | "Any",\n'
            '  "sleeve": "Half Sleeve" | "Full Sleeve" | "Sleeveless" | "Any",\n'
            '  "fabric": "Cotton" | "Polyester" | "Blend" | "Fleece" | "Linen" | "Nylon" | "Any",\n'
            '  "neck": "Round Neck" | "V-Neck" | "Polo" | "Collar" | "Hood" | "Crew Neck" | "Any",\n'
            '  "fandom": "Marvel" | "DC" | "Disney" | "Harry Potter" | "Anime / Cartoons" | "None",\n'
            '  "size": string or null (e.g. "L", "M", "XL", "2XL", "UK 9" for footwear),\n'
            '  "max_price": float or null,\n'
            '  "min_rating": float or null\n'
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
                    data["fabric"] = data.get("fabric", "Any") if data.get("fabric") in [e.value for e in FabricEnum] else "Any"
                    data["neck"] = data.get("neck", "Any") if data.get("neck") in [e.value for e in NeckEnum] else "Any"
                    data["fandom"] = data.get("fandom", "None") if data.get("fandom") in [e.value for e in FandomEnum] else "None"
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
            fandom=safe_enum(FandomEnum, parsed_raw.fandom, FandomEnum.NONE),
            size=parsed_raw.size,
            max_price=parsed_raw.max_price,
            min_rating=parsed_raw.min_rating,
        )
        return canonical, "⚡ Normalized by Rule Engine"

    # ── Stage 3: Candidate Relevance Evaluation ───────────────────────────────

    def evaluate_candidates(
        self,
        user_prompt: str,
        candidates: List[Product],
    ) -> Tuple[List[Product], List[ProductRelevanceEvaluation]]:
        """LLM QA: Verifies retrieved products against user intent. Rejects false positives."""
        if not candidates:
            return [], []

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
            }
            for p in candidates
        ]

        system = (
            "You are an e-commerce QA agent. The user requested a specific product. "
            "For each candidate, decide if it matches the user's intent.\n"
            "Reject a product if:\n"
            "  - User asked for 'solid/plain' but product has 'Graphic Print' or 'Typography' design.\n"
            "  - User asked for a specific category (e.g. t-shirt) but product is a different subclass.\n"
            "  - User asked for a specific character (e.g. Iron Man) but product shows a different character.\n"
            "Output ONLY this JSON:\n"
            "{\n"
            '  "evaluations": [\n'
            '    {"product_id": "...", "product_title": "...", "is_relevant": true, "match_score": 0.95, "reason": "..."}\n'
            "  ]\n"
            "}"
        )
        msg = f"User Intent: \"{user_prompt}\"\nCandidates:\n{json.dumps(cand_summary, indent=2)}"

        raw_json = self._call_llm(msg, system)
        evaluations: List[ProductRelevanceEvaluation] = []
        accepted: List[Product] = []

        if raw_json:
            data = self._extract_json(raw_json)
            if data:
                try:
                    eval_map = {e["product_id"]: e for e in data.get("evaluations", [])}
                    for p in candidates:
                        ev_data = eval_map.get(p.id)
                        if ev_data:
                            ev = ProductRelevanceEvaluation(
                                product_id=p.id,
                                product_title=p.title,
                                is_relevant=bool(ev_data.get("is_relevant", True)),
                                match_score=float(ev_data.get("match_score", 0.8)),
                                reason=str(ev_data.get("reason", "Passed LLM evaluation")),
                            )
                            evaluations.append(ev)
                            if ev.is_relevant and ev.match_score >= 0.5:
                                accepted.append(p)
                        else:
                            accepted.append(p)
                    return accepted, evaluations
                except Exception as e:
                    print(f"[Brain/Eval] Error: {e}")

        # Fallback — accept all with default score
        for p in candidates:
            evaluations.append(ProductRelevanceEvaluation(
                product_id=p.id,
                product_title=p.title,
                is_relevant=True,
                match_score=0.9,
                reason="Passed attribute and keyword pre-filters",
            ))
        return candidates, evaluations
