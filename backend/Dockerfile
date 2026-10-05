# ফাইল: backend/Dockerfile
# এই ফাইলটি Django backend-এর Docker image তৈরির জন্য ব্যবহৃত।

FROM python:3.11-slim

# System dependencies install করা
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Working directory সেট করা
WORKDIR /app

# Python dependencies আগে install করা (cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Project files copy করা
COPY . .

# Logs directory তৈরি করা
RUN mkdir -p logs media static

# Port expose করা
EXPOSE 8000

# Non-root user তৈরি করা (security best practice)
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser
