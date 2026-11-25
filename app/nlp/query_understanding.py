"""Language identification, code-mixed handling, intent classification, and entity extraction."""

from __future__ import annotations

import re

from app.models.schemas import ExtractedEntities, Intent, QueryUnderstandingResult

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
LATIN_RE = re.compile(r"[A-Za-z]")

MARATHI_MARKERS = {
    "आहे", "आहेत", "माझ्या", "माझे", "तुमच्या", "सांगा", "करावे", "करू", "कसे", "कधी",
    "कोणती", "कापूस", "कांदा", "भात", "गहू", "हरभरा", "तूर", "पाने", "पिवळी", "अळी",
    "भाव", "बाजार", "हवामान", "पाऊस", "शेतकरी", "विमा", "योजना", "फवारणी", "माहिती",
    "maza", "mazya", "kapus", "kanda", "kay", "kase", "ahe", "sanga", "bhav", "favarni",
}

HINDI_MARKERS = {
    "है", "हैं", "मेरे", "मेरी", "बताइए", "बताओ", "करें", "कैसे", "कब", "क्या", "कौन",
    "कपास", "प्याज", "धान", "गेहूं", "चना", "अरहर", "पत्ते", "पीले", "सुंडी", "मंडी",
    "मौसम", "बारिश", "किसान", "बीमा", "योजना", "छिड़काव", "जानकारी",
    "mere", "meri", "kya", "kaise", "kab", "batao", "bataiye", "fasal", "keeda", "mandi",
}

CROP_PATTERNS: dict[str, list[str]] = {
    "cotton": ["cotton", "kapas", "kapus", "कपास", "कापूस", "कापसा"],
    "soybean": ["soybean", "soya", "soyabean", "सोयाबीन"],
    "wheat": ["wheat", "gehu", "gehun", "gahu", "गेहूं", "गहू", "गव्हा"],
    "rice": ["rice", "paddy", "dhan", "bhat", "धान", "भात", "भाता", "चावल"],
    "onion": ["onion", "pyaz", "pyaj", "kanda", "प्याज", "कांदा", "कांद्या"],
    "sugarcane": ["sugarcane", "ganna", "oos", "ऊस", "उसा", "गन्ना"],
    "pigeon pea": ["pigeon pea", "tur", "toor", "arhar", "अरहर", "तूर", "तुरी"],
    "chickpea": ["chickpea", "gram", "chana", "harbhara", "चना", "हरभरा", "हरभऱ्या"],
}

LOCATION_STATE_MAP: dict[str, tuple[str, str]] = {
    "nagpur": ("Nagpur", "Maharashtra"),
    "नागपुर": ("Nagpur", "Maharashtra"),
    "नागपूर": ("Nagpur", "Maharashtra"),
    "pune": ("Pune", "Maharashtra"),
    "पुणे": ("Pune", "Maharashtra"),
    "nashik": ("Nashik", "Maharashtra"),
    "नाशिक": ("Nashik", "Maharashtra"),
    "lasalgaon": ("Lasalgaon", "Maharashtra"),
    "लासलगाव": ("Lasalgaon", "Maharashtra"),
    "akola": ("Akola", "Maharashtra"),
    "अकोला": ("Akola", "Maharashtra"),
    "latur": ("Latur", "Maharashtra"),
    "लातूर": ("Latur", "Maharashtra"),
    "maharashtra": ("Maharashtra", "Maharashtra"),
    "महाराष्ट्र": ("Maharashtra", "Maharashtra"),
    "indore": ("Indore", "Madhya Pradesh"),
    "इंदौर": ("Indore", "Madhya Pradesh"),
    "lucknow": ("Lucknow", "Uttar Pradesh"),
    "लखनऊ": ("Lucknow", "Uttar Pradesh"),
    "kanpur": ("Kanpur", "Uttar Pradesh"),
    "कानपुर": ("Kanpur", "Uttar Pradesh"),
    "karnal": ("Karnal", "Haryana"),
    "करनाल": ("Karnal", "Haryana"),
    "ludhiana": ("Ludhiana", "Punjab"),
}

SCHEME_PATTERNS: dict[str, list[str]] = {
    "PM-KISAN": ["pm-kisan", "pm kisan", "pmkisan", "पीएम-किसान", "पीएम किसान", "किसान सम्मान"],
    "PMFBY": ["pmfby", "fasal bima", "pik vima", "फसल बीमा", "पीक विमा"],
    "KCC": ["kcc", "kisan credit", "किसान क्रेडिट"],
}

SEASON_PATTERNS = {
    "Kharif": ["kharif", "खरीफ", "खरीप"],
    "Rabi": ["rabi", "रबी", "रब्बी"],
    "Zaid": ["zaid", "जायद"],
}


