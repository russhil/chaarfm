
import user_db
from datetime import datetime

user_db.init_db()
user_db.log_interaction_db(
    session_id="test_session",
    user_id="russhil",
    track_id="test_track",
    filename="test_song.mp3",
    action="play",
    duration=0,
    justification="Testing admin logs",
    details="Manual insertion"
)
print("Inserted log.")
