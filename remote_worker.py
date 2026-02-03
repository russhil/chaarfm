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

async def run_worker(server_url, pairing_code):
    uri = f"{server_url}/ws/remote/{pairing_code}/worker"
    if uri.startswith("http"):
        uri = uri.replace("http", "ws")
    
    logger.info(f"Connecting to {uri}...")
    
    ssl_context = _get_ssl_context() if uri.startswith("wss://") else None
    
    try:
        async with websockets.connect(uri, ssl=ssl_context) as websocket:
            logger.info("Connected! Waiting for jobs...")
            
            while True:
                try:
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
                        
                        # Execute Job
                        try:
                            # 1. Download
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
                                
                            # 2. Vectorize
                            vector = vectorize_audio(filepath)
                            
                            # Cleanup
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
                        
                except websockets.exceptions.ConnectionClosed:
                    logger.error("Connection closed by server")
                    break
                    
    except Exception as e:
        logger.error(f"Connection Error: {e}")

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
