"""Confidence gate combining ASR, intent, retrieval score, and chemical safety rules."""

from __future__ import annotations

from app.config import Settings
from app.models.schemas import (
    ConfidenceResult,
    GateDecision,
    Intent,
    LiveToolResult,
    RetrievedPassage,
)
from app.safety.guardrails import contains_chemical_advice

REFUSAL_MESSAGES = {
    "en": (
        "I am not fully sure about this based on verified agricultural sources. "
        "Please contact the Kisan Call Centre at {kcc} or your nearest Krishi Vigyan Kendra (KVK) for expert guidance."
    ),
    "hi": (
        "प्रमाणित कृषि स्रोतों के आधार पर मुझे इस बारे में पूरी जानकारी नहीं है। "
        "कृपया सही सलाह के लिए किसान कॉल सेंटर ({kcc}) या अपने नजदीकी कृषि विज्ञान केंद्र (KVK) से संपर्क करें।"
    ),
    "mr": (
        "प्रमाणित कृषी स्रोतांच्या आधारे मला याबद्दल पूर्ण खात्रीशीर माहिती नाही. "
        "कृपया योग्य मार्गदर्शनासाठी किसान कॉल सेंटर ({kcc}) किंवा जवळच्या कृषी विज्ञान केंद्राशी (KVK) संपर्क साधा."
    ),
}

REPEAT_MESSAGES = {
    "en": "I could not hear your voice note clearly. Please speak clearly in a quiet place and send your question again.",
    "hi": "आपकी आवाज स्पष्ट सुनाई नहीं दी। कृपया शांत जगह से साफ आवाज में अपना सवाल दोबारा भेजें।",
    "mr": "तुमचा आवाज स्पष्ट ऐकू आला नाही. कृपया शांत ठिकाणाहून स्पष्ट आवाजात तुमचा प्रश्न पुन्हा पाठवा.",
}

CHEMICAL_SAFETY_NOTES = {
    "en": "Safety note: Always read the product label, wear gloves and a mask, and confirm dosage with your local KVK before spraying.",
    "hi": "सुरक्षा सावधानी: छिड़काव से पहले लेबल पढ़ें, दस्ताने व मास्क पहनें और अपने नजदीकी KVK से मात्रा की पुष्टि करें।",
    "mr": "सुरक्षा सूचना: फवारणीपूर्वी लेबल वाचा, हातमोजे व मास्क वापरा आणि जवळच्या KVK कडून मात्रा तपासून घ्या.",
}


class ConfidenceGate:
    """Decides whether to ANSWER, ASK_REPEAT, or REFUSE with explicit reason codes."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def evaluate(
        self,
        asr_confidence: float,
        intent: Intent,
        passages: list[RetrievedPassage],
        live_result: LiveToolResult | None = None,
        query_text: str = "",
    ) -> ConfidenceResult:
        if asr_confidence < self.settings.asr_min_confidence:
            return ConfidenceResult(
                decision=GateDecision.ASK_REPEAT,
                reason_code="LOW_ASR_CONFIDENCE",
                combined_score=round(asr_confidence, 3),
            )

        if intent == Intent.OUT_OF_SCOPE:
            return ConfidenceResult(
                decision=GateDecision.REFUSE,
                reason_code="OUT_OF_SCOPE",
                combined_score=0.0,
            )

        if intent == Intent.GREETING:
            return ConfidenceResult(
                decision=GateDecision.ANSWER,
                reason_code="GREETING",
                combined_score=1.0,
            )

        # Live tools path
        if intent in (Intent.MARKET_PRICE, Intent.WEATHER):
            if live_result and live_result.success:
                return ConfidenceResult(
                    decision=GateDecision.ANSWER,
                    reason_code="LIVE_TOOL_OK",
                    combined_score=round(0.9 * asr_confidence + 0.1, 3),
                )
            return ConfidenceResult(
                decision=GateDecision.REFUSE,
                reason_code="LIVE_DATA_UNAVAILABLE",
                combined_score=0.2,
            )

        # RAG path
        if not passages:
            return ConfidenceResult(
                decision=GateDecision.REFUSE,
                reason_code="NO_RETRIEVED_EVIDENCE",
                combined_score=0.0,
            )

        top_score = passages[0].rerank_score
        if top_score < self.settings.retrieval_min_score:
            return ConfidenceResult(
                decision=GateDecision.REFUSE,
                reason_code="LOW_RETRIEVAL_CONFIDENCE",
                combined_score=round(top_score, 3),
            )

        combined_text = query_text + " " + " ".join(p.text for p in passages[:2])
        has_chem = contains_chemical_advice(combined_text)

        # Stricter threshold for chemical / dosage advice
        if has_chem and top_score < max(self.settings.retrieval_min_score, 0.34):
            return ConfidenceResult(
                decision=GateDecision.REFUSE,
                reason_code="LOW_CONFIDENCE_CHEMICAL_ADVICE",
                combined_score=round(top_score, 3),
                has_chemical_advice=True,
                safety_note_required=True,
            )

        combined = round(0.35 * asr_confidence + 0.65 * top_score, 3)
        return ConfidenceResult(
            decision=GateDecision.ANSWER,
            reason_code="GROUNDED_EVIDENCE_OK",
            combined_score=combined,
            has_chemical_advice=has_chem,
            safety_note_required=has_chem,
        )

    def get_refusal_text(self, language: str) -> str:
        tmpl = REFUSAL_MESSAGES.get(language, REFUSAL_MESSAGES["en"])
        return tmpl.format(kcc=self.settings.kisan_call_centre)

    def get_repeat_text(self, language: str) -> str:
        return REPEAT_MESSAGES.get(language, REPEAT_MESSAGES["en"])

    def get_chemical_safety_note(self, language: str) -> str:
        return CHEMICAL_SAFETY_NOTES.get(language, CHEMICAL_SAFETY_NOTES["en"])
