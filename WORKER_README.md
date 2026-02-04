# ChaarFM Remote Worker

Standalone executable for distributed music ingestion. Run multiple workers to process ingestion tasks in parallel.

## Quick Start

### macOS
1. Download `chaarfm_worker_macos.dmg`
2. Mount and drag to Applications (or run directly)
3. Open Terminal and run:
   ```bash
   ./chaarfm_worker --url https://chaarfm.onrender.com --code YOUR_CODE
   ```

### Windows
1. Download `chaarfm_worker.exe`
2. Open Command Prompt or PowerShell
3. Run:
   ```cmd
   chaarfm_worker.exe --url https://chaarfm.onrender.com --code YOUR_CODE
   ```

## Getting a Pairing Code

1. Go to `/ingest` on your ChaarFM server
2. Generate a pairing code
3. Use that code when starting workers

## Multiple Workers = Faster Processing

**The magic**: Run multiple workers with the **same pairing code** and tasks are automatically distributed!

### Example Scenarios

**Scenario 1: Single Machine**
```bash
# Terminal 1
./chaarfm_worker --url https://chaarfm.onrender.com --code ABC123

# Terminal 2 (same machine)
./chaarfm_worker --url https://chaarfm.onrender.com --code ABC123

# Terminal 3 (same machine)
./chaarfm_worker --url https://chaarfm.onrender.com --code ABC123
```
Result: 3x faster processing! Tasks are split across all 3 workers.

**Scenario 2: Multiple Machines**
- Machine 1 (Windows): `chaarfm_worker.exe --url ... --code ABC123`
- Machine 2 (macOS): `./chaarfm_worker --url ... --code ABC123`
- Machine 3 (Linux): `./chaarfm_worker --url ... --code ABC123`

Result: All machines work together on the same job queue!

## How It Works

1. **Connect**: Worker connects to server via WebSocket
2. **Receive Tasks**: Server sends tasks (download + vectorize audio)
3. **Process**: Worker downloads from YouTube and generates embeddings
4. **Return Results**: Worker sends results back to server
5. **Auto-Distribute**: Server automatically sends next task to available workers

### Task Distribution

- Tasks are queued when ingestion starts
- Each available worker receives a task immediately
- When a worker finishes, it gets the next task from the queue
- If a worker disconnects, its task can be reassigned
- All workers share the same queue for maximum efficiency

## Command Line Options

```bash
chaarfm_worker [OPTIONS]

Options:
  --url, -u URL     Server URL (default: prompts for input)
  --code, -c CODE   Pairing code from /ingest page (required)
  --help, -h        Show help message
```

## Troubleshooting

### Connection Issues

**"Connection refused" or "Cannot connect"**
- Check that the server URL is correct
- Ensure the server is running and accessible
- Check your firewall/network settings

**"SSL certificate verify failed"**
- Update your system certificates
- macOS: Update macOS or run `sudo update-ca-certificates`
- Windows: Update Windows to get latest root certificates

### Processing Issues

**"Download failed"**
- Check your internet connection
- YouTube may be blocking requests (temporary)
- Try again later

**"Vectorization failed"**
- Ensure you have sufficient disk space
- Check that audio file downloaded correctly
- This is usually temporary - worker will continue with next task

**"FFmpeg not found"**
- FFmpeg should be bundled with the executable
- If not, install FFmpeg separately:
  - macOS: `brew install ffmpeg`
  - Windows: Download from https://ffmpeg.org/download.html

### Performance

**Worker seems slow**
- First run downloads the MusicNN model (~50MB) - this is one-time
- Audio processing is CPU-intensive - be patient
- Multiple workers = faster overall processing

**High CPU/Memory Usage**
- Normal! Audio processing is resource-intensive
- Each worker uses significant CPU and RAM
- Close other applications if needed

## Advanced Usage

### Running in Background

**macOS/Linux:**
```bash
nohup ./chaarfm_worker --url ... --code ... > worker.log 2>&1 &
```

**Windows:**
Use Task Scheduler or run as a service (requires additional setup)

### Monitoring

Watch the console output for:
- Connection status
- Tasks received
- Processing progress
- Errors and warnings

### Stopping Workers

- Press `Ctrl+C` in the terminal
- Or close the terminal window
- Server will detect disconnection and reassign tasks

## Technical Details

### What Gets Processed

Each task involves:
1. **Download**: Fetch audio from YouTube using yt-dlp
2. **Quality Check**: Verify file size and duration
3. **Vectorize**: Generate 200-dimensional embedding using MusicNN
4. **Upload**: Send results back to server for storage

### Dependencies (Bundled)

- **yt-dlp**: YouTube downloader
- **Essentia**: Audio analysis library
- **TensorFlow/Keras**: Machine learning framework
- **MusicNN**: Pre-trained model for music embeddings
- **FFmpeg**: Audio processing (if bundled)

### System Requirements

- **macOS**: 10.14+ (Mojave or later)
- **Windows**: Windows 10 or later
- **RAM**: 2GB minimum, 4GB+ recommended
- **Disk**: 500MB+ free space (for model and temp files)
- **Network**: Stable internet connection

## Building from Source

See `BUILD_WORKER.md` for instructions on building the executable from source.

## Support

For issues or questions:
- Check the console output for error messages
- Ensure all prerequisites are met
- Verify server connectivity
- Check GitHub issues: https://github.com/your-repo/chaarfm

## License

Same as ChaarFM project license.
