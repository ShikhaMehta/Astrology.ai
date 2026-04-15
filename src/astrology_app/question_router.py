from __future__ import annotations

from astrology_app.models import QuestionCategory


def categorize_question(question: str) -> QuestionCategory:
    text = question.lower()
    if _contains_any(text, ("career", "job", "profession", "income", "money", "finance")):
        return QuestionCategory.CAREER
    if _contains_any(text, ("marriage", "relationship", "partner", "love", "spouse")):
        return QuestionCategory.RELATIONSHIPS
    if _contains_any(
        text,
        ("family", "children", "child", "kid", "kids", "parents", "home"),
    ):
        return QuestionCategory.FAMILY
    if _contains_any(text, ("health", "disease", "wellness", "illness")):
        return QuestionCategory.HEALTH
    if _contains_any(text, ("spiritual", "moksha", "sadhana", "dharma")):
        return QuestionCategory.SPIRITUAL
    if _contains_any(text, ("when", "timing", "period", "dasha", "transit")):
        return QuestionCategory.TIMING
    if _contains_any(text, ("personality", "nature", "strength", "weakness", "life path")):
        return QuestionCategory.PERSONALITY
    return QuestionCategory.GENERAL


def select_relevant_chart_keys(category: QuestionCategory) -> list[str]:
    category_to_keys = {
        QuestionCategory.PERSONALITY: ["charts.d1", "charts.d9", "nakshatras"],
        QuestionCategory.CAREER: ["charts.d1", "charts.d9", "dashas"],
        QuestionCategory.RELATIONSHIPS: ["charts.d1", "charts.d9", "dashas", "nakshatras"],
        QuestionCategory.FAMILY: ["charts.d1", "dashas"],
        QuestionCategory.HEALTH: ["charts.d1", "dashas"],
        QuestionCategory.SPIRITUAL: ["charts.d9", "nakshatras", "dashas"],
        QuestionCategory.TIMING: ["dashas", "charts.d1"],
        QuestionCategory.GENERAL: ["charts.d1", "charts.d9", "dashas", "nakshatras"],
    }
    return category_to_keys[category]


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)
