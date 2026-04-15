"""
Shared feature engineering for application scoring.
Extracts text statistics, domain indicators, stage features, and semantic features.
"""

import re

import numpy as np

from lib.embeddings import get_embedding

INDICATOR_PATTERNS = {
    "problem_mention": r"(problem|pain point|challenge|struggle|need|frustrat)",
    "customer_mention": r"(customer|user|client|audience|market|buyer|people who)",
    "revenue_mention": r"(revenue|price|charge|subscription|pay|monetiz|fee|SaaS)",
    "validation_mention": r"(interview|survey|test|feedback|talked to|validated|research)",
    "competition_mention": r"(competitor|alternative|existing|currently use|market gap)",
    "metric_mention": r"(conversion|retention|churn|growth|CAC|LTV|MRR|ARR)",
    "traction_mention": r"(users|customers|revenue|sales|signed up|waitlist|pilot)",
}

STAGE_ORDER = {"idea": 0, "mvp": 1, "launched": 2, "growing": 3}

RUBRIC_ANCHORS = {
    "strong": (
        "A clear, specific problem affecting an identifiable customer segment, "
        "validated through customer interviews, with a viable revenue model "
        "and early traction or a concrete plan to acquire first customers."
    ),
    "weak": (
        "A vague idea without a specific customer, no validation, "
        "no understanding of the market or how to make money."
    ),
}

_anchor_embeddings = {}


def _get_anchor_embedding(level: str) -> list[float]:
    if level not in _anchor_embeddings:
        _anchor_embeddings[level] = get_embedding(RUBRIC_ANCHORS[level])
    return _anchor_embeddings[level]


def cosine_similarity(a, b) -> float:
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def extract_features(application: dict) -> dict:
    idea = application.get("business_idea", "") or ""
    words = idea.split()
    sentences = [s.strip() for s in re.split(r"[.!?]+", idea) if s.strip()]

    features = {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "avg_sentence_length": np.mean([len(s.split()) for s in sentences]) if sentences else 0,
        "vocabulary_richness": len(set(w.lower() for w in words)) / max(len(words), 1),
        "has_numbers": int(bool(re.search(r"\d+", idea))),
        "number_count": len(re.findall(r"\d+", idea)),
    }

    for name, pattern in INDICATOR_PATTERNS.items():
        features[f"has_{name}"] = int(bool(re.search(pattern, idea, re.I)))

    features["stage_ordinal"] = STAGE_ORDER.get(application.get("stage", ""), 0)
    features["has_video"] = int(bool(application.get("video_pitch_url")))

    if idea.strip():
        idea_emb = get_embedding(idea)
        for level in RUBRIC_ANCHORS:
            anchor_emb = _get_anchor_embedding(level)
            features[f"sim_to_{level}"] = cosine_similarity(idea_emb, anchor_emb)
        features["rubric_spread"] = features["sim_to_strong"] - features["sim_to_weak"]
    else:
        features["sim_to_strong"] = 0.0
        features["sim_to_weak"] = 0.0
        features["rubric_spread"] = 0.0

    return features


FEATURE_NAMES = [
    "word_count", "sentence_count", "avg_sentence_length", "vocabulary_richness",
    "has_numbers", "number_count",
    "has_problem_mention", "has_customer_mention", "has_revenue_mention",
    "has_validation_mention", "has_competition_mention", "has_metric_mention",
    "has_traction_mention",
    "stage_ordinal", "has_video",
    "sim_to_strong", "sim_to_weak", "rubric_spread",
]
