# Spotify Data Extractor

This tool uses the `spotapi` library to extract your top tracks and recently played tracks from Spotify.

## Prerequisites

1.  Python 3.x
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  Run the tool:
    ```bash
    python main.py
    ```
2.  Follow the prompts to enter your Spotify `sp_dc` cookie and username/email.

### How to get your `sp_dc` cookie:

1.  Open Spotify in your web browser and log in.
2.  Open Developer Tools (F12 or Right Click -> Inspect).
3.  Go to the **Application** tab (Chrome/Edge) or **Storage** tab (Firefox).
4.  Expand **Cookies** and select `https://open.spotify.com`.
5.  Find the cookie named `sp_dc` and copy its value.

## Output

The tool will save your data to `spotify_data.json` in the same directory.
The JSON file will contain:
-   `top_tracks`: Your top tracks for short, medium, and long terms.
-   `recently_played`: Your recently played tracks.
