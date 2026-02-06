# ChaarFM Quick Start

## 🚀 30-Second Start

```bash
# Setup
./setup.sh server

# Run
source venv/bin/activate
python server_user.py
```

## 📦 Common Commands

### Setup
```bash
./setup.sh server          # Setup server
./setup.sh worker          # Setup worker build env
./setup.sh dev             # Setup both
```

### Build
```bash
./build.sh macos           # Build for macOS
./build.sh windows         # Build for Windows
./build.sh clean           # Clean artifacts
```

### Debug
```bash
python scripts/debug_tools.py all              # All checks
python scripts/debug_tools.py essentia         # Check Essentia
python scripts/debug_tools.py recommender      # Test recommender
```

### Database
```bash
python scripts/db_migrations.py fix-schema     # Fix schema
python scripts/db_migrations.py migrate-qdrant # Migrate
```

### Run
```bash
python server_user.py      # User server
python server_admin.py     # Admin server
python control_panel.py    # GUI panel
```

## 📚 Full Documentation

- **README.md** - Project overview
- **docs/BUILD_GUIDE.md** - Build instructions
- **docs/COMMANDS.md** - All commands
- **CLEANUP_SUMMARY.md** - What changed
- **OPTIMIZATION_COMPLETE.md** - Full details

## 🆘 Help

```bash
./setup.sh --help
./build.sh --help
python scripts/debug_tools.py --help
python scripts/db_migrations.py --help
```

## 🎯 First Time Setup

```bash
# 1. Setup environment
./setup.sh dev

# 2. Configure (create .env with your credentials)
cp .env.example .env
# Edit .env with your DATABASE_URL, API keys, etc.

# 3. Initialize database
source venv/bin/activate
python user_db.py

# 4. Run server
python server_user.py

# 5. Build worker (optional)
./build.sh macos
```

## ✅ Verify Everything Works

```bash
# Test all systems
python scripts/debug_tools.py all
```

---

**Need more details?** See full documentation in `docs/` or run any command with `--help`
