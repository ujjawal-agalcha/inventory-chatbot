import hashlib
from excel.normalizer import normalize_text


def compute_row_hash(*fields) -> str:
    """Generate deterministic SHA256 hash for row deduplication."""
    content = "|".join(normalize_text(f) for f in fields)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
