# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Key commands

### Environment & dependencies
- Install core Python dependencies (Python 3.9+):
  - `pip install -r requirements.txt`
- Install the standalone Last.fm + YouTube pipeline dependencies:
  - `pip install -r music_pipeline/requirements.txt`
  - `pip install musicnn --no-deps`
- Configure environment via `.env` in the project root (used by Supabase/Postgres, Last.fm, and Cloudflare R2/S3). At minimum, the README-based flow expects:
  - `LASTFM_API_KEY`, `LASTFM_API_SECRET`
  - `DATABASE_URL` (Postgres/pgvector, typically Supabase)
  - `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`
  - `R2_PUBLIC_URL` for public audio URLs when hosting in the cloud

### Core apps & dashboards
- **User-facing recommender + player (FastAPI, multi-user, Supabase-backed)**:
  - `python3 server_user.py`
  - Default port: `5001` (overridable with `PORT`). Main pages: `/` (landing), `/login`, `/player`, `/ingest` (remote ingestion UI), `/admin` (when called with a valid admin session).
- **Admin analytics dashboard (FastAPI, Supabase Postgres analytics)**:
  - `python3 server_admin.py`
  - Default port: `5002`, dashboard at `/admin`.
- **Supabase vectorization pipeline dashboard (monitor/control bulk embedding)**:
  - `python3 pipeline_server.py`
  - Default port: `5005`.
- **GUI: Last.fm → YouTube → R2 + vectors (standalone universe builder)**:
  - `python -m music_pipeline.gui_app`
  - This is the primary entrypoint described in `README.md` for end-to-end Last.fm ingestion.

### Vectorization & ingestion pipelines
There are two related but distinct embedding flows: the newer **music_pipeline** universe builder and the older **Supabase/vecs MP3 pipeline**. They both ultimately populate Postgres/pgvector tables but have different entrypoints.

- **Last.fm universe pipeline (music_pipeline)**:
  - CLI pipeline run for a specific Last.fm user:
    - `python -m music_pipeline.main <lastfm_username> --limit 2`
  - Typical workflow (from README):
    1. Extract tracks from Last.fm for a username.
    2. Download MP3s from YouTube (yt-dlp).
    3. Tag metadata and prepare files.
    4. Vectorize audio with Essentia/MusicNN.
    5. Upload MP3s to R2 under a root directory.
    6. Store embeddings in Postgres (`vectors_{username}` tables).
  - For interactive control and monitoring, use the GUI:
    - `python -m music_pipeline.gui_app`

- **Supabase/vecs MP3 pipeline (local folders → pgvector)**:
  - One-off full re-vectorization with parallel workers from local folders defined in `chaarfm_config.json`:
    - `python3 pipeline_vectorize.py --recreate --workers 6`
  - Dry run to inspect which files would be processed:
    - `python3 pipeline_vectorize.py --dry-run`
  - GUI-assisted folder + DB selection (when not using preconfigured `chaarfm_config.json`):
    - `python3 pipeline_vectorize.py --gui`
  - Important flags (see `pipeline_vectorize.py`): `--workers`, `--batch-size`, `--store-path`, `--chunk-size`, `--recreate`.

### Tests
There is no single unified test runner; tests are Python scripts and modules that can be invoked directly.

- **Core recommender/bandit logic sanity check (no DB required)**:
  - `python3 test_logic.py`
- **Admin API & DB wiring smoke test** (requires `server_admin.py` running on port 5002 with a live DB):
  - In one terminal: `python3 server_admin.py`
  - In another: `python3 test_admin.py`
- **Spotify tooling tests** (under `spotify_tool/` — require appropriate Spotify credentials and redirect URIs):
  - From project root, e.g.: `python3 spotify_tool/test_login.py`
- **GUI & vectorization tests**:
  - `python3 test_musicnn.py` – validates MusicNN integration.
  - `python3 test_vectorization.py` – checks vectorization pipeline behavior.
  - `python3 tests/test_gui_logic.py` – tests GUI behavior for the desktop tooling.

## Architecture overview

### High-level system
This repository combines two closely related domains:
- A **multi-user personalized streaming/recommendation stack** (ChaarFM) built on Supabase/Postgres + pgvector and Cloudflare R2 storage.
- A **Last.fm + YouTube “music universe” builder** (`music_pipeline/`) that populates the vector DB and object storage using a richer ETL pipeline.

The core flow is:
1. Extract a user’s “universe” (Last.fm + Spotify-like data, YouTube downloads, tagging).
2. Vectorize audio tracks into MusiCNN embeddings and push into Postgres/pgvector.
3. Serve recommendations and playback via `server_user.py`, with per-user bandit and cluster logic (`user_recommender.py`) and admin analytics (`server_admin.py`, `user_db.py`).

