FROM python:3.10-slim

# Ensure output is not buffered
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies (needed for psycopg2 and numpy sometimes)
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

# Command to run the application using uvicorn directly
# This avoids issues with python signal handling and is production standard
# Shell form allows variable expansion for PORT
CMD ["sh", "-c", "uvicorn server_user:app --host 0.0.0.0 --port ${PORT:-5001}"]
