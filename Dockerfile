FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# ffmpeg is REQUIRED for yt-dlp to extract audio
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    ffmpeg \
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
# We use shell form to allow variable expansion if needed, but array form is safer.
# Using python directly as uvicorn is imported in main block of server_user.py
CMD ["python", "server_fastapi.py"]
