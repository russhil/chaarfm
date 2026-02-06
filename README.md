
# 🎵 ChaarFM

A powerful music recommendation system that uses audio embeddings and machine learning to create personalized music experiences.

## Features

- **Audio Vectorization**: Uses Essentia and MusicNN to create audio embeddings
- **Intelligent Recommendations**: ML-powered recommendation engine with clustering and affinity learning
- **Multi-source Ingestion**: Support for Last.fm, YouTube, and local files
- **Distributed Processing**: Multi-worker architecture for parallel audio processing
- **Cloud Storage**: R2/S3 integration for scalable audio storage
- **User Management**: Authentication and personalized music universes

## Quick Start

### Prerequisites

- Python 3.9-3.11
- PostgreSQL database
- R2/S3 storage (optional)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/chaarfm.git
cd chaarfm

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```env
# Last.fm API
LASTFM_API_KEY=your_key
LASTFM_API_SECRET=your_secret

# Database
DATABASE_URL=postgres://user:pass@host:5432/db

# Storage (optional)
S3_ENDPOINT=https://your-account.r2.cloudflarestorage.com
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
S3_BUCKET=your_bucket_name
R2_PUBLIC_URL=https://pub-xxx.r2.dev
```

### Initialize Database

```bash
python user_db.py
```

### Run Server

```bash
# User-facing server
python server_user.py

# Or use control panel
python control_panel.py
```

## Usage

### Music Pipeline GUI

Extract your music universe from Last.fm:

```bash
python -m music_pipeline.gui_app
```

**Workflow:**
1. Enter Last.fm username to fetch top tracks and recommendations
2. Select how many tracks to process
3. Pipeline will:
   - Download MP3s (yt-dlp)
   - Tag metadata (mutagen)
   - Vectorize audio (Essentia/MusicNN)
   - Upload to R2 storage
   - Store embeddings in PostgreSQL

### Remote Workers

Process audio files in parallel using distributed workers:

```bash
# Start a worker
python remote_worker.py --url https://your-server.com --code YOUR_CODE

# Or use pre-built executable (see docs/BUILD_GUIDE.md)
./chaarfm_worker --url https://your-server.com --code YOUR_CODE
```

Multiple workers can connect with the same code for parallel processing.

### Web Interface

Navigate to your server URL to:
- Browse your music collection
- Get recommendations
- Upload tracks
- View analytics

## Documentation

- **[Build Guide](docs/BUILD_GUIDE.md)**: Build standalone worker executables
- **[Commands Reference](docs/COMMANDS.md)**: All available commands
- **[Debug Tools](scripts/debug_tools.py)**: Diagnostic and testing utilities
- **[Database Migrations](scripts/db_migrations.py)**: Database maintenance tools

## Architecture

### Components

- **Server**: Flask/FastAPI web server
- **User Database**: PostgreSQL with user management
- **Vector Database**: pgvector for audio embeddings
- **Worker Coordinator**: Distributes tasks to remote workers
- **Audio Pipeline**: Downloads, tags, and vectorizes audio
- **Recommender**: ML-based recommendation engine with clustering

### Data Flow

1. User submits tracks via web interface or Last.fm import
2. Server creates processing tasks
3. Workers download and process audio
4. Embeddings stored in vector database
5. Recommender generates personalized suggestions
6. User receives curated playlists

## Command Reference

### Debug & Testing

```bash
# Run all diagnostics
python scripts/debug_tools.py all

# Individual checks
python scripts/debug_tools.py essentia
python scripts/debug_tools.py recommender
python scripts/debug_tools.py db-schema
```

### Database Operations

```bash
# Migrations
python scripts/db_migrations.py fix-schema
python scripts/db_migrations.py migrate-qdrant
python scripts/db_migrations.py add-youtube-col
```

### Build Workers

```bash
# macOS
./build_worker_macos.sh

# Windows
build_worker_windows.bat
```

See [docs/COMMANDS.md](docs/COMMANDS.md) for complete command reference.

## Development

### Project Structure

```
chaarfm/
├── server_user.py          # Main user-facing server
├── remote_worker.py        # Distributed worker
├── user_recommender.py     # Recommendation engine
├── user_db.py             # Database layer
├── music_pipeline/        # Audio processing pipeline
│   ├── gui_app.py        # GUI application
│   ├── downloader.py     # Audio downloader
│   ├── tagger.py         # Metadata tagger
│   └── vectorizer.py     # Audio vectorization
├── scripts/              # Utilities
│   ├── debug_tools.py   # Debug utilities
│   └── db_migrations.py # Database tools
├── docs/                # Documentation
│   ├── BUILD_GUIDE.md  # Build instructions
│   └── COMMANDS.md     # Command reference
└── chaarfm-source/     # Frontend source
```

### Running Tests

```bash
python scripts/debug_tools.py all
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Troubleshooting

### Common Issues

**Build fails with cache permission errors:**
```bash
python build_with_fixed_cache.py build_worker.spec
```

**Database connection errors:**
```bash
python scripts/debug_tools.py db-schema
```

**SSL certificate errors:**
```bash
# macOS
sudo update-ca-certificates

# Windows
# Update Windows via Windows Update
```

See [docs/BUILD_GUIDE.md](docs/BUILD_GUIDE.md) for detailed troubleshooting.

## License

[Your License Here]

## Credits

- **Essentia**: Audio analysis library
- **MusicNN**: Music tagging model
- **yt-dlp**: Audio download
- **Flask/FastAPI**: Web framework
- **PostgreSQL/pgvector**: Vector storage

## Support

For issues and questions:
- Open an issue on GitHub
- Check documentation in `docs/`
- Run diagnostics: `python scripts/debug_tools.py all`