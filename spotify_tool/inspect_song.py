import spotapi
import inspect
from spotapi import Song

try:
    print(inspect.getsource(Song.query_songs))
except Exception as e:
    print(f"Error: {e}")
