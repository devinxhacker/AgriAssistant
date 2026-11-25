"""Content guardrails for harmful, off-topic, or unsafe chemical requests."""

from __future__ import annotations

import re

UNSAFE_PATTERNS = [
    r"\b(suicide|kill myself|poison someone|self harm)\b",
    r"\b(bomb|explosive|weapon)\b",
    r"\b(ignore previous instructions|system prompt|jailbreak)\b",
    r"(आत्महत्या|जहर किसी को)",
]

CHEMICAL_KEYWORDS = {
    "pesticide", "insecticide", "fungicide", "herbicide", "spray", "dose", "dosage",
    "urea", "dap", "profenofos", "emamectin", "imidacloprid", "chlorantraniliprole",
    "propiconazole", "fipronil", "spinosad", "cartap", "neem oil", "magnesium sulphate",
    "दवा", "कीटनाशक", "फवारणी", "छिड़काव", "यूरिया", "युरिया",
}


def check_content_safety(text: str) -> tuple[bool, str]:
    """Return (is_safe, reason_code)."""
    lower = text.lower()
    for pat in UNSAFE_PATTERNS:
        if re.search(pat, lower):
            return False, "UNSAFE_OR_INJECTION_REQUEST"
    return True, "SAFE"


def contains_chemical_advice(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in CHEMICAL_KEYWORDS)
