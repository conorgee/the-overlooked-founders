"""
Shared embedding utility using sentence-transformers.
Singleton model — loads once, reused across requests.
Default: all-MiniLM-L6-v2 (384 dimensions).
Override with EMBEDDING_MODEL env var to use a fine-tuned model.
"""

import os

from sentence_transformers import SentenceTransformer

MODEL_PATH = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
_model = None


def _get_model():
    global _model
    if _model is None:
        mlflow_uri = os.environ.get("MLFLOW_MODEL_URI")
        if mlflow_uri:
            import mlflow.sentence_transformers
            _model = mlflow.sentence_transformers.load_model(mlflow_uri)
        else:
            _model = SentenceTransformer(MODEL_PATH)
    return _model


def get_embedding(text: str) -> list[float]:
    model = _get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()
