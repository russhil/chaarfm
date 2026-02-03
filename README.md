
## 🎵 Last.fm Universe Pipeline GUI

A standalone tool to extract your music universe from Last.fm, download songs, and vectorise them into a cloud database.

### Setup

1.  **Environment Variables**:
    Create a `.env` file in the project root with the following:
    ```env
    LASTFM_API_KEY=your_key
    LASTFM_API_SECRET=your_secret
    DATABASE_URL=postgres://user:pass@host:5432/db
    S3_ENDPOINT=https://your-account.r2.cloudflarestorage.com
    S3_ACCESS_KEY=your_access_key
    S3_SECRET_KEY=your_secret_key
    S3_BUCKET=your_bucket_name
    R2_PUBLIC_URL=https://pub-xxx.r2.dev
    ```

2.  **Run the GUI**:
    ```bash
    python -m music_pipeline.gui_app
    ```

### Workflow
1.  **Extract**: Enter Last.fm username to fetch top tracks and recommendations.
2.  **Select**: Choose how many random tracks ($N$) to process from the extracted universe.
3.  **Process**: The pipeline will:
    -   Download MP3s (yt-dlp)
    -   Tag metadata (mutagen)
    -   Vectorize audio (Essentia/MusicNN)
    -   Upload to R2 (Root directory)
    -   Store embeddings in Render Postgres (`vectors_{username}`)
