import yt_dlp
import os
import glob

def download_song(artist, title, output_dir="downloads"):
    """
    Downloads a song from YouTube using yt-dlp.
    Returns the path to the downloaded mp3 file or None if failed.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    search_query = f"{artist} {title} lyrics"
    filename_template = f"{output_dir}/{artist} - {title}.%(ext)s"
    
    # Check if already exists
    expected_file = f"{output_dir}/{artist} - {title}.mp3"
    if os.path.exists(expected_file):
        print(f"  Skipping (already exists): {expected_file}")
        return expected_file

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filename_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'default_search': 'ytsearch1',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        # Filters to avoid music videos if possible (heuristic: duration)
        # Lyrics videos are usually 2-8 mins.
        'match_filter': yt_dlp.utils.match_filter_func("duration > 60 & duration < 900"), 
        'addmetadata': True,
    }

    print(f"  Downloading: {artist} - {title}...")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([search_query])
            
        # Verify file exists
        if os.path.exists(expected_file):
            return expected_file
        else:
            # Sometimes extension handling is tricky, check glob
            files = glob.glob(f"{output_dir}/{artist} - {title}.*")
            if files:
                return files[0]
            return None
            
    except Exception as e:
        print(f"  Download failed: {e}")
        return None
