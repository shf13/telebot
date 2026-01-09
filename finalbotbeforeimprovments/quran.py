import csv
import random
import os

class QuranProvider:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.ayahs = []
        self._load_data()

    def _load_data(self):
        if not os.path.exists(self.filepath):
            print(f"Warning: Quran CSV file not found at {self.filepath}")
            return

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                # Assuming CSV headers: ar, en, ru, ref
                # ref is optional (e.g., "Surah 2:255")
                reader = csv.DictReader(f)
                for row in reader:
                    self.ayahs.append(row)
        except Exception as e:
            print(f"Error loading Quran CSV: {e}")

    def get_random_ayah(self) -> dict | None:
        if not self.ayahs:
            return None
        return random.choice(self.ayahs)