### Configuration, environment, and collection layout
- `config_manager.py` governs all **local music folder** and **collection name** mappings used by the Supabase/vecs pipeline:
  - `chaarfm_config.json` maps short source names (e.g. `"russhil"`) to absolute folders and collection names (`music_<source>`), plus combined/`_p03` variants.
  - `.env` holds **cloud credentials and DB URLs**; `load_env_vars()` loads them at startup for both the pipelines and the servers.
  - `configure_interactive()` launches a Tk GUI to add/remove folders and configure Supabase (`DATABASE_URL`) and R2/S3 credentials on disk.
- Supabase/Postgres is the **authoritative store** for:
  - Vectors and per-track metadata (e.g. `vecs."collection_name"` and/or `vectors_{username}` tables for the Last.fm pipeline).
  - User interaction logs (`user_logs` and related tables managed via `user_db.py`).
  - Aggregated cluster affinity and history statistics (`cluster_affinity`, etc.), which are used to warm-start bandit priors.
- Cloudflare R2 (or a compatible S3 endpoint) is used as the **canonical audio store** in cloud deployments:
  - `R2_PUBLIC_URL` and `S3_*` env vars determine where uploaded MP3s live.
  - Playback servers (`server_user.py`) prefer redirecting to R2 URLs when configured, falling back to local `MUSIC_ROOT` when running on a laptop.

### Embedding & ingestion layer
There are two main embedding paths that share the underlying MusiCNN-based extraction but differ in orchestration and targets.

- **Legacy/core MP3 → pgvector pipeline (`pipeline_vectorize.py` + `pipeline_server.py`)**:
  - `pipeline_vectorize.py`:
    - Uses `config_manager.load_config()` to discover `FOLDERS` and `COLLECTIONS`.
    - Spawns a multiprocessing pool; each worker initializes `MusicNNExtractor` in `init_worker()` and extracts `average_vector` for each audio file.
    - Writes idempotent state to `vectorize_state.db` via `StateManager`, allowing re-runs that skip unchanged files unless `--recreate` is provided.
    - Pushes results into an `AsyncSupabaseUploader` thread which:
      - Batches by collection (`music_<source>` + global `music_combined`).
      - Upserts via `vecs` client, attaching metadata such as filename and source (and optionally full file path).
  - `pipeline_server.py` wraps this logic in a FastAPI **monitoring UI**:
    - Tracks `pipeline_state` (status, per-folder progress, ETA, logs).
    - Serves an inline HTML/JS dashboard at `/` with an SSE stream (`/api/progress`) and `POST /api/start` / `POST /api/stop` controls.

- **`music_pipeline/` universe builder (Last.fm + YouTube → R2 + Postgres)**:
  - `music_pipeline/main.py` and `music_pipeline/gui_app.py` orchestrate a richer pipeline:
    - Uses Last.fm API (`pylast` + `LASTFM_*` keys) to build a “universe” of tracks per user.
    - Downloads audio via YouTube (yt-dlp) in `downloader.py`.
    - Normalizes and tags metadata in `tagger.py`.
    - Vectorizes with MusiCNN in `vectorizer.py`, producing track-level embeddings.
    - Uploads MP3s to R2 via `storage.py` and writes embeddings to Postgres (e.g. `vectors_<username>`).
  - `music_pipeline/web_app.py` exposes an ingestion **coordinator** (see below) that allows remote workers and the main UI to talk via websockets.

### Vector stores & persistence
- `vector_db.py` encapsulates the **legacy Qdrant** vector store for backwards compatibility (used primarily by older paths such as `recommender.RecommenderSession`, `server_fastapi.py`, and `server.py`). It provides:
  - Client creation and collection initialization.
  - Convenience search helpers like `get_random_tracks`, `recommend_tracks`, `get_track_by_id` operating over 200-D MusiCNN embeddings.
- `user_db.py` is the **central relational layer** for the Supabase/Postgres side:
  - `init_db()` initializes tables and SQLAlchemy engine.
  - `verify_user()`, `log_interaction_db()`, `get_admin_stats()`, `get_history_stats()`, `clear_user_history()`, and `get_logs()` implement auth, logging, and analytics.
  - Exposes helpers that `UserRecommender` and admin APIs depend on for cluster affinity, per-user history, and building high-level views.

### Recommendation engines
- **Legacy Qdrant-based recommender (`recommender.RecommenderSession`)**:
  - Used in `server_fastapi.py` and `server.py` for earlier single-user prototypes.
  - Pulls from Qdrant via `vector_db.get_client()` and clusters the embeddings with `clustering.ClusterManager`.
  - Maintains `user_vector`, `liked_vectors`, `disliked_vectors`, and a Beta-bandit `cluster_scores` map.
  - Implements micro-interaction-based adaptation (skip vs partial vs full listen) and outlier-aware cluster probing.

