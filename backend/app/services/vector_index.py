from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Sequence

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import faiss
except Exception:  # pragma: no cover - optional dependency
    faiss = None

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    np = None


class KnowledgeVectorIndex:
    def __init__(self) -> None:
        self.index = None
        self.records: List[dict] = []
        self.dimension: int | None = None

    def is_available(self) -> bool:
        return faiss is not None and np is not None

    def build(self, vectors: Sequence[Sequence[float]], records: List[dict]) -> None:
        if not self.is_available():
            raise RuntimeError("FAISS dependencies are not installed.")
        if not vectors:
            self.index = None
            self.records = []
            self.dimension = None
            return

        matrix = np.asarray(vectors, dtype="float32")
        self.dimension = int(matrix.shape[1])
        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(matrix)
        self.records = list(records)

    def search(self, query_vector: Sequence[float], k: int = 5) -> List[dict]:
        if self.index is None or not self.records or np is None:
            return []
        query = np.asarray([query_vector], dtype="float32")
        distances, indices = self.index.search(query, min(k, len(self.records)))
        results = []
        for score, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.records):
                continue
            row = dict(self.records[idx])
            row["confidence"] = float(score)
            results.append(row)
        return results

    def save(self) -> None:
        if not self.is_available() or self.index is None or faiss is None:
            return
        path = Path(settings.VECTOR_INDEX_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(path))


vector_index = KnowledgeVectorIndex()
