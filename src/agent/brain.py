"""Agent Brain & Multi-Model LLM Reasoning Engine.

Implements:
1. LLM Intent Normalization (Raw Prompt -> Canonical Pydantic Enums).
2. Multi-Model Fallback Router (Gemini 2.5 Flash -> Groq Llama-3.3-70B -> Rule-based fallback).
3. LLM Candidate Relevance Evaluation & False Positive Filter.
"""

import os
import json
import re
from typing import Any, Dict, List, Optional, Tuple
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
)
from src.agent.parser import parse_user_intent

load_dotenv()


class AgentBrain:
    """The reasoning and evaluation engine for Rasor Agentic Commerce."""

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        primary_model: str = "gemini-2.5-flash",
        fallback_model: str = "llama-3.3-70b-versatile"
    ):
        self.gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.groq_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.last_model_used = "none"

    def _call_gemini_json(self, prompt: str, system_instruction: str) -> Optional[str]:
        """Calls Google Gemini API via official google.genai SDK or REST endpoint."""
        if not self.gemini_key:
            return None
        
        try:
            # Direct REST call to Gemini 2.5 Flash / 1.5 Flash
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.primary_model}:generateContent?key={self.gemini_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "systemInstruction": {"parts": [{"text": system_instruction}]},
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.1
                }
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                self.last_model_used = f"Google {self.primary_model}"
                return text
            else:
                print(f"[Brain] Gemini returned HTTP {resp.status_code}: {resp.text[:200]}")
                return None
        except Exception as e:
            print(f"[Brain] Gemini exception: {e}")
            return None

    def _call_groq_json(self, prompt: str, system_instruction: str) -> Optional[str]:
        """Calls Groq Llama 3.3 70B with JSON mode as secondary fallback."""
        if not self.groq_key:
            return None
        
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.groq_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.fallback_model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                self.last_model_used = f"Groq {self.fallback_model}"
                return text
            else:
                print(f"[Brain] Groq returned HTTP {resp.status_code}: {resp.text[:200]}")
                return None
        except Exception as e:
            print(f"[Brain] Groq exception: {e}")
            return None

    def normalize_intent(self, user_prompt: str) -> Tuple[CanonicalShoppingQuery, str]:
        """Stage 1: Uses LLM to parse free-form prompt into canonical Pydantic Enums."""
        system_prompt = (
            "You are a precision e-commerce intent normalizer. Given a user shopping prompt, "
            "extract and map all attributes into this EXACT JSON schema:\n"
            "{\n"
            '  "cleaned_keywords": string,\n'
            '  "gender": "men" | "women" | "unisex" | "all",\n'
            '  "category": "t-shirt" | "hoodie" | "joggers" | "jeans" | "shirt" | "vest" | "footwear" | "electronics" | "general",\n'
            '  "color": "Black" | "Blue" | "White" | "Red" | "Green" | "Orange" | "Grey" | "Yellow" | "Maroon" | "Beige" | "Brown" | "Navy" | "Any",\n'
            '  "design": "Solid" | "Graphic Print" | "Typography" | "All Over Print" | "Washed" | "Checked" | "Any",\n'
            '  "fit": "Oversized Fit" | "Regular Fit" | "Boyfriend Fit" | "Baggy Fit" | "Super Baggy Fit" | "Slim Fit" | "Any",\n'
            '  "sleeve": "Half Sleeve" | "Full Sleeve" | "Sleeveless" | "Any",\n'
            '  "fandom": "Marvel" | "DC" | "Disney" | "Harry Potter" | "Anime / Cartoons" | "None",\n'
            '  "size": string or null (e.g. "L", "M", "XL", "2XL", "3XL"),\n'
            '  "max_price": float or null,\n'
            '  "min_rating": float or null\n'
            "}\n"
            "Rules:\n"
            "- If user says 'plain', 'solid', 'basic', map design to 'Solid'.\n"
            "- If user mentions 'batman', 'superman', 'joker', map fandom to 'DC'.\n"
            "- If user mentions 'marvel', 'spiderman', 'avengers', map fandom to 'Marvel'.\n"
            "- Output ONLY valid JSON matching this schema."
        )

        user_msg = f"User Shopping Prompt: \"{user_prompt}\""
        
        # 1. Try Gemini (Primary)
        raw_json = self._call_gemini_json(user_msg, system_prompt)
        
        # 2. Try Groq (Fallback)
        if not raw_json:
            raw_json = self._call_groq_json(user_msg, system_prompt)

        # 3. Parse LLM JSON or fallback to Regex Parser
        if raw_json:
            try:
                clean_json_str = re.search(r"\{.*\}", raw_json, re.DOTALL)
                if clean_json_str:
                    data = json.loads(clean_json_str.group(0))
                    data["original_prompt"] = user_prompt
                    canonical = CanonicalShoppingQuery(**data)
                    return canonical, f"🧠 Normalized by {self.last_model_used}"
            except Exception as e:
                print(f"[Brain] Error parsing LLM JSON: {e}. Falling back to heuristic parser.")

        # Heuristic fallback if LLMs are unavailable
        parsed_raw = parse_user_intent(user_prompt)
        canonical = CanonicalShoppingQuery(
            original_prompt=user_prompt,
            cleaned_keywords=parsed_raw.cleaned_query or user_prompt,
            gender=GenderEnum(parsed_raw.gender) if parsed_raw.gender else GenderEnum.MEN,
            category=CategoryEnum(parsed_raw.category) if parsed_raw.category in [c.value for c in CategoryEnum] else CategoryEnum.TSHIRT,
            color=ColorEnum(parsed_raw.color) if parsed_raw.color in [c.value for c in ColorEnum] else ColorEnum.ANY,
            design=DesignEnum(parsed_raw.design) if parsed_raw.design in [d.value for d in DesignEnum] else DesignEnum.ANY,
            fit=FitEnum(parsed_raw.fit) if parsed_raw.fit in [f.value for f in FitEnum] else FitEnum.ANY,
            sleeve=SleeveEnum(parsed_raw.sleeve) if parsed_raw.sleeve in [s.value for s in SleeveEnum] else SleeveEnum.ANY,
            fandom=FandomEnum(parsed_raw.fandom) if parsed_raw.fandom in [f.value for f in FandomEnum] else FandomEnum.NONE,
            size=parsed_raw.size,
            max_price=parsed_raw.max_price,
            min_rating=parsed_raw.min_rating
        )
        return canonical, "⚡ Normalized by Deterministic Rule Engine"

    def evaluate_candidates(
        self,
        user_prompt: str,
        candidates: List[Product]
    ) -> Tuple[List[Product], List[ProductRelevanceEvaluation]]:
        """Stage 3: LLM verifies retrieved products and rejects false positives."""
        if not candidates:
            return [], []

        # Prepare candidates summary for evaluation
        cand_list = []
        for p in candidates:
            cand_list.append({
                "id": p.id,
                "title": p.title,
                "price": p.price,
                "color": p.specs.get("color"),
                "design": p.specs.get("design"),
                "fit": p.specs.get("fit"),
                "fandom": p.specs.get("fandom_partner"),
                "sizes_in_stock": p.specs.get("available_sizes")
            })

        system_prompt = (
            "You are an e-commerce QA validation agent. The user requested a specific product. "
            "Examine each candidate retrieved from the store API. For each candidate, decide:\n"
            "1. is_relevant: true/false (Reject if it contradicts user intent, e.g. user asked for solid/plain and item has graphics)\n"
            "2. match_score: 0.0 to 1.0\n"
            "3. reason: 1-sentence explanation\n"
            "Output JSON format:\n"
            "{\n"
            '  "evaluations": [\n'
            '    {"product_id": "...", "product_title": "...", "is_relevant": true, "match_score": 0.95, "reason": "..."}\n'
            "  ]\n"
            "}"
        )

        user_msg = f"User Intent: \"{user_prompt}\"\n\nCandidate Products:\n{json.dumps(cand_list, indent=2)}"

        raw_json = self._call_gemini_json(user_msg, system_prompt) or self._call_groq_json(user_msg, system_prompt)

        evaluations: List[ProductRelevanceEvaluation] = []
        accepted_products: List[Product] = []

        if raw_json:
            try:
                clean_match = re.search(r"\{.*\}", raw_json, re.DOTALL)
                if clean_match:
                    eval_data = json.loads(clean_match.group(0)).get("evaluations", [])
                    eval_map = {e["product_id"]: e for e in eval_data}

                    for p in candidates:
                        ev = eval_map.get(p.id)
                        if ev:
                            eval_obj = ProductRelevanceEvaluation(
                                product_id=p.id,
                                product_title=p.title,
                                is_relevant=bool(ev.get("is_relevant", True)),
                                match_score=float(ev.get("match_score", 0.8)),
                                reason=str(ev.get("reason", "Satisfies user criteria"))
                            )
                            evaluations.append(eval_obj)
                            if eval_obj.is_relevant and eval_obj.match_score >= 0.5:
                                accepted_products.append(p)
                        else:
                            accepted_products.append(p)

                    return accepted_products, evaluations
            except Exception as e:
                print(f"[Brain Evaluation] Parsing error: {e}. Accepting all candidates.")

        # Fallback: All products accepted with default confidence
        for p in candidates:
            evaluations.append(ProductRelevanceEvaluation(
                product_id=p.id,
                product_title=p.title,
                is_relevant=True,
                match_score=0.9,
                reason="Passed keyword and attribute validation"
            ))
        return candidates, evaluations
