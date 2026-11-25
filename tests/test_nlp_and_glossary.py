"""Tests for language ID, code-mixed queries, intent/entities, and glossary translation."""

from app.models.schemas import Intent
from app.nlp.query_understanding import QueryUnderstandingService
from app.nlp.translation import TranslationService


def test_marathi_hindi_codemix_detection():
    nlu = QueryUnderstandingService()

    mr = nlu.analyze("माझ्या कापूस पिकाची पाने पिवळी पडत आहेत, काय करावे?")
    assert mr.detected_language == "mr"
    assert mr.intent == Intent.PEST_DISEASE
    assert mr.entities.crop == "cotton"

    hi = nlu.analyze("नागपुर में आज मौसम और बारिश का हाल बताइए")
    assert hi.detected_language == "hi"
    assert hi.intent == Intent.WEATHER
    assert hi.entities.location == "Nagpur"
    assert hi.entities.state == "Maharashtra"

    cm = nlu.analyze("mere rice fasal me stem borer lag gaya hai control kaise kare?")
    assert cm.detected_language == "hi"
    assert cm.intent == Intent.PEST_DISEASE
    assert cm.entities.crop == "rice"


def test_glossary_protected_translation(test_settings):
    tr = TranslationService(test_settings)
    en_q = tr.to_english("कापसावर गुलाबी बोंड अळी आली आहे", "mr")
    assert "cotton" in en_q.lower()
    assert "pink bollworm" in en_q.lower()

    mr_ans = tr.from_english("Spray Neem oil 1500 ppm for pink bollworm on cotton.", "mr")
    assert "गुलाबी बोंड अळी" in mr_ans
    assert "कापूस" in mr_ans
