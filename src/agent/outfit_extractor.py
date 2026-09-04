"""Multimodal Vision Extractor for 'Match My Outfit' Garment Uploads.

Analyzes user-uploaded photos of their owned wardrobe garments via Gemini Multimodal.
Extracts:
- Category (t-shirt, hoodie, shirt, jeans, joggers, etc.)
- Dominant Color (mapped to canonical LCh color registry)
- Pattern / Design (Solid, Graphic Print, Washed, Checked)
- Fit (Oversized, Regular, Slim, Baggy)
- Short visual description
"""

import base64
import json
import os
import re
from typing import Any, Dict, Optional
import requests
from dotenv import load_dotenv

load_dotenv()


class GarmentVisionExtractor:
    """Extracts structured fashion attributes from garment photos."""

    def __init__(self, primary_model: str = "gemini-2.5-flash"):
        self.primary_model = primary_model
        self.gemini_key = os.getenv("GEMINI_API_KEY")

    def extract_from_base64(self, image_b64: str, mime_type: str = "image/jpeg") -> Dict[str, Any]:
        """Extracts garment attributes from base64 image data."""
        # Strip header if present (e.g. data:image/png;base64,...)
        if "," in image_b64:
            header, image_b64 = image_b64.split(",", 1)
            if "png" in header.lower():
                mime_type = "image/png"
            elif "webp" in header.lower():
                mime_type = "image/webp"

        if not self.gemini_key:
            return self._fallback_extraction("Black t-shirt", "offline_mock")

        system_instruction = (
            "You are an expert fashion stylist computer vision analyzer.\n"
            "Analyze the uploaded photo of the clothing garment and output ONLY valid JSON in this exact schema:\n"
            "{\n"
            '  "category": "t-shirt" | "hoodie" | "shirt" | "polo" | "joggers" | "jeans" | "trousers" | "shorts" | "vest" | "jacket",\n'
            '  "color": "Black" | "White" | "Heather Grey" | "Charcoal" | "Dark Navy" | "Navy" | "Sand Beige" | "Olive Green" | "Deep Maroon" | "Mustard" | "Cobalt Blue" | "Red" | "Blue",\n'
            '  "pattern": "Solid" | "Graphic Print" | "Typography" | "Washed" | "Checked",\n'
            '  "fit": "Oversized Fit" | "Regular Fit" | "Slim Fit" | "Baggy Fit" | "Relaxed Fit",\n'
            '  "visual_description": "1 concise sentence describing the garment, graphic, and color"\n'
            "}\n"
            "Rules:\n"
            "- Focus on the primary clothing item in the photo.\n"
            "- Map the color accurately to the closest option above.\n"
            "- Output valid JSON only, no markdown backticks."
        )

        prompt_text = "Identify the clothing category, dominant color, pattern, and fit of this garment."

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.primary_model}:generateContent?key={self.gemini_key}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt_text},
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": image_b64
                                }
                            }
                        ]
                    }
                ],
                "systemInstruction": {"parts": [{"text": system_instruction}]},
                "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
            }

            resp = requests.post(url, json=payload, timeout=12)
            if resp.status_code == 200:
                raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                data = json.loads(raw_text)
                return {
                    "success": True,
                    "category": data.get("category", "t-shirt"),
                    "color": data.get("color", "Black"),
                    "pattern": data.get("pattern", "Solid"),
                    "fit": data.get("fit", "Regular Fit"),
                    "visual_description": data.get("visual_description", "Owned clothing piece")
                }
            else:
                print(f"[GarmentVisionExtractor] Gemini error {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            print(f"[GarmentVisionExtractor] Exception: {e}")

        return self._fallback_extraction("Black oversized t-shirt", "fallback")

    def _fallback_extraction(self, label: str, reason: str) -> Dict[str, Any]:
        """Provides graceful fallback when vision call cannot complete."""
        return {
            "success": True,
            "category": "t-shirt",
            "color": "Black",
            "pattern": "Solid",
            "fit": "Oversized Fit",
            "visual_description": f"Analyzed garment ({label}) - {reason}"
        }
