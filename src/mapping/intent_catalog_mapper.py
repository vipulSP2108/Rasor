"""
Decoupled Query Intent to Catalog Schema & Semantic Mapping Orchestrator.

Provides:
  1. map_intent_to_catalog(): Primary public API transforming CatalogMappingInput -> ResolvedCatalogIntent
  2. preprocess_prompt(): Pre-clean typos, spellings, vibes, and fandom lore
  3. get_product_color(): Color extraction from titles and specs
  4. get_semantic_affinity_tier(): 5-tier semantic relevance ranker
  5. resolve_handle(): Bewakoof collection handle resolver
  6. parse_requested_sizes(): Compound size string parser
  7. NativeLLMHook: Built-in connection to project's existing Gemini & Grok/Groq models in .env
"""

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from src.mapping.contracts import (
    CatalogMappingInput,
    ResolvedCatalogIntent,
    StorePlatformEnum,
)
from src.mapping.taxonomy import (
    CHARACTER_ENTITY_MAP,
    COLOR_TAXONOMY,
    CATEGORY_TAXONOMY,
    ENTITY_FRANCHISE_MAP,
    FANDOM_KNOWLEDGE_GRAPH,
    MACRO_CATEGORY_EXPANSIONS,
    NOISE_WORDS,
    SPELL_CORRECTIONS,
    SYNONYM_MAP,
    VIBE_MAP,
)
from src.mapping.compilers import (
    BewakoofCompiler,
    ShopifyCompiler,
    UniversalCompiler,
    SearchTierCompiler,
)


# ------------------------------------------------------------------------------
# 1. Parsing & Utility Functions
# ------------------------------------------------------------------------------

def parse_requested_sizes(size_str: Optional[str]) -> List[str]:
    """
    Parses size specifications like 'L/XL', 'M, L', 'XL / XXL', 'L or XL', '2XL', '32'
    into a list of normalized uppercase size tokens: ['L', 'XL'].
    """
    if not size_str:
        return []
    cleaned = str(size_str).strip()
    if cleaned.lower() in ("any", "none", "all", ""):
        return []
    cleaned = cleaned.upper().replace("XXXL", "3XL").replace("XXL", "2XL")
    parts = re.split(r"[/,|]|\bOR\b", cleaned)
    result = []
    for p in parts:
        s = p.strip()
        if s:
            result.append(s)
    return result


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
    """
    Step 0: Normalize case, fix spelling typos, expand vibes and fandom lore.
    Runs deterministically in < 1ms before any downstream processing.
    """
    text = (prompt or "").strip().lower()

    # Normalize '3k', '2.5k', 'under 3k' to numeric values
    text = re.sub(r'\b(\d+(?:\.\d+)?)\s*k\b', lambda m: str(int(float(m.group(1)) * 1000)), text)

    # Apply vibe mapping
    for vibe, expansion in VIBE_MAP.items():
        if re.search(rf"\b{re.escape(vibe)}\b", text):
            text = text + " " + expansion

    # Apply spell corrections
    for typo, fix in SPELL_CORRECTIONS.items():
        text = re.sub(rf"\b{re.escape(typo)}\b", fix, text)

    # Apply synonym expansion
    for synonym, canonical in SYNONYM_MAP.items():
        text = re.sub(rf"\b{re.escape(synonym)}\b", canonical, text)

    # Apply Fandom Knowledge Graph Expansion
    if enable_semantic:
        expanded_terms = []
        for entity, related_keywords in FANDOM_KNOWLEDGE_GRAPH.items():
            if re.search(rf"\b{re.escape(entity)}\b", text):
                expanded_terms.extend(related_keywords)

        if expanded_terms:
            unique_terms = list(dict.fromkeys(expanded_terms))
            text = text + " " + " ".join(unique_terms)

    return text


