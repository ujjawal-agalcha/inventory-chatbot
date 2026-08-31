import re
from typing import Any, Tuple, List

# ============================================================
# STOP WORDS FOR KEYWORD EXTRACTION
# ============================================================
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
    "to", "was", "were", "will", "with", "needed", "urgent", "office",
    "team", "all", "monthly", "room", "desk", "new", "old", "set", "pack",
    "s", "no", "sno", "item", "items", "details", "remarks", "price", "amount"
}


def normalize_text(text: Any) -> str:
    """Normalize string: lowercase, strip punctuation, collapse whitespace."""
    if text is None:
        return ""
    s = str(text).strip().lower()
    s = re.sub(r"[^\w\s-]", " ", s)
    return " ".join(s.split())


def clean_display_name(raw_name: Any) -> str:
    """Clean raw product name for presentation."""
    if not raw_name:
        return "Unknown Item"
    s = str(raw_name).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def extract_keywords_and_aliases(name: str, details: str = "", remarks: str = "") -> Tuple[List[str], List[str]]:
    """
    Extract meaningful search keywords and query aliases from product attributes.
    """
    combined = f"{name} {details} {remarks}".lower()
    clean_str = re.sub(r"[^\w\s-]", " ", combined)
    raw_tokens = clean_str.split()
    
    keywords = set()
    for token in raw_tokens:
        token = token.strip("-").strip()
        if len(token) >= 2 and token not in STOP_WORDS and not token.isdigit():
            keywords.add(token)
        elif token.isdigit() and len(token) <= 5:
            keywords.add(token)

    # Aliases generation
    aliases = set()
    norm_name = normalize_text(name)
    if norm_name:
        aliases.add(norm_name)
    
    # Remove parenthetical variations
    name_clean = re.sub(r"\(.*?\)", "", name).strip()
    if name_clean and normalize_text(name_clean) != norm_name:
        aliases.add(normalize_text(name_clean))

    if details:
        norm_details = normalize_text(details)
        if norm_details:
            aliases.add(norm_details)
            aliases.add(f"{norm_name} {norm_details}")

    return sorted(list(keywords)), sorted(list(aliases))
