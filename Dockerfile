FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# Removed ffmpeg as server no longer processes audio
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port (defaults to 5001, but cloud overrides via PORT env var)
EXPOSE 5001

# Command to run the application
CMD ["python", "server_fastapi.py"]
