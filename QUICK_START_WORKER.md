# Quick Start - Remote Worker (Multi-Worker Support)

## Installation & Setup

### Step 1: Install Python Dependencies
```bash
pip3 install websockets requests certifi yt-dlp tensorflow tf-keras mutagen numpy librosa python-dotenv psycopg2-binary essentia
```

### Step 2: Download Worker Script
Copy `remote_worker.py` to the machine, or clone the repo.

## Running the Worker

### Single Worker
```bash
python3 remote_worker.py --url https://chaarfm.onrender.com --code YOUR_PAIRING_CODE
```

### Multiple Workers (Same Machine)
Open multiple terminals and run the same command in each:
```bash
# Terminal 1
python3 remote_worker.py --url https://chaarfm.onrender.com --code YOUR_PAIRING_CODE

# Terminal 2
python3 remote_worker.py --url https://chaarfm.onrender.com --code YOUR_PAIRING_CODE

# Terminal 3
python3 remote_worker.py --url https://chaarfm.onrender.com --code YOUR_PAIRING_CODE
```

### Multiple Workers (Different Machines)
Run the same command on each machine with the **same pairing code**:
```bash
python3 remote_worker.py --url https://chaarfm.onrender.com --code YOUR_PAIRING_CODE
```

## Getting a Pairing Code

1. Go to `/ingest` on your ChaarFM server
2. Generate a pairing code
3. Use that code when starting workers

## How It Works

- **Same Pairing Code = Shared Workload**
- Tasks are automatically distributed across all connected workers
- 2 workers = 2x faster, 3 workers = 3x faster, etc.
- Workers can connect/disconnect anytime
- If a worker disconnects, its task is reassigned

## Troubleshooting

**Connection Issues:**
```bash
# Check network
ping chaarfm.onrender.com

# Test with verbose output
python3 remote_worker.py --url https://chaarfm.onrender.com --code YOUR_CODE -v
```

**Missing Dependencies:**
```bash
# Install all at once
pip3 install websockets requests certifi yt-dlp tensorflow tf-keras mutagen numpy librosa python-dotenv psycopg2-binary essentia
```

**FFmpeg Required:**
- macOS: `brew install ffmpeg`
- Windows: Download from https://ffmpeg.org/download.html
- Linux: `sudo apt-get install ffmpeg` or `sudo yum install ffmpeg`

## Example Usage

```bash
# Start 3 workers on the same machine for 3x speed
python3 remote_worker.py --url https://chaarfm.onrender.com --code ABC123 &
python3 remote_worker.py --url https://chaarfm.onrender.com --code ABC123 &
python3 remote_worker.py --url https://chaarfm.onrender.com --code ABC123 &
```
