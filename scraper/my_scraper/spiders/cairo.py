import scrapy
from datetime import datetime

class PrayerTimesSpider(scrapy.Spider):
    name = "cairo"
    
    custom_settings = {
        "FEED_EXPORT_ENCODING": "utf-8",
        "DOWNLOAD_DELAY": 0.5,
        "USER_AGENT": "Mozilla/5.0 (compatible; PrayerTimesBot/1.0)",
    }

    start_urls = [
        "https://www.dar-alifta.org/ar/prayer",  # replace with your actual URL
        # add more URLs here
    ]

    def parse(self, response):
        # Extract prayer times data
        prayers = {}

        # Find the rows of the table containing the prayer times
        rows = response.css("table.prayer-timings-table tbody tr")
        
        for row in rows:
            # Extract the day
            day = row.css("td::text").get().strip()
            
            # Extract the prayer times (remove extra spaces and handle cases where time might not be present)
            fajr = row.css("td#fajr::text").get() or ""
            shurooq = row.css("td#shurooq::text").get() or ""
            dhuhr = row.css("td#dhuhr::text").get() or ""
            asr = row.css("td#asr::text").get() or ""
            maghrib = row.css("td#maghrib::text").get() or ""
            isha = row.css("td#isha::text").get() or ""

            prayers[day] = {
                "fajr": fajr.strip(),
                "shurooq": shurooq.strip(),
                "dhuhr": dhuhr.strip(),
                "asr": asr.strip(),
                "maghrib": maghrib.strip(),
                "isha": isha.strip(),
            }

        # Yield the scraped data
        yield {
            "scraped_at": datetime.utcnow().isoformat() + "Z",
            "source_url": response.url,
            "prayers": prayers,
        }
