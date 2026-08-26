"""Stylist Agent Node for Conversational UX.

Fully LLM-powered multi-turn conversational shopping assistant. 
Uses the same Gemini → Groq fallback chain as AgentBrain.

Architecture:
  - StylistAgent.process_turn() calls the LLM with the full conversation 
    history and a rich system prompt that enforces the UX design document.
  - The LLM always returns structured JSON: 
      {
        "intent": "greeting|clarify|search|autopilot",
        "message": "Natural language reply to user",
        "ready_for_search": true|false,
        "updated_query": "refined search terms to pass to CatalogAgent"
      }
  - ColorMatchingAgent is called as a pure rule engine when the LLM 
    classifies user input as a skin tone rating.
"""

import os
import json
import re
import requests
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Response Model
# ---------------------------------------------------------------------------

class StylistResponse(BaseModel):
    intent: str = Field(default="clarify", description="One of: greeting, clarify, search, autopilot")
    message: str = Field(..., description="Conversational reply to show the user.")
    ready_for_search: bool = Field(default=False, description="True when intent is refined enough to hit CatalogAgent.")
    updated_query: str = Field(default="", description="Synthesized search query from all conversation turns so far.")
    suggested_options: list[str] = Field(default_factory=list, description="List of short quick-reply options for the user to tap (e.g. ['Oversized', 'Slim Fit']).")


# ---------------------------------------------------------------------------
# Color Matching Agent (Pure Rule Engine)
# ---------------------------------------------------------------------------

class ColorMatchingAgent:
    """Translates 1-10 skin tone ratings to optimal color palettes per color theory."""

    # Based on color theory for South Asian + global skin tone distribution
    _COLOR_MAP = {
        (1, 3): {
            "label": "Fair / Cool",
            "best": ["Emerald Green", "Deep Burgundy", "Navy Blue", "Cobalt Blue", "Jewel Tones", "Royal Purple"],
            "avoid": ["Pale Yellow", "Stark White", "Beige", "Nude"],
        },
        (4, 7): {
            "label": "Medium / Warm",
            "best": ["Mustard Yellow", "Olive Green", "Terracotta", "Coral", "Rust", "Warm Brown"],
            "avoid": ["Neon colors", "Ice Blue", "Cool Pastels"],
        },
        (8, 10): {
            "label": "Deep / Rich",
            "best": ["Cobalt Blue", "Crisp White", "Bright Yellow", "Pastel Pink", "Electric Blue", "Ivory"],
            "avoid": ["Dark Brown", "Black-on-Black", "Very dark maroon"],
        },
    }

    @classmethod
    def get_recommendation(cls, rating: int) -> dict:
        for (low, high), data in cls._COLOR_MAP.items():
            if low <= rating <= high:
                return data
        return cls._COLOR_MAP[(4, 7)]  # default to Medium/Warm

    @classmethod
    def to_search_colors(cls, rating: int) -> str:
        rec = cls.get_recommendation(rating)
        return ", ".join(rec["best"][:3])  # Top 3 for search query injection


# ---------------------------------------------------------------------------
# Occasion Matching Agent (Pure Rule Engine)
# ---------------------------------------------------------------------------

class OccasionMatchingAgent:
    """Translates Occasion/Vibe to stylistic recommendations and coupled attributes."""

    _OCCASION_MAP = {
        "Party": {
            "suggestion": "How about a sharp Polo or a Slim-fit dark shirt to stand out?",
            "query_append": "polo OR slim fit shirt dark"
        },
        "Gym": {
            "suggestion": "For the gym, let's look at some breathable, dry-fit tees or tank tops.",
            "query_append": "dry-fit OR sports t-shirt OR sleeveless"
        },
        "Casual": {
            "suggestion": "For a relaxed vibe, an Oversized Graphic Tee or thick Cotton Hoodie works perfectly.",
            "query_append": "oversized graphic t-shirt OR hoodie"
        },
        "Office": {
            "suggestion": "For the office, a clean Solid Polo or a crisp Regular Fit Shirt is best.",
            "query_append": "solid polo OR regular fit shirt"
        }
    }

    @classmethod
    def get_recommendation(cls, occasion: str) -> dict:
        # Match case-insensitively
        for key, data in cls._OCCASION_MAP.items():
            if key.lower() in occasion.lower():
                return data
        return {}


