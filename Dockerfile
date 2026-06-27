FROM python:3.11-slim

WORKDIR /app

# Install cron tools
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Setup a cron job (e.g., Run daily at midnight)
RUN echo "0 0 * * * cd /app && python scripts/ingest_daily_games.py >> /var/log/cron.log 2>&1" > /etc/cron.d/scraper-cron
RUN chmod 0644 /etc/cron.d/scraper-cron
RUN crontab /etc/cron.d/scraper-cron

# Keep container alive and run cron
CMD ["cron", "-f"]
