FROM python:3.11-slim

WORKDIR /app

# Install cron
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Setup cron to execute the pipeline daily at 5:00 AM UTC (Midnight EST)
# Leaving the argument blank defaults the script to yesterday's date automatically
RUN echo "0 5 * * * cd /app && python scripts/run_daily_pipeline.py >> /var/log/cron.log 2>&1" > /etc/cron.d/scraper-cron
RUN chmod 0644 /etc/cron.d/scraper-cron
RUN crontab /etc/cron.d/scraper-cron

CMD ["cron", "-f"]