class QueryUnderstandingService:
    """Detects language, code-mixing, intent, entities, and normalizes query text."""

    def analyze(self, text: str, language_hint: str | None = None) -> QueryUnderstandingResult:
        cleaned = " ".join(text.strip().split())
        lower = cleaned.lower()
        tokens = set(re.findall(r"[\w\u0900-\u097F-]+", lower))

        has_dev = bool(DEVANAGARI_RE.search(cleaned))
        has_lat = bool(LATIN_RE.search(cleaned))
        is_code_mixed = has_dev and has_lat

        # Language detection
        detected_lang = self._detect_language(cleaned, tokens, has_dev, language_hint)

        # Entities
        crop = self._match_first(lower, CROP_PATTERNS)
        location, state = self._match_location(lower)
        scheme_name = self._match_first(lower, SCHEME_PATTERNS)
        season = self._match_first(lower, SEASON_PATTERNS)

        # Intent classification
        intent = self._classify_intent(lower, tokens, crop, scheme_name)

        entities = ExtractedEntities(
            crop=crop,
            location=location,
            state=state,
            season=season,
            commodity=crop,
            mandi=location if intent == Intent.MARKET_PRICE else None,
            scheme_name=scheme_name,
        )

        normalized = self._normalize_query(cleaned, entities, intent)
        return QueryUnderstandingResult(
            original_text=cleaned,
            detected_language=detected_lang,
            is_code_mixed=is_code_mixed,
            intent=intent,
            entities=entities,
            normalized_query=normalized,
        )

    def _detect_language(
        self, text: str, tokens: set[str], has_dev: bool, hint: str | None
    ) -> str:
        if "ळ" in text:
            return "mr"
        mr_score = len(tokens & MARATHI_MARKERS)
        hi_score = len(tokens & HINDI_MARKERS)
        if mr_score > hi_score:
            return "mr"
        if hi_score > mr_score:
            return "hi"
        if has_dev:
            return hint if hint in ("hi", "mr") else "hi"
        if hint in ("hi", "mr", "en"):
            return hint
        return "en"

    @staticmethod
    def _match_first(lower_text: str, mapping: dict[str, list[str]]) -> str | None:
        for canonical, variants in mapping.items():
            for v in variants:
                if v in lower_text:
                    return canonical
        return None

    @staticmethod
    def _match_location(lower_text: str) -> tuple[str | None, str | None]:
        for key, (loc, st) in LOCATION_STATE_MAP.items():
            if key in lower_text:
                return loc, st
        return None, None

    @staticmethod
    def _classify_intent(
        lower_text: str, tokens: set[str], crop: str | None, scheme_name: str | None
    ) -> Intent:
        if tokens <= {"hi", "hello", "namaste", "namaskar", "नमस्ते", "नमस्कार"}:
            return Intent.GREETING

        out_of_scope_kw = [
            "cricket", "movie", "song", "politics", "bitcoin", "stock market",
            "recipe", "joke", "exam", "ipl", "फिल्म", "गाना", "क्रिकेट",
        ]
        if any(k in lower_text for k in out_of_scope_kw):
            return Intent.OUT_OF_SCOPE

        if scheme_name or any(
            k in lower_text
            for k in ["scheme", "yojana", "subsidy", "insurance", "loan", "ekyc", "e-kyc", "योजना", "विमा", "बीमा", "कर्ज"]
        ):
            return Intent.SCHEME_INFO

        price_kw = [
            "price", "rate", "mandi", "bhav", "market", "quintal", "भाव", "मंडी", "बाजार", "दर",
        ]
        if any(k in lower_text for k in price_kw):
            return Intent.MARKET_PRICE

        weather_kw = [
            "weather", "rain", "forecast", "temperature", "humidity", "mausam",
            "मौसम", "बारिश", "हवामान", "पाऊस", "तापमान",
        ]
        if any(k in lower_text for k in weather_kw):
            return Intent.WEATHER

        pest_kw = [
            "pest", "bollworm", "rust", "thrips", "borer", "insect", "spray", "pesticide",
            "dose", "dosage", "yellowing", "disease", "keeda", "sundi", "ali",
            "कीट", "सुंडी", "अळी", "रोग", "फवारणी", "दवा", "पीले", "पिवळी", "तांबेरा",
        ]
        if any(k in lower_text for k in pest_kw):
            return Intent.PEST_DISEASE

        if crop or any(
            k in lower_text
            for k in ["sow", "sowing", "variety", "fertilizer", "urea", "irrigation", "crop", "बुवाई", "लागवड", "खाद", "पीक", "फसल"]
        ):
            return Intent.CROP_ADVICE

        return Intent.OUT_OF_SCOPE

    @staticmethod
    def _normalize_query(text: str, entities: ExtractedEntities, intent: Intent) -> str:
        parts = [text]
        if entities.crop and entities.crop not in text.lower():
            parts.append(f"[crop:{entities.crop}]")
        if entities.state and entities.state.lower() not in text.lower():
            parts.append(f"[state:{entities.state}]")
        if entities.scheme_name and entities.scheme_name.lower() not in text.lower():
            parts.append(f"[scheme:{entities.scheme_name}]")
        return " ".join(parts)
