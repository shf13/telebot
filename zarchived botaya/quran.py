import csv
import random
from pathlib import Path
from typing import Optional
from html import escape


@dataclass
class Ayah:
    """Represents a single Quranic verse."""
    surah: str  # Surah name
    ayah_num: str  # Ayah number
    arabic: str
    english: Optional[str] = None
    russian: Optional[str] = None


class QuranManager:
    """Manages loading and retrieving Quranic verses from CSV."""
    
    def __init__(self, csv_file: str):
        self.csv_file = csv_file
        self.ayahs: list[Ayah] = []
        self._load_ayahs()
    
    def _load_ayahs(self):
        """Load ayahs from CSV file."""
        if not Path(self.csv_file).exists():
            print(f"Warning: Quran CSV file not found: {self.csv_file}")
            return
        
        try:
            with open(self.csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ayah = Ayah(
                        surah=row.get("surah", ""),
                        ayah_num=row.get("ayah_num", ""),
                        arabic=row.get("arabic", ""),
                        english=row.get("english"),
                        russian=row.get("russian"),
                    )
                    if ayah.arabic:  # Only add if has at least Arabic text
                        self.ayahs.append(ayah)
        except Exception as e:
            print(f"Error loading Quran CSV: {e}")
    
    def get_random_ayah(self) -> Optional[Ayah]:
        """Get a random ayah from the collection."""
        if not self.ayahs:
            return None
        return random.choice(self.ayahs)
    
    def format_ayah(self, ayah: Ayah, lang: str) -> str:
        """
        Format ayah for display based on language.
        - Arabic (ar): Arabic only
        - English (en): English + Arabic
        - Russian (ru): Russian + Arabic
        """
        if not ayah:
            return ""
        
        lines = []
        lines.append("")  # Blank line separator
        lines.append("<b>✨ Ayah of the Day ✨</b>")
        
        if lang == "ar":
            # Arabic only
            lines.append(f"<b>{escape(ayah.surah)} - {escape(ayah.ayah_num)}</b>")
            lines.append(f"<i>{escape(ayah.arabic)}</i>")
        
        elif lang == "en":
            # English + Arabic
            lines.append(f"<b>{escape(ayah.surah)} - {escape(ayah.ayah_num)}</b>")
            if ayah.english:
                lines.append(f"<i>{escape(ayah.english)}</i>")
            lines.append("")
            lines.append(f"<i>{escape(ayah.arabic)}</i>")
        
        elif lang == "ru":
            # Russian + Arabic
            lines.append(f"<b>{escape(ayah.surah)} - {escape(ayah.ayah_num)}</b>")
            if ayah.russian:
                lines.append(f"<i>{escape(ayah.russian)}</i>")
            lines.append("")
            lines.append(f"<i>{escape(ayah.arabic)}</i>")
        
        return "\n".join(lines)