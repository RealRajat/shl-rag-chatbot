import json
import os
import logging
from typing import List, Dict, Any
from app.models.schemas import Recommendation

logger = logging.getLogger(__name__)

class RecommendationService:
    def __init__(self, catalog_path: str = "catalog/catalog.json"):
        self.catalog_path = catalog_path
        self._catalog_map = None

    def _load_catalog(self) -> Dict[str, Dict[str, Any]]:
        """
        Loads the catalog and builds a case-insensitive name-to-item mapping.
        """
        if self._catalog_map is not None:
            return self._catalog_map

        if not os.path.exists(self.catalog_path):
            logger.error(f"Catalog file not found at {self.catalog_path} for recommendation verification.")
            return {}

        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                catalog_data = json.load(f)
            
            # Map by normalized names
            self._catalog_map = {
                item["name"].strip().lower(): item 
                for item in catalog_data
            }
            logger.info(f"Loaded {len(self._catalog_map)} items into validation map.")
        except Exception as e:
            logger.error(f"Failed to load catalog for verification: {e}")
            self._catalog_map = {}

        return self._catalog_map

    def validate_recommendations(self, raw_recommendations: List[Dict[str, Any]]) -> List[Recommendation]:
        """
        Verifies LLM recommendations against catalog.json.
        Only items present in the official catalog are returned, with official names/URLs/types.
        """
        catalog_map = self._load_catalog()
        valid_recs = []

        for rec in raw_recommendations:
            name = rec.get("name", "").strip()
            normalized_name = name.lower()
            
            # Try exact match or partial/contained match as a fallback
            matched_item = None
            if normalized_name in catalog_map:
                matched_item = catalog_map[normalized_name]
            else:
                # Fuzzy fallback: check if the catalog name contains the recommended name or vice-versa
                for cat_name, item in catalog_map.items():
                    if normalized_name in cat_name or cat_name in normalized_name:
                        matched_item = item
                        logger.info(f"Fuzzy matched '{name}' to official catalog item '{item['name']}'")
                        break

            if matched_item:
                valid_recs.append(
                    Recommendation(
                        name=matched_item["name"],
                        url=matched_item["url"],
                        test_type=matched_item["test_type"]
                    )
                )
            else:
                logger.warning(f"Discarding hallucinated or unknown recommendation: '{name}'")

        return valid_recs
