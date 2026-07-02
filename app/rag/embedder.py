import numpy as np
from typing import List, Union
import logging

logger = logging.getLogger(__name__)

class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            logger.info(f"Loading SentenceTransformer model: {self.model_name}...")
            # Inline import to prevent loading on module load
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            logger.info("SentenceTransformer model loaded successfully.")
        return self._model

    def embed_query(self, text: str) -> np.ndarray:
        """
        Embeds a single query string.
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return np.array(embedding, dtype=np.float32)

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        """
        Embeds a list of document strings.
        """
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return np.array(embeddings, dtype=np.float32)
