# Distributed Vectorization System (Server-Coordinator / Laptop-Worker)

Since Render cannot handle the heavy lifting (vectorization), we will turn your laptop into a "Remote Processing Unit" that connects to the server securely to perform the work.

## 1. Architecture
*   **The Coordinator (Render Server)**: Acts as the brain. It fetches the "To-Do List" from Last.fm, checks the database for what's missing, and assigns tasks.
*   **The UI (Browser)**: Generates a unique **Pairing Code** (e.g., `8721`) and displays the progress.
*   **The Worker (Your Laptop)**: A Python script you run locally. You enter the Pairing Code, and it connects to the server via WebSocket. It receives "Download & Vectorize this song" commands, does the work locally, and sends the result (Vector + ID) back to the server.

## 2. Implementation Steps

### Step 1: Server Logic (Coordinator)
*   Update `web_app.py` to handle "Remote Sessions".
*   Create a WebSocket endpoint `/ws/remote/{code}/{client_type}`.
*   Implement a job queue system:
    *   **UI** sends `START {username}` -> **Server** fetches Last.fm tracks -> **Server** sends `JOB {artist, title}` to **Worker**.
    *   **Worker** sends `RESULT {vector, id}` -> **Server** saves to DB -> **Server** sends `PROGRESS` to **UI**.

### Step 2: The Worker Script (`remote_worker.py`)
*   Create a standalone script for your laptop.
*   It will reuse the existing logic (`download_temp_youtube`, `vectorize_audio`) but triggered by network events.
*   **Plug & Play**: You just run `python remote_worker.py`, enter the code displayed on your screen, and watch it go.

### Step 3: Frontend Update
*   Modify `ingest` page to show: "Server Mode (Legacy)" vs "Remote Worker Mode (Recommended)".
*   In Remote Mode, display a large **Pairing Code** and a status: "Waiting for laptop to connect...".

## 3. Workflow
1.  Open `/ingest` on your hosted app.
2.  Select "Remote Worker Mode".
3.  Copy the 4-digit code displayed.
4.  Open your terminal on laptop: `python remote_worker.py`.
5.  Paste the code.
6.  The browser UI will update to "Connected" and start showing progress as your laptop churns through the songs.

This approach bypasses Render's limitations completely while keeping the "Central Database" architecture intact.