def get_semantic_affinity_tier(
    product: Any,
    target_char_key: Optional[str] = None,
    target_char_terms: Optional[List[str]] = None,
    query_text: str = ""
) -> int:
    """
    Returns an integer semantic affinity tier (4 down to 0) representing closeness to user intent:
      Tier 4 (Exact Target Entity/Character): Direct match for target subject (e.g. 'black panther').
      Tier 3 (Core Lore / Associated Sub-Entities): Direct lore, iconic aliases, or related key entities
             (e.g. for Black Panther: 'wakanda', 't'challa', 'the king', 'panther').
      Tier 2 (Parent Universe / Franchise): Parent universe without the character (e.g. 'marvel', 'dc', 'anime').
      Tier 1 (Neutral Category / Color): Matches generic attributes without conflicting characters.
      Tier 0 (Conflicting Character): Features a different/opposing character.
    """
    p_title = getattr(product, "title", "") or ""
    p_specs = getattr(product, "specs", {}) or {}
    p_fandom = str(p_specs.get("fandom_partner", "")).lower()
    p_design = str(p_specs.get("design", "")).lower()
    p_subclass = str(p_specs.get("subclass", "")).lower()
    p_text = f"{p_title} {p_fandom} {p_design} {p_subclass}".lower()

    if target_char_key:
        # 1. Conflicting Character Check
        for other_key, other_terms in CHARACTER_ENTITY_MAP.items():
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
        lore_terms = target_char_terms or CHARACTER_ENTITY_MAP.get(target_char_key, [])
        if any(re.search(rf"\b{re.escape(lt)}\b", p_text) for lt in lore_terms if lt not in exact_terms):
            return 3  # Tier 3: Core Lore / Direct Sub-Entity

        # 4. Parent Universe / Franchise
        parent_universe = ENTITY_FRANCHISE_MAP.get(target_char_key)
        if parent_universe and (
            parent_universe in p_text or
            parent_universe in p_fandom
        ):
            return 2  # Tier 2: Parent Universe

    # Default neutral match
    return 1


def resolve_handle(
    gender: str,
    category: Optional[str],
    sleeve: Optional[str],
    fandom: Optional[str],
    design: Optional[str],
    fit: Optional[str],
) -> Tuple[str, bool]:
    """
    Backwards-compatible wrapper returning (handle, needs_subclass_filter).
    Delegates to BewakoofCompiler.
    """
    spec = BewakoofCompiler.compile(
        gender=gender,
        category=category,
        sleeve=sleeve,
        fandom=fandom,
        design=design,
        fit=fit,
    )
    return spec.handle, spec.needs_subclass_filter


# ------------------------------------------------------------------------------
# 2. Semantic Attribute Normalizers
# ------------------------------------------------------------------------------

