"""Glossary-protected multilingual translation (English <-> Hindi <-> Marathi)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.config import Settings

# Common agricultural phrase mappings for fast, deterministic offline translation
PHRASE_TEMPLATES_EN_TO_HI = {
    "yellowing leaves": "पीले पत्ते",
    "pink bollworm": "गुलाबी सुंडी",
    "drain excess standing water": "खेत से अतिरिक्त पानी तुरंत निकालें",
    "spray": "छिड़काव करें",
    "per liter of water": "प्रति लीटर पानी में",
    "per hectare": "प्रति हेक्टेयर",
    "per acre": "प्रति एकड़",
    "days after sowing": "बुवाई के दिन बाद",
    "safety note": "सुरक्षा सावधानी",
    "source": "स्रोत",
    "data as of": "डेटा दिनांक",
    "consult your local kvk": "अपने नजदीकी कृषि विज्ञान केंद्र (KVK) से सलाह लें",
}

PHRASE_TEMPLATES_EN_TO_MR = {
    "yellowing leaves": "पाने पिवळी पडणे",
    "pink bollworm": "गुलाबी बोंड अळी",
    "drain excess standing water": "शेतातील जादा साचलेले पाणी तात्काळ बाहेर काढा",
    "spray": "फवारणी करा",
    "per liter of water": "प्रति लिटर पाण्यात",
    "per hectare": "प्रति हेक्टर",
    "per acre": "प्रति एकर",
    "days after sowing": "पेरणीच्या दिवसांनंतर",
    "safety note": "सुरक्षा सूचना",
    "source": "स्रोत",
    "data as of": "माहिती दिनांक",
    "consult your local kvk": "तुमच्या जवळच्या कृषी विज्ञान केंद्राचा (KVK) सल्ला घ्या",
}


class TranslationService:
    """Translates queries and answers while protecting domain glossary terms."""

    def __init__(self, settings: Settings, glossary_path: Path | None = None):
        self.settings = settings
        self.glossary_path = glossary_path or Path("data/glossary.json")
        self.terms: list[dict] = self._load_glossary()

    def _load_glossary(self) -> list[dict]:
        if self.glossary_path.exists():
            return json.loads(self.glossary_path.read_text(encoding="utf-8"))
        return []

    def reload_glossary(self, terms: list[dict]) -> None:
        self.terms = terms

    def to_english(self, text: str, source_lang: str) -> str:
        """Translate Hindi/Marathi/code-mixed query to English with glossary preservation."""
        if source_lang == "en":
            return text

        result = text
        # Handle common Marathi/Hindi morphological inflections before glossary lookup
        stem_map = {
            "कापसावर": "cotton",
            "कापसाची": "cotton",
            "कापसाचे": "cotton",
            "कांद्याचा": "onion",
            "कांद्यावर": "onion",
            "गव्हावर": "wheat",
            "भातावर": "rice",
            "सोयाबीनवर": "soybean",
            "पिकाची": "crop",
            "पिकावर": "crop",
            "पडत आहेत": " ",
            "आली आहे": " ",
            "लग गया है": " ",
            "झाले तर": " ",
            "ई-केवाईसी": "e-kyc",
            "केवाईसी": "e-kyc",
            "पीएम किसान": "PM-KISAN",
            "पीएम-किसान": "PM-KISAN",
            "पीक विमा": "PMFBY crop insurance",
            "फसल बीमा": "PMFBY crop insurance",
            "थ्रिप्स": "thrips",
        }
        for src_s, en_s in stem_map.items():
            if src_s in result:
                result = result.replace(src_s, f" {en_s} ")

        # Replace glossary terms from source_lang -> en
        for term in self.terms:
            src_val = term.get(source_lang) or ""
            en_val = term.get("en") or ""
            if src_val and en_val and src_val.lower() in result.lower():
                result = re.sub(re.escape(src_val), f" {en_val} ", result, flags=re.IGNORECASE)

        # Common Hindi/Marathi agricultural question words -> English keywords for retrieval
        word_map = {
            "पीले": "yellowing", "पत्ते": "leaves", "पिवळी": "yellowing", "पाने": "leaves",
            "भाव": "price", "मंडी": "mandi", "बाजार": "market", "आज": "today",
            "मौसम": "weather", "बारिश": "rain", "हवामान": "weather", "पाऊस": "rain", "पावसामुळे": "rain",
            "दवा": "pesticide", "फवारणी": "spray", "छिड़काव": "spray", "छिड़कें": "spray",
            "योजना": "scheme", "पात्रता": "eligibility", "किस्त": "installment", "हप्ता": "installment",
            "नुकसान": "loss", "बीमा": "insurance", "विमा": "insurance",
            "तक्रार": "report", "तासात": "hours", "किती": "how many",
            "बुवाई": "sowing", "लागवड": "sowing", "बीज": "seed", "उपचार": "treatment",
            "भंडारण": "storage", "सलाह": "advisory", "कीटनाशक": "insecticide",
            "कीट": "pest", "रोग": "disease", "नियंत्रण": "control", "रोकथाम": "control",
            "खेती": "cultivation", "कैसे": "how", "कसे": "how", "कब": "when", "कधी": "when",
            "कितना": "how much", "कोणती": "which", "काय": "what", "करावे": "do", "करू": "do", "करें": "do",
        }
        for src_w, en_w in word_map.items():
            if src_w in result:
                result = result.replace(src_w, f" {en_w} ")

        # Remove common Hindi/Marathi grammatical stopwords while keeping unknown domain nouns (e.g. avocado, ladakh)
        devanagari_stopwords = {
            "में", "के", "लिए", "कौन", "सा", "सी", "से", "की", "का", "को", "है", "हैं", "और", "पर",
            "माझ्या", "माझे", "आहे", "आहेत", "वर", "मध्ये", "सांगा", "तर", "असेल", "होते",
        }
        tokens = [t for t in result.split() if t not in devanagari_stopwords]
        return " ".join(tokens)

    def from_english(self, text_en: str, target_lang: str) -> str:
        """Translate short grounded English answer to Hindi or Marathi using glossary + templates."""
        if target_lang == "en":
            return text_en

        out = text_en
        phrase_map = (
            PHRASE_TEMPLATES_EN_TO_HI
            if target_lang == "hi"
            else PHRASE_TEMPLATES_EN_TO_MR
        )
        for en_phrase, tgt_phrase in phrase_map.items():
            out = re.sub(re.escape(en_phrase), tgt_phrase, out, flags=re.IGNORECASE)

        # Apply glossary terms (longest match first)
        sorted_terms = sorted(self.terms, key=lambda t: len(t.get("en", "")), reverse=True)
        for term in sorted_terms:
            en_val = term.get("en", "")
            tgt_val = term.get(target_lang, "")
            if en_val and tgt_val:
                out = re.sub(
                    rf"\b{re.escape(en_val)}\b",
                    tgt_val,
                    out,
                    flags=re.IGNORECASE,
                )
        return out
