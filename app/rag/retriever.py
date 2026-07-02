import logging
from typing import List, Dict, Any
from app.rag.vectorstore import VectorStore

logger = logging.getLogger(__name__)

class Retriever:
    def __init__(self, vectorstore: VectorStore = None):
        self.vectorstore = vectorstore or VectorStore()

    def retrieve(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieves the top k catalog items most relevant to the query.
        """
        logger.info(f"Retrieving top {k} items for query: '{query}'")
        search_results = self.vectorstore.similarity_search(query, k=k)
        
        # Extract only the catalog items
        items = [item for item, dist in search_results]
        return items

    def retrieve_formatted_context(self, query: str, k: int = 10) -> str:
        """
        Retrieves the top k items and formats them as a clean text context block for LLM prompts.
        """
        items = self.retrieve(query, k=k)
        if not items:
            return "No matching assessments found in catalog."
            
        formatted_items = []
        for i, item in enumerate(items, 1):
            skills_str = ", ".join(item.get("skills", []))
            languages_str = ", ".join(item.get("languages", []))
            remote = "Yes" if item.get("remote_testing_support") else "No"
            adaptive = "Yes" if item.get("adaptive_support") else "No"
            
            formatted_item = (
                f"[{i}] Name: {item.get('name')}\n"
                f"Category: {item.get('category')}\n"
                f"Test Type: {item.get('test_type')}\n"
                f"Duration: {item.get('duration')}\n"
                f"Languages: {languages_str}\n"
                f"Remote Testing Support: {remote}\n"
                f"Adaptive Support: {adaptive}\n"
                f"Skills Evaluated: {skills_str}\n"
                f"Description: {item.get('description')}\n"
                f"URL: {item.get('url')}\n"
            )
            formatted_items.append(formatted_item)
            
        return "\n---\n".join(formatted_items)
