"""
Video Transcript Analytics — NLP Pipeline

4 metrics computed on weekly submission transcripts:
  1. Confidence: assertive vs hedging language (regex-based)
  2. Topic alignment: embedding similarity to expected week topic
  3. Specificity: concrete indicators vs vague language (regex-based)
  4. Sentiment: positive/negative via distilbert (optional, degrades gracefully)
"""

import re

import numpy as np

from lib.embeddings import get_embedding
from lib.knowledge_retrieval import WEEK_TOPIC_MAP

# ---------------------------------------------------------------------------
# Confidence patterns
# ---------------------------------------------------------------------------

ASSERTIVE_PATTERNS = [
    r"\b(we will|we are|we have|we've|our plan is|we know|the data shows)\b",
    r"\b(we validated|we tested|we built|we launched|we interviewed|we shipped)\b",
    r"\b(customers told us|the numbers show|we confirmed|we proved)\b",
    r"\b(definitely|certainly|clearly|absolutely|specifically)\b",
]

HEDGING_PATTERNS = [
    r"\b(i think maybe|i'm not sure|i guess|i don't know|kind of|sort of)\b",
    r"\b(hopefully|probably|might|could be|possibly|perhaps)\b",
    r"\b(not really sure|haven't really|don't really know)\b",
    r"\b(like basically|just sort of|i mean like)\b",
]


def _count_patterns(text: str, patterns: list[str]) -> int:
    return sum(len(re.findall(p, text, re.I)) for p in patterns)


def measure_confidence(transcript: str) -> dict:
    assertive = _count_patterns(transcript, ASSERTIVE_PATTERNS)
    hedging = _count_patterns(transcript, HEDGING_PATTERNS)
    score = assertive / (assertive + hedging + 1)
    return {
        "score": round(score, 3),
        "assertive_count": assertive,
        "hedging_count": hedging,
    }


# ---------------------------------------------------------------------------
# Topic alignment
# ---------------------------------------------------------------------------

def measure_topic_alignment(transcript: str, week_number: int) -> dict:
    expected_topic = WEEK_TOPIC_MAP.get(week_number)
    if not expected_topic or not transcript.strip():
        return {"score": 0.0, "best_match_week": week_number, "is_on_topic": False}

    transcript_emb = np.array(get_embedding(transcript[:2000]))
    expected_emb = np.array(get_embedding(expected_topic))
    alignment = float(np.dot(transcript_emb, expected_emb) / (
        np.linalg.norm(transcript_emb) * np.linalg.norm(expected_emb) + 1e-9
    ))

    all_alignments = {}
    for week, topic in WEEK_TOPIC_MAP.items():
        topic_emb = np.array(get_embedding(topic))
        sim = float(np.dot(transcript_emb, topic_emb) / (
            np.linalg.norm(transcript_emb) * np.linalg.norm(topic_emb) + 1e-9
        ))
        all_alignments[week] = sim

    best_match_week = max(all_alignments, key=all_alignments.get)

    return {
        "score": round(alignment, 3),
        "best_match_week": best_match_week,
        "is_on_topic": alignment > 0.4,
        "topic_gap": best_match_week - week_number,
    }


# ---------------------------------------------------------------------------
# Specificity
# ---------------------------------------------------------------------------

SPECIFIC_PATTERNS = [
    r"\b\d+\s*%",                          # percentages
    r"[\$\u00a3\u20ac]\s*\d+",             # money references
    r"\b\d+\s*(customers?|users?|people|restaurants?|interviews?)\b",
    r"\b(tested|built|launched|interviewed|shipped|signed|converted)\b",
]

VAGUE_PATTERNS = [
    r"\b(things|stuff|whatever|something|somehow|basically)\b",
    r"\b(a lot of|tons of|really big|super important)\b",
    r"\b(everyone|people in general|the market)\b",
]


def measure_specificity(transcript: str) -> dict:
    specific = _count_patterns(transcript, SPECIFIC_PATTERNS)
    vague = _count_patterns(transcript, VAGUE_PATTERNS)
    score = specific / (specific + vague + 1)

    numbers = re.findall(r"\b\d+[\d,.]*\b", transcript)

    return {
        "score": round(score, 3),
        "specific_count": specific,
        "vague_count": vague,
        "number_count": len(numbers),
    }


# ---------------------------------------------------------------------------
# Sentiment (optional — requires transformers)
# ---------------------------------------------------------------------------

_sentiment_pipeline = None


def _get_sentiment_pipeline():
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        try:
            from transformers import pipeline
            _sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english",
            )
        except Exception:
            _sentiment_pipeline = False  # mark as unavailable
    return _sentiment_pipeline if _sentiment_pipeline is not False else None


def measure_sentiment(transcript: str) -> dict:
    pipe = _get_sentiment_pipeline()
    if pipe is None:
        return {"score": None, "available": False}

    # Chunk into 512-token segments
    words = transcript.split()
    segments = []
    for i in range(0, len(words), 100):
        segment = " ".join(words[i:i + 100])
        if segment.strip():
            segments.append(segment[:512])

    if not segments:
        return {"score": None, "available": True}

    scores = []
    for segment in segments:
        try:
            result = pipe(segment)[0]
            score = result["score"] if result["label"] == "POSITIVE" else 1 - result["score"]
            scores.append(score)
        except Exception:
            continue

    avg_score = sum(scores) / len(scores) if scores else None
    return {
        "score": round(avg_score, 3) if avg_score is not None else None,
        "available": True,
        "num_segments": len(segments),
    }


# ---------------------------------------------------------------------------
# Combined analysis
# ---------------------------------------------------------------------------

def analyse_transcript(transcript: str, week_number: int) -> dict:
    """Run all NLP metrics on a single transcript."""
    if not transcript or not transcript.strip():
        return {
            "confidence": {"score": 0.0},
            "topic_alignment": {"score": 0.0, "is_on_topic": False},
            "specificity": {"score": 0.0},
            "sentiment": {"score": None},
            "word_count": 0,
            "warnings": ["No transcript available"],
        }

    confidence = measure_confidence(transcript)
    topic = measure_topic_alignment(transcript, week_number)
    specificity = measure_specificity(transcript)
    sentiment = measure_sentiment(transcript)

    warnings = []
    if confidence["score"] < 0.3:
        warnings.append("Low confidence language detected")
    if not topic["is_on_topic"]:
        warnings.append(f"Transcript may be off-topic for Week {week_number}")
    if specificity["score"] < 0.3:
        warnings.append("Lacking specific examples or data points")
    if sentiment["score"] is not None and sentiment["score"] < 0.3:
        warnings.append("Negative sentiment detected")

    return {
        "confidence": confidence,
        "topic_alignment": topic,
        "specificity": specificity,
        "sentiment": sentiment,
        "word_count": len(transcript.split()),
        "warnings": warnings,
    }
