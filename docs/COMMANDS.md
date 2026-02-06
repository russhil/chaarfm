# ChaarFM Commands Reference

Quick reference for all common ChaarFM commands and operations.

## Table of Contents
- [Setup & Installation](#setup--installation)
- [Running Services](#running-services)
- [Building Executables](#building-executables)
- [Database Operations](#database-operations)
- [Debug & Testing](#debug--testing)
- [Worker Management](#worker-management)

---

## Setup & Installation

### Complete Setup (One Command)

```bash
# macOS with Python 3.10
python3.10 -m venv venv && \
source venv/bin/activate && \
pip install --upgrade pip && \
pip install -r requirements.txt
```

### Setup with Essentia Fix

```bash
./INSTALL_WITH_ESSENTIA_FIX.sh
```

### Setup and Run

```bash
./setup_and_run.sh
```

---

## Running Services

### Main Server

```bash
python server.py
```

### User Server

```bash
python server_user.py
```

### Admin Server

```bash
python server_admin.py
```

### Batch Server

```bash
python server_batch.py
```

### FastAPI Server

```bash
python server_fastapi.py
```

### Pipeline Server

```bash
python pipeline_server.py
```

### Control Panel (GUI)

```bash
python control_panel.py
# Or double-click:
./ChaarFM_Control_Panel.command
```

### Worker Launcher

```bash
python worker_launcher.py
```

---

## Building Executables

### Build Worker (macOS)

```bash
./build_worker_macos.sh
```

### Build Worker (Windows)

```batch
build_worker_windows.bat
```

### Build Worker (Offline)

```bash
./build_worker_offline.sh
```

### Build with Existing Environment

```bash
./build_with_existing_env.sh
```

### Build One-File Executable (No Sudo)

```bash
./build_onefile_nosudo.sh
```

### Build with Fixed Cache

```bash
python build_with_fixed_cache.py build_worker.spec
```

---

## Database Operations

### Run Migrations

```bash
# Add youtube_id column
python scripts/db_migrations.py add-youtube-col

# Fix schema
python scripts/db_migrations.py fix-schema

# Fix constraints
python scripts/db_migrations.py fix-constraints

# Migrate from Qdrant to Supabase
python scripts/db_migrations.py migrate-qdrant

# Create averaged collection
python scripts/db_migrations.py migrate-averaged

# Migrate users from SQLite
python scripts/db_migrations.py migrate-users
```

### Database Utilities

```bash
# Initialize database
python user_db.py

# Inspect schema
python scripts/debug_tools.py db-schema

# Inspect constraints
python scripts/debug_tools.py db-constraints
```

---

## Debug & Testing

### Run All Diagnostics

```bash
python scripts/debug_tools.py all
```

### Individual Checks

```bash
# Check Essentia installation
python scripts/debug_tools.py essentia

# Check MusicNN
python scripts/debug_tools.py musicnn

# Check Tkinter GUI
python scripts/debug_tools.py tkinter

# Check Qdrant models
python scripts/debug_tools.py qdrant

# Inspect database schema
python scripts/debug_tools.py db-schema

# Inspect database constraints
python scripts/debug_tools.py db-constraints

# Test recommender system
python scripts/debug_tools.py recommender

# Test S3/R2 connection
python scripts/debug_tools.py s3

# Test vectorization
python scripts/debug_tools.py vectorization

# Test database logging
python scripts/debug_tools.py db-log
```

---

## Worker Management

### Start Remote Worker

```bash
python remote_worker.py --url https://chaarfm.onrender.com --code YOUR_CODE
```

### Start Multiple Workers (Same Machine)

```bash
# Terminal 1
python remote_worker.py --url https://chaarfm.onrender.com --code ABC123

# Terminal 2
python remote_worker.py --url https://chaarfm.onrender.com --code ABC123

# Terminal 3
python remote_worker.py --url https://chaarfm.onrender.com --code ABC123
```

### Run Compiled Worker (macOS)

```bash
./build_worker_macos/dist/chaarfm_worker --url https://chaarfm.onrender.com --code YOUR_CODE
```

### Run Compiled Worker (Windows)

```cmd
build_worker_windows\dist\chaarfm_worker.exe --url https://chaarfm.onrender.com --code YOUR_CODE
```

---

## Music Pipeline

### GUI Application

```bash
python -m music_pipeline.gui_app
```

### Web Application

```bash
python -m music_pipeline.web_app
```

### Pipeline Components

```bash
# Download audio
python -m music_pipeline.downloader

# Tag metadata
python -m music_pipeline.tagger

# Vectorize audio
python -m music_pipeline.vectorizer

# Generate universe
python -m music_pipeline.universe
```

---

## Utilities

### Audio Processing

```bash
python audio_processor.py
```

### Genre Analysis

```bash
python genre_quality_analyzer.py
python genre_universe.py
```

### Clustering

```bash
python clustering.py
```

### Visualization

```bash
python visualize.py
```

### Upload to R2

```bash
python upload_to_r2.py
```

### Populate YouTube Universe

```bash
python populate_youtube_universe.py
```

---

## Recommendation System

### Batch Recommender

```bash
python batch_recommender.py
```

### User Recommender

```bash
python user_recommender.py
```

### Test Recommender

```bash
python scripts/debug_tools.py recommender
```

---

## Docker

### Build Docker Image

```bash
docker build -t chaarfm .
```

### Run Docker Container

```bash
docker run -p 5000:5000 --env-file .env chaarfm
```

### Migrate to Docker

```bash
python migrate_to_docker.py
```

---

## Git Operations

### Push Changes

```bash
# See GIT_PUSH_COMMAND.txt for safe push commands
git add .
git commit -m "Your message"
git push origin main
```

---

## Environment Variables

Create a `.env` file with:

```env
# Last.fm
LASTFM_API_KEY=your_key
LASTFM_API_SECRET=your_secret

# Database
DATABASE_URL=postgres://user:pass@host:5432/db

# S3/R2 Storage
S3_ENDPOINT=https://your-account.r2.cloudflarestorage.com
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
S3_BUCKET=your_bucket_name
R2_PUBLIC_URL=https://pub-xxx.r2.dev

# Optional
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_key
```

---

## Troubleshooting Commands

### Clear Cache

```bash
./force_clear_cache.sh
```

### Fix Cache and Build

```bash
./fix_cache_and_build.sh
```

### Check Algorithms

```bash
python scripts/debug_tools.py essentia
```

### Test Database Connection

```bash
python scripts/debug_tools.py db-schema
```

### Test S3 Connection

```bash
python scripts/debug_tools.py s3
```

---

## Quick Start Workflows

### Complete Setup and Build

```bash
# 1. Clone repository
git clone https://github.com/yourusername/chaarfm.git
cd chaarfm

# 2. Create environment
python3.10 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Setup environment variables
cp .env.example .env
# Edit .env with your credentials

# 5. Initialize database
python user_db.py

# 6. Run server
python server_user.py
```

### Build and Distribute Worker

```bash
# 1. Build worker
./build_worker_macos.sh

# 2. Test locally
./build_worker_macos/dist/chaarfm_worker --url http://localhost:5000 --code TEST

# 3. Distribute
# Share chaarfm_worker_macos.dmg
```

### Start Development Server

```bash
# 1. Activate environment
source venv/bin/activate

# 2. Start server with auto-reload
python server_user.py

# 3. In another terminal, start worker
python remote_worker.py --url http://localhost:5000 --code ABC123
```

---

## Environment Management

### Create Virtual Environment

```bash
python3.10 -m venv venv
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-worker.txt
```

### Upgrade Dependencies

```bash
pip install --upgrade -r requirements.txt
```

### Export Dependencies

```bash
pip freeze > requirements.txt
```

---

## Testing

### Run Tests

```bash
# All tests
python -m pytest tests/

# Specific test
python scripts/debug_tools.py recommender
```

### Test GUI Logic

```bash
python tests/test_gui_logic.py
```

---

## Notes

- Always activate virtual environment before running commands
- Use Python 3.9-3.11 for best compatibility
- Check `.env` file for required environment variables
- Build artifacts are in `build_worker_macos/` and `build_worker_windows/`
- Logs are written to console and log files (where applicable)