def normalize_color(color_str: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Returns (canonical_name, color_family, hex_anchor).
    E.g. 'navy blue' -> ('Navy', 'Blue', '#001F3F').
    """
    if not color_str or color_str.lower() in ("any", "none", "all", "multi", ""):
        return None, None, None

    cl = color_str.lower().strip()

    # Exact key match in taxonomy
    if cl in COLOR_TAXONOMY:
        c = COLOR_TAXONOMY[cl]
        return c.canonical_name, c.family, c.hex_anchor

    # Check aliases with longest match first to avoid partial collision (e.g. 'blue' vs 'navy blue')
    all_alias_entries = []
    for _, profile in COLOR_TAXONOMY.items():
        for alias in profile.aliases:
            all_alias_entries.append((alias, profile))
    all_alias_entries.sort(key=lambda x: len(x[0]), reverse=True)

    for alias, profile in all_alias_entries:
        if re.search(rf"\b{re.escape(alias)}\b", cl):
            return profile.canonical_name, profile.family, profile.hex_anchor

    # Fallback to title-cased string
    return color_str.title(), color_str.title(), "#888888"


FIT_CANONICAL_MAP = {
    "oversized": "Oversized Fit",
    "oversized fit": "Oversized Fit",
    "baggy": "Oversized Fit",
    "baggy fit": "Oversized Fit",
    "loose": "Oversized Fit",
    "regular": "Regular Fit",
    "regular fit": "Regular Fit",
    "slim": "Slim Fit",
    "slim fit": "Slim Fit",
    "relaxed": "Oversized Fit",
    "relaxed fit": "Oversized Fit",
    "boyfriend": "Boyfriend Fit",
    "boyfriend fit": "Boyfriend Fit",
}


def normalize_category(category_str: Optional[str]) -> Tuple[str, str, List[str]]:
    """
    Returns (canonical_name, macro_category, synonyms_list).
    E.g. 'uppers' -> ('t-shirt', 'upper', ['t-shirt', 'shirt', 'hoodie', ...])
    """
    if not category_str or category_str.lower() in ("any", "all", "clothing", "items", ""):
        return "general", "general", ["clothing", "wear", "items"]

    cl = category_str.lower().replace("-", "").replace(" ", "")

    # Direct match in taxonomy
    for cat_key, c_def in CATEGORY_TAXONOMY.items():
        cleaned_key = cat_key.replace("-", "").replace(" ", "")
        if cl == cleaned_key or any(cl == syn.replace("-", "").replace(" ", "") for syn in c_def.synonyms):
            return c_def.canonical_name, c_def.macro, c_def.synonyms

    # Macro category check
    for macro_key, expansions in MACRO_CATEGORY_EXPANSIONS.items():
        if cl == macro_key.replace("-", "").replace(" ", ""):
            first_cat = expansions[0]
            macro_label = "upper" if "upper" in macro_key or "top" in macro_key else ("lower" if "lower" in macro_key or "bottom" in macro_key else macro_key)
            return first_cat, macro_label, expansions

    # Default fallback
    return category_str.lower(), "general", [category_str.lower()]


# ------------------------------------------------------------------------------
# 3. Main IntentCatalogMapper Orchestrator
# ------------------------------------------------------------------------------

class IntentCatalogMapper:
    """
    Decoupled orchestrator mapping user query intent to catalog search schemas.
    Independent of HTTP scrapers, UI components, and conversational agent state.
    """

    def __init__(self, enable_fandom_expansion: bool = True):
        self.enable_fandom_expansion = enable_fandom_expansion

    def map_intent(self, input_data: CatalogMappingInput) -> ResolvedCatalogIntent:
        """
        Transforms a CatalogMappingInput into a fully compiled ResolvedCatalogIntent.
        """
        notes: List[str] = []
        confidence: float = 1.0

        # Step 1: Pre-process query text
        cleaned_query = preprocess_prompt(input_data.query_text, enable_semantic=self.enable_fandom_expansion)
        if cleaned_query != input_data.query_text.strip().lower():
            notes.append(f"Pre-processed text: '{input_data.query_text}' -> '{cleaned_query}'")

        # Step 2: Extract or normalize category
        raw_cat = input_data.category
        if not raw_cat:
            # Infer from cleaned query
            for cat_key, c_def in CATEGORY_TAXONOMY.items():
                if any(re.search(rf"\b{re.escape(syn)}\b", cleaned_query) for syn in c_def.synonyms):
                    raw_cat = cat_key
                    notes.append(f"Inferred category '{cat_key}' from query keywords")
                    break

        canonical_cat, macro_cat, synonyms = normalize_category(raw_cat)

        # Step 3: Normalize gender
        g = (input_data.gender or "men").lower()
        if g not in ("men", "women", "unisex", "all"):
            g = "men"
            notes.append("Defaulted gender to 'men'")

        # Step 4: Normalize color & family
        raw_color = input_data.color
        if not raw_color:
            extracted_color = get_product_color(cleaned_query)
            if extracted_color:
                raw_color = extracted_color
                notes.append(f"Extracted color '{raw_color}' from query text")

        norm_color, color_fam, hex_anchor = normalize_color(raw_color)

        # Step 5: Parse sizes
        norm_sizes = parse_requested_sizes(input_data.size)
        if not norm_sizes and input_data.size:
            notes.append(f"Could not parse size string '{input_data.size}'")

        # Step 6: Normalize fit & design
        norm_fit = input_data.fit
        if norm_fit:
            norm_fit = FIT_CANONICAL_MAP.get(norm_fit.lower().strip(), norm_fit.title())
        else:
            if "oversized" in cleaned_query or "loose" in cleaned_query or "baggy" in cleaned_query:
                norm_fit = "Oversized Fit"
                notes.append("Inferred fit: 'Oversized Fit'")
            elif "slim" in cleaned_query:
                norm_fit = "Slim Fit"
                notes.append("Inferred fit: 'Slim Fit'")

        norm_design = input_data.design
        if norm_design:
            design_map = {
                "graphic": "Graphic Print", "graphic print": "Graphic Print", "printed": "Graphic Print",
                "solid": "Solid", "plain": "Solid", "basic": "Solid",
                "typography": "Typography", "quote": "Typography",
                "washed": "Washed", "acid wash": "Washed",
                "all over print": "All Over Print", "checked": "Checked",
            }
            norm_design = design_map.get(norm_design.lower().strip(), norm_design.title())
        else:
            if any(k in cleaned_query for k in ["graphic", "print", "anime"]):
                norm_design = "Graphic Print"
                notes.append("Inferred design: 'Graphic Print'")
            elif any(k in cleaned_query for k in ["typography", "text", "quote", "slogan"]):
                norm_design = "Typography"
                notes.append("Inferred design: 'Typography'")
            elif any(k in cleaned_query for k in ["solid", "plain", "basic"]):
                norm_design = "Solid"
                notes.append("Inferred design: 'Solid'")
            elif "washed" in cleaned_query or "acid" in cleaned_query:
                norm_design = "Washed"
                notes.append("Inferred design: 'Washed'")

        # Step 7: Fandom detection
        norm_fandom = input_data.fandom
        if not norm_fandom or norm_fandom.lower() in ("none", "any", ""):
            for entity, partner in ENTITY_FRANCHISE_MAP.items():
                if entity in cleaned_query:
                    norm_fandom = partner.title()
                    notes.append(f"Detected fandom partner '{norm_fandom}' from entity '{entity}'")
                    break

        # Step 8: Vibe detection
        applied_vibe = input_data.vibe
        inferred_vibe_tags: List[str] = []
        for vibe_name, vibe_tags in VIBE_MAP.items():
            if vibe_name in cleaned_query:
                applied_vibe = vibe_name
                inferred_vibe_tags = vibe_tags.split()
                notes.append(f"Applied aesthetic vibe: '{vibe_name}'")
                break

        # Step 9: Compile store specifications
        bewakoof_spec = BewakoofCompiler.compile(
            gender=g,
            category=canonical_cat,
            sleeve=input_data.sleeve,
            fandom=norm_fandom,
            design=norm_design,
            fit=norm_fit,
        )

        raw_kw_list = [w for w in cleaned_query.split() if w not in NOISE_WORDS]
        shopify_spec = ShopifyCompiler.compile(
            raw_keywords=raw_kw_list,
            category=canonical_cat,
            gender=g,
            fandom=norm_fandom,
            color=norm_color,
        )

        universal_spec = UniversalCompiler.compile(
            category=canonical_cat,
            macro_category=macro_cat,
            gender=g,
            color=norm_color,
            color_family=color_fam,
            sizes=norm_sizes,
            fit=norm_fit,
            design=norm_design,
            fandom=norm_fandom,
            max_price=input_data.max_price,
            min_rating=input_data.min_rating,
        )

        # Step 10: Build search tiers
        search_tiers = SearchTierCompiler.build_tiers(
            category=canonical_cat,
            color=norm_color,
            fit=norm_fit,
            design=norm_design,
            sizes=norm_sizes,
            max_price=input_data.max_price,
        )

        return ResolvedCatalogIntent(
            original_query=input_data.query_text,
            canonical_category=canonical_cat,
            macro_category=macro_cat,
            category_synonyms=synonyms,
            normalized_gender=g,
            normalized_color=norm_color,
            color_family=color_fam,
            hex_anchor=hex_anchor,
            normalized_sizes=norm_sizes,
            normalized_fit=norm_fit,
            normalized_design=norm_design,
            normalized_sleeve=input_data.sleeve,
            normalized_fabric=input_data.fabric,
            normalized_neck=input_data.neck,
            normalized_fandom=norm_fandom,
            vibe_applied=applied_vibe,
            inferred_vibe_tags=inferred_vibe_tags,
            max_price=input_data.max_price,
            min_rating=input_data.min_rating,
            bewakoof=bewakoof_spec,
            shopify=shopify_spec,
            universal=universal_spec,
            search_tiers=search_tiers,
            confidence_score=confidence,
            mapping_notes=notes,
        )


# Global default mapper singleton
_DEFAULT_MAPPER = IntentCatalogMapper()

def map_intent_to_catalog(input_data: CatalogMappingInput) -> ResolvedCatalogIntent:
    """Public convenience function to map an input contract to a resolved catalog intent."""
    return _DEFAULT_MAPPER.map_intent(input_data)


# ------------------------------------------------------------------------------
# 4. Native LLM Extension Hook (Gemini & Grok/Groq)
# ------------------------------------------------------------------------------

class NativeLLMHook:
    """
    Provides native access to project LLM endpoints (Gemini & Grok/Groq) for
    situations where complex multi-intent decomposition requires LLM reasoning.
    
    Environment variables used:
      - GEMINI_API_KEY: Configured in .env for Google Gemini models (e.g. gemini-2.5-flash)
      - GROQ_API_KEY / XAI_API_KEY: Configured in .env for Groq / xAI Grok endpoints
    """

    @staticmethod
    def get_api_keys() -> Dict[str, Optional[str]]:
        """Returns the configured API key status for the project's LLM endpoints."""
        return {
            "gemini": os.getenv("GEMINI_API_KEY"),
            "groq": os.getenv("GROQ_API_KEY"),
            "xai": os.getenv("XAI_API_KEY"),
        }

    @staticmethod
    def is_gemini_available() -> bool:
        return bool(os.getenv("GEMINI_API_KEY"))

    @staticmethod
    def is_groq_available() -> bool:
        return bool(os.getenv("GROQ_API_KEY") or os.getenv("XAI_API_KEY"))
