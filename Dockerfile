FROM python:3.11-slim

WORKDIR /app

# Install any basic system requirements your scrapers need
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# We leave CMD blank because Railway will dictate the command via its UI dashboard!
