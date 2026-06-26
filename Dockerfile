# Use a lightweight, official Python runtime
FROM python:3.11-slim

# Install system dependencies required for building psycopg2 (Postgres client)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/apt-cache/*

# Set the working directory inside the container
WORKDIR /app

# Copy and install Python dependencies first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# Set Python path to ensure internal directory module imports function correctly
ENV PYTHONPATH=/app

# Command executed when the Railway Cron triggers
CMD ["python", "src/pipeline.py"]
