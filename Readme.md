- Add the scarpy command to crontab 
1. `crontab -e`
2. add `20 0 * * * cd /home/sherif/bottele/scraper && /home/sherif/bottele/boot/bin/python -m scrapy crawl prayer_times -O /home/sherif/bottele/data/latest.json >> /home/sherif/bottele/logs/scrape.log 2>&1`
3. add also `35 0 * * * cd /home/sherif/bottele/scraper && /home/sherif/bottele/boot/bin/python -m scrapy crawl prayer_times -O /home/sherif/bottele/data/latest.json >> /home/sherif/bottele/logs/scrape.log 2>&1`

- Create a service for systemd 
1. `sudo vim /etc/systemd/system/prayerbot.service`
2. add
```bash
[Unit]
Description=Prayer Times Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/WorkingDirectory/bot
Environment=PYTHONUNBUFFERED=1
ExecStart=/PATH/TO/.venv/bin/python /PATH/TO/BOT/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```