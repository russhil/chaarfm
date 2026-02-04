import os
import sys
import ssl
import json
import asyncio
import logging
import requests
import traceback

# Try to import websocket client
try:
    import websockets
except ImportError:
    print("Error: 'websockets' library is required. Install with: pip install websockets")
    sys.exit(1)

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Reuse existing logic
from populate_youtube_universe import download_temp_youtube, download_temp_youtube_by_url, vectorize_audio

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - WORKER - %(message)s'
)
logger = logging.getLogger(__name__)

def _get_ssl_context():
    """Create SSL context with proper CA certs for wss:// connections (fixes macOS certificate verify failed)."""
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    return ctx

RECONNECT_DELAY_MIN = 2
RECONNECT_DELAY_MAX = 60
RECONNECT_BACKOFF_FACTOR = 1.5
KEEPALIVE_INTERVAL = 600  # 10 minutes

def _http_ping(url):
    """Blocking HTTP GET so we can run in executor."""
    requests.get(url, timeout=10)

async def _keepalive_loop(server_url):
    """Ping the server every 10 minutes so Render does not spin down during ingestion."""
    base = server_url.rstrip("/")
    url = f"{base}/api/keepalive"
    while True:
        await asyncio.sleep(KEEPALIVE_INTERVAL)
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _http_ping, url)
            logger.info("Keepalive ping sent (keeps server awake)")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Keepalive ping failed: %s", e)

async def run_worker_once(server_url, pairing_code):
    """Connect, process jobs until connection is lost. Returns when disconnected."""
    uri = f"{server_url}/ws/remote/{pairing_code}/worker"
    if uri.startswith("http"):
        uri = uri.replace("http", "ws")

    ssl_context = _get_ssl_context() if uri.startswith("wss://") else None
    async with websockets.connect(uri, ssl=ssl_context) as websocket:
        logger.info("Connected! Waiting for jobs...")
        ping_task = asyncio.create_task(_keepalive_loop(server_url))
        try:
            while True:
                message = await websocket.recv()
                data = json.loads(message)

                if data.get("type") == "job":
                    job_id = data.get("job_id")
                    payload = data.get("payload", {})
                    artist = payload.get("artist")
                    title = payload.get("title")
                    youtube_url = payload.get("youtube_url")

                    label = youtube_url or f"{artist} - {title}"
                    logger.info(f"Received Job: {label}")

                    try:
                        if youtube_url:
                            filepath, youtube_id, metadata = download_temp_youtube_by_url(youtube_url)
                            artist = artist or (metadata or {}).get('artist') or "YouTube Artist"
                            title = title or (metadata or {}).get('title') or f"Test Track {youtube_id or ''}".strip()
                        else:
                            filepath, youtube_id = download_temp_youtube(artist, title)

                        if not filepath:
                            logger.warning("Download failed")
                            await websocket.send(json.dumps({
                                "type": "result",
                                "job_id": job_id,
                                "status": "failed",
                                "error": "Download failed"
                            }))
                            continue

                        vector = vectorize_audio(filepath)
                        if os.path.exists(filepath):
                            os.remove(filepath)

                        if vector:
                            logger.info("Vectorization successful")
                            await websocket.send(json.dumps({
                                "type": "result",
                                "job_id": job_id,
                                "status": "success",
                                "data": {
                                    "artist": artist,
                                    "title": title,
                                    "youtube_id": youtube_id,
                                    "vector": vector,
                                    "source_url": youtube_url
                                }
                            }))
                        else:
                            logger.warning("Vectorization returned None")
                            await websocket.send(json.dumps({
                                "type": "result",
                                "job_id": job_id,
                                "status": "failed",
                                "error": "Vectorization failed"
                            }))

                    except Exception as e:
                        logger.error(f"Job Execution Error: {e}")
                        traceback.print_exc()
                        await websocket.send(json.dumps({
                            "type": "result",
                            "job_id": job_id,
                            "status": "failed",
                            "error": str(e)
                        }))

                elif data.get("type") == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))
        finally:
            ping_task.cancel()
            try:
                await ping_task
            except asyncio.CancelledError:
                pass


async def run_worker(server_url, pairing_code):
    """Connect and process jobs; reconnect with backoff when connection is lost."""
    uri = f"{server_url}/ws/remote/{pairing_code}/worker"
    if uri.startswith("http"):
        uri = uri.replace("http", "ws")

    delay = RECONNECT_DELAY_MIN
    while True:
        try:
            logger.info(f"Connecting to {uri}...")
            await run_worker_once(server_url, pairing_code)
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"Connection closed: {e}. Reconnecting in {delay:.0f}s...")
        except (OSError, asyncio.CancelledError) as e:
            if isinstance(e, asyncio.CancelledError):
                raise
            logger.warning(f"Connection error: {e}. Reconnecting in {delay:.0f}s...")
        except Exception as e:
            logger.error(f"Error: {e}")
            traceback.print_exc()
            logger.warning(f"Reconnecting in {delay:.0f}s...")

        await asyncio.sleep(delay)
        delay = min(delay * RECONNECT_BACKOFF_FACTOR, RECONNECT_DELAY_MAX)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Chaar.fm Remote Worker")
    parser.add_argument("--url", "-u", default="", help="Server URL (e.g. https://chaarfm.onrender.com)")
    parser.add_argument("--code", "-c", default="", help="Pairing code from /ingest page")
    args = parser.parse_args()

    print("=== Chaar.fm Remote Worker ===")
    default_host = "https://chaarfm.onrender.com"

    host = args.url.strip() if args.url else ""
    code = args.code.strip() if args.code else ""

    if not host or not code:
        try:
            host = host or input(f"Enter Server URL (default: {default_host}): ").strip() or default_host
            code = code or input("Enter Pairing Code: ").strip()
        except EOFError:
            print("\nUsage: python remote_worker.py --url https://chaarfm.onrender.com --code YOUR_CODE")
            sys.exit(1)

    if not code:
        print("Pairing code is required.")
        sys.exit(1)

    try:
        asyncio.run(run_worker(host, code))
    except KeyboardInterrupt:
        print("\nWorker stopped.")
