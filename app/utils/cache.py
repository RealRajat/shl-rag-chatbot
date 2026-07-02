import time
from typing import Dict, Any, Optional

class MemoryCache:
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieves a value from cache if it exists and has not expired.
        """
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        if time.time() - entry["timestamp"] > self.ttl_seconds:
            # Expired
            del self.cache[key]
            return None
            
        return entry["value"]

    def set(self, key: str, value: Any):
        """
        Stores a value in the cache with the current timestamp.
        """
        self.cache[key] = {
            "value": value,
            "timestamp": time.time()
        }

    def clear(self):
        """
        Clears all items in the cache.
        """
        self.cache.clear()
