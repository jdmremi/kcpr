from datetime import datetime
from uuid import uuid7
import api
import sys
import time

# poll every 60 seconds
REQUEST_INTERVAL_SEC: int = 60

# prints a timestamped message to stderr
def log(message: str):
    print(f"[{datetime.now().astimezone().isoformat()}] {message}", file=sys.stderr)

# calls fetch() and returns its result, or None if it fails for any reason
# (network error, bad status code, unexpected response format, ...)
def try_fetch(description: str, fetch):
    try:
        return fetch()
    except Exception as e:
        log(f"{description} failed: {e!r}")
        return None

# checks KCPR once; if a new track is playing, fetches the other data and logs it
def poll(state: api.AppState):
    now_playing = try_fetch("KCPR now playing", api.get_now_playing)
    # couldn't reach KCPR, try again next time
    if now_playing is None:
        return

    # same track as last time, nothing to do
    key = api.track_key(now_playing)
    if key == state.last_track_key:
        return

    # id and timestamp shared by every row from this poll (to relate entries across CSV files)
    request_id = str(uuid7())
    request_time = datetime.now().astimezone().isoformat()

    state.now_playing = now_playing
    state.current_weather = try_fetch("Weather", api.get_current_weather)

    # only look up songs: skip station IDs and entries with no artist
    is_song = not now_playing.is_ad and now_playing.artist is not None
    if is_song:
        state.current_track_analysis = try_fetch("Track analysis", lambda: api.get_track_analysis(now_playing))
        state.current_track_metadata = try_fetch("Track metadata", lambda: api.get_track_metadata(now_playing))
    else:
        state.current_track_analysis = None
        state.current_track_metadata = None

    for record in (state.now_playing, state.current_weather, state.current_track_analysis, state.current_track_metadata):
        if record is not None:
            record.request_id = request_id
            record.request_time = request_time

    # log even if some lookups failed, so every play is recorded exactly once
    api.log_state(state)
    state.last_track_key = key
    log(f"Logged: {now_playing.title} - {now_playing.artist}")

if __name__ == "__main__":
    # create csv files if they don't exist and write their headers
    api.ensure_csv_files_exist()
    # holds current state info. starts from the last logged track so a restart doesn't log it twice.
    state = api.AppState(last_track_key=api.load_last_track_key())

    while True:
        poll(state)
        time.sleep(REQUEST_INTERVAL_SEC)