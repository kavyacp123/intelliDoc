from __future__ import annotations

import logging
from typing import Iterable, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    np = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None


class EmbeddingService:
    def __init__(self) -> None:
        self._model: Optional[SentenceTransformer] = None

    def is_available(self) -> bool:
        return SentenceTransformer is not None and np is not None

    def embed(self, texts: Iterable[str]) -> List[List[float]]:
        if not self.is_available():
            raise RuntimeError("Embedding dependencies are not installed.")

        model = self._get_model()
        vectors = model.encode(list(texts), normalize_embeddings=True)
        return vectors.tolist()

    def serialize(self, vector: List[float]) -> bytes:
        if np is None:
            raise RuntimeError("NumPy is required to serialize embeddings.")
        return np.asarray(vector, dtype="float32").tobytes()

    def deserialize(self, raw: bytes) -> List[float]:
        if np is None:
            raise RuntimeError("NumPy is required to deserialize embeddings.")
        return np.frombuffer(raw, dtype="float32").tolist()

    def dimension(self) -> int:
        if not self.is_available():
            raise RuntimeError("Embedding dependencies are not installed.")
        return int(self._get_model().get_sentence_embedding_dimension())

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            if SentenceTransformer is None:
                raise RuntimeError("sentence-transformers is not installed.")
            logger.info("Loading embedding model: %s", settings.EMBEDDING_MODEL_NAME)
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        return self._model


embedding_service = EmbeddingService()
