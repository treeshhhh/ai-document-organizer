"""Transparent deterministic suggestions; no custom classifier was trained."""
from collections import Counter
import re

CATEGORIES = {
    'Finance': {'invoice', 'payment', 'budget', 'revenue', 'expense', 'billing', 'receipt', 'tax', 'cost'},
    'Research': {'research', 'experiment', 'hypothesis', 'study', 'dataset', 'findings', 'methodology', 'abstract'},
    'Education': {'homework', 'lecture', 'course', 'assignment', 'student', 'exam', 'curriculum', 'lesson'},
    'Legal': {'contract', 'agreement', 'liability', 'clause', 'legal', 'confidentiality', 'parties', 'termination'},
    'Career': {'resume', 'employment', 'hiring', 'internship', 'recruitment', 'candidate', 'interview', 'position'},
    'Technology': {'software', 'algorithm', 'database', 'api', 'deployment', 'code', 'server', 'encryption'},
    'Personal': {'travel', 'itinerary', 'recipe', 'vacation', 'appointment', 'family', 'hotel', 'flight'},
}
STOP = set('the a an of to and or for in on is are was were be been with by from at as it its this that these those we our you your their they can will not into about document text have has had also which using use'.split())


def words(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z'-]{2,}", text.lower())


def suggest(text: str, filename: str) -> dict:
    tokens = words(text)
    counts = Counter(w for w in tokens if w not in STOP)
    keywords = [w for w, _ in counts.most_common(8)]
    scores = {category: sum(min(counts[word], 3) for word in terms) for category, terms in CATEGORIES.items()}
    ranked = sorted(scores, key=lambda c: (-scores[c], c))
    best = ranked[0]
    score = scores[best]
    if not score:
        category, strength = 'Other', 0.0
        evidence = []
    else:
        category = best
        # Heuristic strength combines coverage and separation, not a probability.
        coverage = min(score / 6, 1)
        separation = (score - scores[ranked[1]]) / score
        strength = round(.5 * coverage + .5 * separation, 3)
        evidence = sorted(w for w in CATEGORIES[best] if counts[w])
    lines = [re.sub(r'^\s*#+\s*', '', line).strip() for line in text.splitlines() if line.strip()]
    first = lines[0] if lines else filename.rsplit('.', 1)[0]
    title = first[:100].strip() if len(first.split()) <= 18 else filename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ')[:100]
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text) if s.strip()]
    if sentences:
        def rank(item):
            index, sentence = item
            terms = words(sentence)
            return sum(counts[t] for t in set(terms) if t not in STOP) / max(1, len(terms)) ** .5
        chosen = sorted(sorted(enumerate(sentences), key=rank, reverse=True)[:3])
        summary = ' '.join(sentence for _, sentence in chosen)[:650]
    else:
        summary = text[:650]
    return {'title': title or filename, 'keywords': keywords, 'summary': summary, 'category': category,
            'classification_strength': strength, 'classification_evidence': evidence,
            'method': 'keyword rules + frequency-ranked extractive summary; suggestions, not verified facts'}
