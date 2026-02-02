# Last.fm Data Extractor

This tool uses the `pylast` library to extract top tracks and recent tracks from Last.fm.

## Prerequisites

1.  Python 3.x
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Last.fm API Account**: You need an API Key and Shared Secret.
    *   Get them here: [https://www.last.fm/api/account/create](https://www.last.fm/api/account/create)

## Usage

1.  Run the tool:
    ```bash
    python main.py
    ```
2.  Follow the prompts to enter your **API Key**, **API Secret**, and **Username**.

## Output

The tool will save your data to `lastfm_data.json` in the same directory.
The JSON file will contain:
-   `top_tracks`: Top 50 tracks of all time.
-   `recent_tracks`: Last 50 scrobbled tracks.