# ---------------------------------------------------------------------------
# Stylist Agent
# ---------------------------------------------------------------------------

_STYLIST_SYSTEM_PROMPT = """You are Rasor's AI Personal Stylist — a friendly, knowledgeable fashion expert embedded in a conversational shopping assistant.

YOUR PERSONALITY:
- Natural and warm, like a real human stylist — not a search bar.
- ASK ONLY ONE QUESTION PER MESSAGE. NEVER ask multiple questions at once.
- Be concise. Your messages should be 1-3 sentences max.
- Use emojis sparingly — only when they genuinely add warmth.

YOUR MISSION:
Systematically gather the following taxonomy attributes from the user to narrow down the search space:
1. Category & Gender (Coupled: e.g. Men's T-shirt)
2. Occasion / Vibe (e.g. Party, Gym, Casual, Office)
3. Color (or Skin Tone 1-10)
4. Fit & Size (Coupled: e.g. Oversized L)
5. Design / Fandom (e.g. Graphic print, Marvel)

YOUR DECISION RULES (follow these strictly):

1. GREETING: If the user says hello, hi, or makes small talk with no shopping intent, respond warmly and introduce yourself. Set intent="greeting", ready_for_search=false.

2. CLARIFY (QUESTION COUPLING): To reduce fatigue, couple related questions together. Ask EXACTLY ONE coupled question per message.
   - If Gender OR Category is missing: Ask them together (e.g., "Are we shopping for men's or women's, and what specific clothing item?").
   - If Occasion is missing: Ask what the occasion or vibe is (e.g., "Is this for a party, the gym, or just casual wear?").
   - If Color is missing: Ask what color they want. IMPORTANT: If they don't know, proactively offer the skin tone feature (e.g., "If you're unsure, I can pick the perfect color for your skin tone! Just rate your skin tone from 1 (Fair) to 10 (Deep).")
   - If Fit OR Size is missing (and applicable): Ask them together (e.g., "What fit and size are you looking for?").
   - MULTI-ITEM OUTFITS: If the user requests a multi-item bundle (e.g., "a hoodie and joggers") but has not specified a maximum budget, you MUST ask for their total budget (e.g., "What is your total budget for this outfit?") before searching.
   Set intent="clarify", ready_for_search=false.

3. PROACTIVE SUGGESTIONS (Vibe/Occasion):
   - If the user specifies an occasion (e.g., Party, Gym, Casual), enthusiastically suggest a coupled style based on that vibe in your message (e.g., "For the gym, let's look at some breathable dry-fit tees!").

4. INTENT RESOLUTION (ANY vs AUTOPILOT): 
   - Local Bypass ("Any"): If the user explicitly says they don't care about a *single* attribute (e.g., "any color is fine"), accept it, do NOT trigger autopilot, and just move to the next missing attribute.
   - Global Bypass (Autopilot): If the user says "pick for me", "I don't care about the whole outfit", or "whatever", immediately trigger a search with a broad default query like "best rated men tshirt" and tell the user you'll pick the best options. Set intent="autopilot", ready_for_search=true.

5. SEARCH: When the user has provided enough context to reasonably narrow down the search space (typically Gender + Category + Color/Fit), it is time to search.
   Synthesize everything discussed so far into a concise search query (e.g., "men oversized black graphic tshirt under 800").
   Set intent="search", ready_for_search=true, updated_query="<synthesized query>".

6. SKIN TONE: If the user mentions their skin tone as a number (1-10) at any point, acknowledge it warmly. If you still need other attributes, ask ONE coupled question about them. If you have enough info, trigger a search.

IMPORTANT: Always return valid JSON only. No markdown, no extra text.

JSON SCHEMA:
{
  "intent": "greeting|clarify|search|autopilot",
  "message": "Your natural language reply to the user (ONLY ONE QUESTION MAX)",
  "ready_for_search": true or false,
  "updated_query": "concise search query string if ready_for_search is true, else empty string",
  "suggested_options": ["Option 1", "Option 2"] // Provide 2-4 short options for the user to tap if you asked a clarifying question (e.g. ["Oversized", "Slim Fit"]). Max 3 words per option. Leave empty [] if no options make sense.
}
"""


