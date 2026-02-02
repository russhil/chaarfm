# ChaarFM - Personalized Music Vectorization & Streaming

A high-performance music recommendation engine that uses audio feature vectorization (MusicNN) and Qdrant to create personalized, cluster-based playlists.

## 🚀 Features

- **Parallel Vectorization**: Optimized for M3/Apple Silicon with multi-core processing.
- **Plug & Play**: Works on any machine with configurable music directories.
- **Admin Dashboard**: Real-time analytics, LLM-powered insights, and vector control.
- **Multi-User**: Session management and per-user recommendations.
- **Control Panel**: Easy desktop GUI for managing the entire stack.

## 🛠️ Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-repo/chaarfm.git
    cd chaarfm
    ```

2.  **Install Dependencies**:
    Requires Python 3.9+.
    ```bash
    pip install -r requirements.txt
    ```

    *Note: You may need `essentia` or `essentia-tensorflow`. If `pip install essentia` fails, check [Essentia Official Docs](https://essentia.upf.edu/installing.html).*

3.  **Install Qdrant**:
    Run Qdrant using Docker:
    ```bash
    docker run -p 6333:6333 qdrant/qdrant
    ```
    *Or the pipeline will fallback to a local disk-based instance if Docker is not available.*

## 🎮 How to Run

### **Mac/Linux Users:**
Double-click the **`ChaarFM_Control_Panel.command`** file.

### **Manual Method:**
Run the control panel script:
```bash
python3 control_panel.py
```

## ⚙️ Configuration (First Run)

1.  Open the **Control Panel**.
2.  Click **📂 Configure Directories**.
3.  Add your music folders (mp3/wav/flac). Give them a source name (e.g., "russhil", "mymusic").
4.  Click **🎛️ Start Vectorising UI** or run the optimized pipeline command below.

## ⚡ Power User: Fast Vectorization

To run the ultra-optimized vectorization pipeline (for thousands of songs):

```bash
python3 pipeline_vectorize.py --recreate --workers 6
```
- `--recreate`: Wipes DB and starts fresh.
- `--workers 6`: Sets parallel workers (Adjust based on CPU).
- `--store-path`: Optional, stores full file path in DB.

## 🌐 Ports

- **App**: `http://localhost:5001`
- **Admin/Pipeline UI**: `http://localhost:5002`
- **Qdrant DB**: `http://localhost:6333`

## 🔒 Security

- `chaarfm_config.json` stores your local paths and is **not committed**.
- `vectorize_state.db` stores local processing state and is **not committed**.

## ☁️ Hosting & Cloud Database

This app is "Cloud Ready". To deploy:

1.  **Database (Supabase/Postgres)**:
    - Create a project on [Supabase](https://supabase.com).
    - Get the **Connection String** (Transaction Mode aka Port 6543 or Session Mode Port 5432).
    - Set Environment Variable: `DATABASE_URL=postgresql://user:pass@host:5432/postgres`

2.  **Vector DB (Qdrant Cloud)**:
    - Create a cluster on [Qdrant Cloud](https://cloud.qdrant.io).
    - Set Environment Variables:
      - `QDRANT_URL=https://xyz.qdrant.tech`
      - `QDRANT_API_KEY=your_key`

3.  **Deploy App**:
    - Push to GitHub.
    - Connect to Vercel/Render/Railway.
    - Add the Environment Variables above.
    - Set `MUSIC_ROOT` if serving files from a connected volume, or configure cloud storage (coming soon).

4.  **Sync Files (Hybrid Mode)**:
    Since vectorization happens locally:
    - Run `python3 upload_to_r2.py` on your laptop to sync MP3s to your Cloudflare bucket.
    - The hosted app will stream from there automatically.