- **Supabase-native multi-user recommender (`user_recommender.UserRecommender`)**:
  - Primary engine used by `server_user.py`.
  - Loads track vectors and metadata from Postgres (`vecs."collection_name"` for ChaarFM collections or `vectors_<username>` tables for universe-specific collections) into an in-memory `track_map`.
  - Builds an internal `ClusterManager` (KMeans) with a relatively high number of clusters (e.g. 50) to capture fine-grained “vibes”.
  - Tracks per-session state:
    - `user_vector` (RL-updated taste vector),
    - Streaks, boredom, exploration drift,
    - Session-local likes/dislikes and historical likes/dislikes from `user_logs` and `cluster_affinity`.
  - Provides higher-level operations that power the API:
    - `get_next_track()` / `get_next_batch()` – choose next song(s) based on bandit + cluster + drift logic.
    - `record_feedback()` – interpret play duration and explicit like/dislike into bandit updates, RL vector updates, and cluster drift.
    - `search()` – map textual queries to nearby tracks using the in-memory map.
    - `set_seed()` – reseed the session around an explicit track and rebuild the batch queue.

### API layers, ingestion control, and UIs
- **`server_user.py` – main user/API server**:
  - Exposes a FastAPI `app` and wires in:
    - Supabase DB layer (`user_db.init_db()`),
    - `UserRecommender` for per-session recommendation logic,
    - `music_pipeline.web_app.coordinator` for distributed ingestion.
  - Adds `SessionMiddleware` for cookie-based login and configures Google OAuth via `authlib` for authentication.
  - Maintains an in-memory `sessions` dict keyed by `session_id` → {`user_id`, `recommender`, `queue`, `music_root`, `youtube_mode`}.
  - Key endpoints:
    - `/` / `/v2` / `/v3` – various landing pages rendered from `templates/`.
    - `/ingest` – front-end UI for orchestrating remote ingestion runs.
    - `/ws/remote/{code}/{client_type}` – websocket endpoint used by `music_pipeline.web_app.coordinator` to connect UI and worker processes for a given ingestion job.
    - `/api/login` / OAuth-related flows (not fully shown here) – authenticate users and create sessions.
    - `/api/next`, `/api/feedback`, `/api/search`, `/api/select` – drive the recommendation loop via `UserRecommender` and manage the per-session batch queue.
    - `/stream/{filename}` – stream tracks either via R2 redirect (`R2_PUBLIC_URL`) or local filesystem lookups using `MUSIC_ROOT`/collection-specific roots.
    - `/api/profile`, `/api/history-stats`, `/api/clear-history`, `/api/logout` – surface profile and history operations backed by `user_db`.

- **`server_admin.py` – standalone admin analytics server**:
  - Exposes `/admin` plus JSON APIs under `/api/admin/*` that query Supabase/Postgres for:
    - Global and per-user aggregate stats (plays, average duration, skip rates).
    - Recent `user_logs` entries.
    - A simple LLM-backed admin chat endpoint (currently mocked in this repo) to summarize behavior.

- **Legacy servers (`server_fastapi.py`, `server.py`, `server_batch.py`, `server_fastapi` variants)**:
  - Provide older experimental UIs for playback and recommendations directly off local files and Qdrant.
  - Still useful for debugging low-level behavior but secondary to `server_user.py` in current architecture.

- **Desktop/control GUIs**:
  - `control_panel.py` – Tk control panel for starting `server_user.py`, `pipeline_server.py`, configuring folders (`config_manager.py`), and optionally running `ngrok` tunnels on macOS.
  - `music_pipeline/gui_app.py` – dedicated GUI for the Last.fm universe pipeline that wraps the CLI and coordinates R2 + DB writes.

### Tests and diagnostics
- `test_logic.py` – focused on `UserRecommender` bandit logic (lock-in, boredom handling, drift) with mocked `user_db` and synthetic vectors.
- `test_admin.py` – smoke test for the admin HTTP surface against a running `server_admin.py` instance.
- `test_musicnn.py`, `test_vectorization.py`, `test_render_connection.py` – verify MusicNN behavior, vectorization correctness, and connectivity to Render/Supabase environments.
- `tests/test_gui_logic.py` – asserts basic GUI flows for the desktop control apps.
- Additional `debug_*.py` scripts (`debug_qdrant.py`, `debug_models.py`, `debug_essentia.py`, `debug_recommender.py`, `debug_db.py`, `inspect_schema.py`, etc.) are intended for interactive debugging of individual subsystems (models, DB, Qdrant, pipelines) and should be run directly when needed.
