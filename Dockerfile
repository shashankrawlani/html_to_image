# Use Alpine Linux as the base image for a lightweight container
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies for wkhtmltopdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    wkhtmltopdf \
    fontconfig \
    libfreetype6 \
    fonts-dejavu \
    fonts-liberation \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy only the requirements file first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY app/app.py .

# Create static directory for storing images
RUN mkdir -p static && chmod 777 static

# Set environment variables
ENV HOST_IMAGES=1
ENV MAX_DOWNLOADS=5
ENV IMAGE_EXPIRY_DAYS=3
ENV API_TOKEN="DaduBhogLagaRaheHai"
ENV ROOT_PATH="/html_to_image"
ENV BASE_URL="https://tools.automationtester.in"

# Expose the port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
