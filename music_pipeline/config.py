import os
from dotenv import load_dotenv

load_dotenv()

# Last.fm
LASTFM_API_KEY = "f3d0dfdb4bb8c0fbe7e41400c6ff979e"
LASTFM_API_SECRET = "072547e52c6e1f3b890b9af5a10103e8"

# Database
DATABASE_URL = os.getenv("DATABASE_URL")

# Cloudflare R2
S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "") # Optional public domain

# Validation
if not all([DATABASE_URL, S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET]):
    print("Warning: Some environment variables are missing. Check .env file.")
