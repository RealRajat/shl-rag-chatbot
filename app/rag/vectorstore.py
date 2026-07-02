import os
import json
import logging
import faiss
import numpy as np
from typing import List, Dict, Any, Tuple
from app.rag.embedder import Embedder

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self, catalog_path: str = "catalog/catalog.json", index_path: str = "catalog/index.faiss"):
        self.catalog_path = catalog_path
        self.index_path = index_path
        self.embedder = Embedder()
        self.index = None
        self.catalog_data = []

    def load_catalog(self) -> List[Dict[str, Any]]:
        """
        Loads the catalog from the JSON file.
        """
        if not os.path.exists(self.catalog_path):
            logger.warning(f"Catalog file not found at {self.catalog_path}")
            return []
        
        with open(self.catalog_path, "r", encoding="utf-8") as f:
            self.catalog_data = json.load(f)
        return self.catalog_data

    def prepare_document_text(self, item: Dict[str, Any]) -> str:
        """
        Converts a catalog item into a descriptive text representation for embedding.
        """
        skills_str = ", ".join(item.get("skills", []))
        languages_str = ", ".join(item.get("languages", []))
        remote = "Yes" if item.get("remote_testing_support") else "No"
        adaptive = "Yes" if item.get("adaptive_support") else "No"
        
        return (
            f"Name: {item.get('name')}\n"
            f"Category: {item.get('category')}\n"
            f"Test Type: {item.get('test_type')}\n"
            f"Duration: {item.get('duration')}\n"
            f"Languages: {languages_str}\n"
            f"Remote Testing: {remote}\n"
            f"Adaptive Support: {adaptive}\n"
            f"Skills: {skills_str}\n"
            f"Description: {item.get('description')}"
        )

    def build_index(self):
        """
        Builds the FAISS index from scratch using the catalog data and saves it.
        """
        logger.info("Building FAISS index...")
        self.load_catalog()
        
        if not self.catalog_data:
            raise ValueError("Catalog is empty. Cannot build index.")
            
        doc_texts = [self.prepare_document_text(item) for item in self.catalog_data]
        embeddings = self.embedder.embed_documents(doc_texts)
        
        # Check embeddings dimension
        dimension = embeddings.shape[1]
        
        # Initialize L2 flat index
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings)
        
        # Save index locally
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        faiss.write_index(self.index, self.index_path)
        logger.info(f"FAISS index built and saved to {self.index_path}")

    def load_index(self):
        """
        Loads the FAISS index and catalog from disk.
        """
        self.load_catalog()
        
        if not os.path.exists(self.index_path):
            logger.info("Index file not found. Building index...")
            self.build_index()
        else:
            self.index = faiss.read_index(self.index_path)
            logger.info(f"Loaded FAISS index from {self.index_path}")

    def similarity_search(self, query: str, k: int = 10) -> List[Tuple[Dict[str, Any], float]]:
        """
        Performs similarity search against the index and returns matching catalog items with distances.
        """
        if self.index is None or not self.catalog_data:
            self.load_index()
            
        query_vector = self.embedder.embed_query(query)
        # Reshape to (1, dimension) for FAISS
        query_vector = np.expand_dims(query_vector, axis=0)
        
        # Determine actual k based on catalog size
        actual_k = min(k, len(self.catalog_data))
        if actual_k <= 0:
            return []
            
        distances, indices = self.index.search(query_vector, actual_k)
        
        results = []
        for idx, dist in zip(indices[0], distances[0]):
            if idx < 0 or idx >= len(self.catalog_data):
                continue
            results.append((self.catalog_data[idx], float(dist)))
            
        return results