class StylistAgent:
    """LLM-powered conversational stylist that manages multi-turn shopping dialogue."""

    def __init__(self, primary_model: str = "gemini-3.1-flash-lite", fallback_model: str = "openai/gpt-oss-20b"):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.color_agent = ColorMatchingAgent()

    # ── LLM Callers ──────────────────────────────────────────────────────────

    def _call_gemini(self, conversation_prompt: str) -> Optional[str]:
        if not self.gemini_key:
            return None
        try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.primary_model}:generateContent?key={self.gemini_key}"
            )
            payload = {
                "contents": [{"parts": [{"text": conversation_prompt}]}],
                "systemInstruction": {"parts": [{"text": _STYLIST_SYSTEM_PROMPT}]},
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.6,  # Slightly more creative for natural conversation
                },
            }
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            print(f"[Stylist/Gemini] HTTP {resp.status_code}: {resp.text[:150]}")
        except Exception as e:
            print(f"[Stylist/Gemini] Error: {e}")
        return None

    def _call_groq(self, conversation_prompt: str) -> Optional[str]:
        if not self.groq_key:
            return None
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"},
                json={
                    "model": self.fallback_model,
                    "messages": [
                        {"role": "system", "content": _STYLIST_SYSTEM_PROMPT},
                        {"role": "user", "content": conversation_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.6,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            print(f"[Stylist/Groq] HTTP {resp.status_code}: {resp.text[:150]}")
        except Exception as e:
            print(f"[Stylist/Groq] Error: {e}")
        return None

    def _extract_json(self, raw: Optional[str]) -> Optional[dict]:
        if not raw:
            return None
        try:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                return json.loads(m.group(0))
        except Exception as e:
            print(f"[Stylist] JSON parse error: {e} | Raw: {raw[:100]}")
        return None

    def _build_prompt(self, user_input: str, history: list) -> str:
        """Build the conversation prompt from history + new user message."""
        lines = []
        for msg in history:
            role = "User" if msg["role"] == "user" else "Stylist"
            lines.append(f"{role}: {msg['content']}")
        lines.append(f"User: {user_input}")
        lines.append("Stylist (respond in JSON):")
        return "\n".join(lines)

    # ── Rule-Based Fallback ───────────────────────────────────────────────────

    def _rule_fallback(self, user_input: str, conversation_history: list) -> StylistResponse:
        """
        Smart rule-based fallback when LLM is unavailable (network blocked, rate limited, etc.).
        This handles the same 5 intents the LLM would handle, but with regex instead.
        """
        u = user_input.lower().strip()
        
        # 1. Greeting — handle typos like 'he hi', 'helo', or any short non-shopping phrase
        _greeting_words = re.search(r"\b(hi|hello|hey|heya|sup|namaste|greetings|howdy)\b", u)
        _has_any_product_signal = re.search(
            r"\b(shirt|tee|hoodie|pant|jean|trouser|jacket|buy|want|need|looking|show|black|white|blue|navy|dark|light|oversized|slim|men|women|polo|graphic)\b", u
        )
        _is_short = len(u.split()) <= 3
        if _greeting_words or (_is_short and not _has_any_product_signal):
            return StylistResponse(
                intent="greeting",
                message="Hey there! 👋 I'm Rasor's AI stylist. Tell me what you're looking to shop for today and I'll help you find the best picks!",
                ready_for_search=False,
                updated_query=""
            )
        
        # 2. Autopilot
        if re.search(r"\b(pick for me|just pick|i don.?t (care|mind)|you choose|whatever|surprise me|just show)\b", u):
            return StylistResponse(
                intent="autopilot",
                message="Perfect — Autopilot mode activated! 🚀 I'll find the highest-rated men's t-shirts and sort them by quality for you.",
                ready_for_search=True,
                updated_query="best rated men t-shirt"
            )
        
        # 3. Build context from history for query synthesis
        all_user_text = " ".join(
            [msg["content"] for msg in conversation_history if msg["role"] == "user"]
        ) + " " + user_input
        
        # Detect key signals in the accumulated context
        has_category = bool(re.search(r"\b(t-?shirt|tee|tees|hoodie|jogger|jeans|shirt|shirts|polo|trouser|shorts|sweatshirt)\b", all_user_text))
        has_color = bool(re.search(r"\b(black|white|blue|red|green|yellow|grey|gray|navy|maroon|olive|pink|orange|dark|light)\b", all_user_text))
        has_fit = bool(re.search(r"\b(oversized|regular|slim|polo|round neck|v.?neck|boyfriend|baggy|loose)\b", all_user_text))
        has_gender = bool(re.search(r"\b(men|women|male|female|unisex|man|woman|guys)\b", all_user_text))
        
        # 4. Specific enough to search
        if has_category and (has_color or has_fit):
            return StylistResponse(
                intent="search",
                message="Great, I have enough to work with! Let me search the catalog for you now... 🔍",
                ready_for_search=True,
                updated_query=all_user_text.strip()
            )
        
        # 5. Vague — ask ONE smart follow-up (Coupled Questions)
        if not has_category or not has_gender:
            return StylistResponse(
                intent="clarify",
                message="Nice! To narrow it down — are we shopping for men's or women's clothing, and what specific item are you looking for? (e.g. T-shirt, Hoodie)",
                ready_for_search=False,
                updated_query=""
            )
        if not has_color:
            return StylistResponse(
                intent="clarify",
                message="I found loads of options! What color are you looking for? (Or rate your skin tone 1-10 and I'll pick a matching palette!)",
                ready_for_search=False,
                updated_query=""
            )
        if not has_fit:
            return StylistResponse(
                intent="clarify",
                message="Are you going for a classic regular fit, or more of a relaxed oversized look?",
                ready_for_search=False,
                updated_query=""
            )
        
        # Completely unknown intent
        return StylistResponse(
            intent="clarify",
            message="I'd love to help! Are we shopping for men's or women's clothing, and what specific item are you looking for today? (e.g., t-shirt, hoodie)",
            ready_for_search=False,
            updated_query=""
        )

    # ── Main Entry Point ─────────────────────────────────────────────────────

    def process_turn(self, user_input: str, conversation_history: list) -> StylistResponse:
        """
        Process the user's input using the full conversation history.
        Returns a structured StylistResponse with the AI's reply and search intent.
        """
        # Check for skin tone rating first — inject colors into query before LLM
        skin_tone_match = re.search(r"\b(?:skin\s*tone[^0-9]*|i['\']?m\s*(?:a\s*)?|around\s*a?\s*)(\d+)\b", user_input.lower())
        skin_tone_rating = None
        if skin_tone_match:
            rating = int(skin_tone_match.group(1))
            if 1 <= rating <= 10:
                skin_tone_rating = rating

        # Build the prompt from full conversation context
        prompt = self._build_prompt(user_input, conversation_history)

        # Call LLM (Gemini → Groq fallback)
        raw = self._call_gemini(prompt) or self._call_groq(prompt)
        parsed = self._extract_json(raw)

        if not parsed:
            # Smart rule-based fallback when LLM is unavailable
            return self._rule_fallback(user_input, conversation_history)

        # If skin tone was detected, append color theory to the search query
        if skin_tone_rating and parsed.get("ready_for_search"):
            rec = self.color_agent.get_recommendation(skin_tone_rating)
            best_colors = self.color_agent.to_search_colors(skin_tone_rating)
            parsed["message"] = (
                f"With your skin tone ({rec['label']}), you'll look amazing in {rec['best'][0]}, "
                f"{rec['best'][1]}, or {rec['best'][2]}! Let me find the best options in those colors for you. 🎨"
            )
            existing_query = parsed.get("updated_query", "")
            parsed["updated_query"] = f"{existing_query} {best_colors}".strip()
            parsed["ready_for_search"] = True

        return StylistResponse(
            intent=parsed.get("intent", "clarify"),
            message=parsed.get("message", "Could you tell me more about what you're looking for?"),
            ready_for_search=parsed.get("ready_for_search", False),
            updated_query=parsed.get("updated_query", ""),
            suggested_options=parsed.get("suggested_options", [])
        )
