from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
import os

def tag_mp3(filepath, artist, title, album=None):
    """
    Updates the ID3 tags of an MP3 file.
    """
    try:
        try:
            audio = MP3(filepath, ID3=EasyID3)
        except:
            # If no ID3 tag exists, create one
            audio = MP3(filepath)
            audio.add_tags()
            audio = MP3(filepath, ID3=EasyID3)
            
        audio['artist'] = artist
        audio['title'] = title
        if album:
            audio['album'] = album
            
        audio.save()
        # print(f"  Tagged: {artist} - {title}")
        return True
    except Exception as e:
        print(f"  Tagging error: {e}")
        return False
