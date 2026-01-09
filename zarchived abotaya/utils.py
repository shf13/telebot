# utils.py
import time
from formatter import load_latest

class DataLoader:
    def __init__(self, filepath):
        self.filepath = filepath
        self._cache = None
        self._last_loaded = 0
        self._cache_duration = 300  # Cache for 5 minutes (300 seconds)

    def get_data(self):
        """Returns the cached data, or reloads if cache is old."""
        now = time.time()
        # Reload if cache is empty OR cache expired
        if self._cache is None or (now - self._last_loaded > self._cache_duration):
            try:
                # print("DEBUG: Reloading data from disk...") 
                self._cache = load_latest(self.filepath)
                self._last_loaded = now
            except Exception as e:
                print(f"Error loading data: {e}")
                # If reload fails, return empty dict or old cache if available
                if self._cache is None:
                    return {}
        return self._cache