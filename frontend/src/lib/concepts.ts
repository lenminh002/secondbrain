const COMMON_CONCEPT_STOPWORDS = new Set([
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
]);

const GENERIC_CONCEPT_WORDS = new Set([
  "agent", "agents", "back", "content", "data", "example", "fact", "file", "first",
  "good", "great", "idea", "ideas", "information", "knowledge", "look", "lot", "make",
  "note", "notes", "people", "person", "point", "process", "question", "questions",
  "source", "still", "system", "thing", "things", "think", "time", "way", "well",
  "work", "year",
]);

function labelWords(label: string) {
  return label
    .trim()
    .replace(/\s+/g, " ")
    .split(" ")
    .map((word) => word.replace(/^[-_.,:;!?()[\]{}"']+|[-_.,:;!?()[\]{}"']+$/g, "").toLowerCase())
    .filter(Boolean);
}

export function isQualityConcept(label: string) {
  const normalized = label.trim().replace(/\s+/g, " ");
  if (normalized.length < 3) return false;

  const words = labelWords(normalized);
  if (!words.length) return false;

  if (words.length === 1 && (COMMON_CONCEPT_STOPWORDS.has(words[0]) || GENERIC_CONCEPT_WORDS.has(words[0]))) {
    return false;
  }

  return words.some((word) => !COMMON_CONCEPT_STOPWORDS.has(word) && !GENERIC_CONCEPT_WORDS.has(word));
}

export function filterQualityConcepts(labels: string[]) {
  const seen = new Set<string>();
  return labels.filter((label) => {
    const normalized = label.trim().replace(/\s+/g, " ");
    const key = normalized.toLowerCase();
    if (!normalized || seen.has(key) || !isQualityConcept(normalized)) return false;
    seen.add(key);
    return true;
  });
}
