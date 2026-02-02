# Music Pipeline

This pipeline extracts a music universe from Last.fm, downloads songs, vectorizes them, and stores them in Cloudflare R2 and a Postgres Vector DB.

## Setup

1.  Install dependencies:
    ```bash
    pip install -r music_pipeline/requirements.txt
    pip install musicnn --no-deps
    ```
2.  Ensure `.env` has all credentials.

## Usage

Run the pipeline for a username:

```bash
python -m music_pipeline.main russhil --limit 2
```

(Use a small limit for testing first)
