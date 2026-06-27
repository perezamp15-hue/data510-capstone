FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Force Python to recognize the root directory as an import source
ENV PYTHONPATH=/app

CMD ["python", "scripts/run_daily_pipeline.py"]
