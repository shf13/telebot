import os
from datetime import datetime, date
import scrapy


class PrayerTimesSpider(scrapy.Spider):
    name = "prayer_times"

    custom_settings = {
        # ensure Cyrillic exports correctly
        "FEED_EXPORT_ENCODING": "utf-8",
        # be polite; tune as needed
        "DOWNLOAD_DELAY": 0.5,
        "USER_AGENT": "Mozilla/5.0 (compatible; PrayerTimesBot/1.0)",
    }

    start_urls = [
        "https://mihrab.ru",
        # add more URLs here
    ]
    
    def parse(self, response):
        prayers = {}

        for li in response.css("ul.modiptultimer li.modiptprayer"):
            # text()[1] = the text node before <span>
            name = li.xpath("normalize-space(text()[1])").get() or ""
            time_str = li.css("span::text").get() or ""

            name = name.strip()
            time_str = time_str.strip()

            if name and time_str:
                prayers[name] = time_str

        yield {
            "date": date.today().isoformat(),
            "scraped_at": datetime.utcnow().isoformat() + "Z",
            "source_url": response.url,
            "prayers": prayers,
        }