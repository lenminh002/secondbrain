from __future__ import annotations

COMMON_CONCEPT_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "also", "am", "an",
    "and", "any", "are", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "could", "did", "do", "does",
    "doing", "down", "during", "each", "few", "for", "from", "further", "get", "go",
    "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself",
    "just", "like", "many", "me", "more", "most", "my", "myself", "need", "no",
    "nor", "not", "of", "off", "on", "once", "only", "or", "other", "our", "ours",
    "ourselves", "out", "over", "own", "same", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who",
    "whom", "why", "will", "with", "would", "you", "your", "yours", "yourself",
    "yourselves",
}

GENERIC_CONCEPT_WORDS = {
    "agent", "agents", "back", "content", "data", "example", "fact", "file", "first",
    "good", "great", "idea", "ideas", "information", "knowledge", "look", "lot", "make",
    "note", "notes", "people", "person", "point", "process", "question", "questions",
    "source", "still", "system", "thing", "things", "think", "time", "way", "well",
    "work", "year",
}


def _label_words(label: str) -> list[str]:
    return [
        word.strip("-_.,:;!?()[]{}\"'").lower()
        for word in " ".join(str(label).strip().split()).split()
    ]


def is_quality_concept(label: str) -> bool:
    normalized = " ".join(str(label).strip().split())
    if len(normalized) < 3:
        return False

    words = [word for word in _label_words(normalized) if word]
    if not words:
        return False

    if len(words) == 1 and (
        words[0] in COMMON_CONCEPT_STOPWORDS or words[0] in GENERIC_CONCEPT_WORDS
    ):
        return False

    meaningful = [
        word
        for word in words
        if word not in COMMON_CONCEPT_STOPWORDS and word not in GENERIC_CONCEPT_WORDS
    ]
    return bool(meaningful)


def filter_quality_concepts(labels: list[str], limit: int | None = None) -> list[str]:
    filtered: list[str] = []
    seen: set[str] = set()
    for label in labels:
        normalized = " ".join(str(label).strip().split())
        key = normalized.lower()
        if not normalized or key in seen or not is_quality_concept(normalized):
            continue
        seen.add(key)
        filtered.append(normalized)
        if limit is not None and len(filtered) >= limit:
            break
    return filtered
