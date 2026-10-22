from dataclasses import dataclass, fields
from dataclass_csv import DataclassWriter
from datetime import datetime, timezone
from dotenv import load_dotenv
import csv
import os
import re
import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import xml.etree.ElementTree as ET

# load env vars
load_dotenv()

STATION_ID_TITLE: str = "KCPR Cal Poly Radio. Where Different Matters."
KCPR_NOW_PLAYING_URL: str = "https://streamdb8web.securenetsystems.net/player_status_update/KCPR1.xml"
OPENWEATHER_API_KEY: str  = os.environ["OPENWEATHER_API_KEY"]
SOUNDNET_API_KEY: str     = os.environ["SOUNDNET_API_KEY"]

# use safari user agent to "mimic" a browser request... this doesn't mimic browser requests entirely but is okay enough
KCPR_REQUEST_HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.6.2 Safari/605.1.15",
}

# latitude/longitude of cal poly graphic arts building
CAL_POLY_LAT, CAL_POLY_LON    = 35.29929042318235, -120.66171542472954
OPENWEATHER_API_URL_BASE: str = "https://api.openweathermap.org/data/2.5/weather"

SOUNDNET_API_URL_BASE: str               = "https://track-analysis.p.rapidapi.com/pktx"
SOUNDNET_REQUEST_HEADERS: dict[str, str] = {
    "x-rapidapi-host": "track-analysis.p.rapidapi.com",
    "x-rapidapi-key": SOUNDNET_API_KEY,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.6.2 Safari/605.1.15",
    "accept": "application/json",
}

KCPR_REQUEST_SESSION: requests.Session    = requests.Session()
OPENWEATHER_API_SESSION: requests.Session = requests.Session()
SOUNDNET_API_SESSION: requests.Session    = requests.Session()

"""
Note: Below, request_id and request_time are used to relate entries: ntries with the same request_id and request_time are related to each other.
"""
@dataclass
class KcprResponse:
    request_id: str | None
    request_time: str | None
    dcs_output_version: int
    station_call_sign: str
    program_type: str
    media_type: str
    title: str
    artist: str | None
    album: str | None
    cover: str | None
    duration: int
    campaign_id: str | None
    file_id: str | None
    click_url: str | None
    program_start_ts: datetime
    ad_block_pos: str | None
    plays: int
    plays_days: int
    is_ad: bool

@dataclass
class WeatherResponse:
    request_id: str | None
    request_time: str | None
    lon: float
    lat: float
    weather_id: int
    weather_main: str
    weather_description: str
    weather_icon: str
    base: str
    temp: float
    feels_like: float
    temp_min: float
    temp_max: float
    pressure: int
    humidity: int
    sea_level: int | None
    grnd_level: int | None
    visibility: int | None
    wind_speed: float
    wind_deg: int | None
    wind_gust: float | None
    clouds: int
    dt: int
    timezone: int
    sys_type: int | None
    sys_id: int | None
    country: str
    sunrise: int
    sunset: int
    id: int
    name: str
    cod: int

@dataclass
class TrackAnalysis:
    request_id: str | None
    request_time: str | None
    id: str
    key: str
    mode: str
    camelot: str
    tempo: int
    duration: str
    popularity: int
    energy: int
    danceability: int
    happiness: int
    acousticness: int
    instrumentalness: int
    liveness: int
    speechiness: int
    loudness: str

@dataclass
class TrackMetadata:
    request_id: str | None
    request_time: str | None
    id: str
    title: str
    length: int
    video: bool
    first_release_date: str
    aliases: str
    genres: str
    artist_name: str
    artist_sort_name: str
    artist_type: str
    artist_country: str
    artist_aliases: str
    artist_genres: str
    release_titles: str
    release_dates: str
    release_countries: str
    release_statuses: str
    release_qualities: str
    release_genres: str
    release_languages: str
    release_scripts: str

@dataclass
class AppState:
    # identifies the last logged track (see track_key)
    last_track_key: tuple[str, ...] | None = None
    now_playing: KcprResponse | None = None
    current_weather: WeatherResponse | None = None
    current_track_analysis: TrackAnalysis | None = None
    current_track_metadata: TrackMetadata | None = None

# headers for csv
CSV_FILE_HEADERS = {
    "now_playing.csv": ",".join([f.name for f in fields(KcprResponse)]),
    "track_analysis.csv": ",".join([f.name for f in fields(TrackAnalysis)]),
    "track_metadata.csv": ",".join([f.name for f in fields(TrackMetadata)]),
    "weather.csv": ",".join([f.name for f in fields(WeatherResponse)])
}

# identifies a track play. request_id/request_time are left out since they change on every poll.
# program_start_ts is included so the same song played twice in a row counts as two plays.
def track_key(track: KcprResponse) -> tuple[str, ...]:
    return (track.title, track.artist or "", track.album or "", str(track.program_start_ts))

# returns the key of the last track in now_playing.csv, so a restart doesn't log the current track twice
def load_last_track_key() -> tuple[str, ...] | None:
    if not os.path.exists("./now_playing.csv"):
        return None
    with open("./now_playing.csv", newline="") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        return None
    last = rows[-1]
    return (last["title"], last["artist"], last["album"], last["program_start_ts"])

# returns the currently playing song from KCPR.
def get_now_playing():
    res = KCPR_REQUEST_SESSION.get(KCPR_NOW_PLAYING_URL, headers=KCPR_REQUEST_HEADERS, timeout=10)

    res.raise_for_status()
    data = ET.fromstring(res.content)

    # strips whitespace from tag value
    def get_text(tag: str) -> str | None:
        value = data.findtext(tag)
        return value.strip() or None if value is not None else None

    return KcprResponse(
        request_id=None,
        request_time=None,
        dcs_output_version=int(get_text("DCSoutputVersion") or 0),
        station_call_sign=get_text("stationCallSign") or "",
        program_type=get_text("programType") or "",
        media_type=get_text("mediaType") or "",
        title=get_text("title") or "",
        artist=get_text("artist"),
        album=get_text("album"),
        cover=get_text("cover"),
        duration=int(get_text("duration") or 0),
        campaign_id=get_text("campaignId"),
        file_id=get_text("fileId"),
        click_url=get_text("clickURL"),
        program_start_ts=datetime.strptime(get_text("programStartTS") or "", "%d %b %Y %H:%M:%S").replace(tzinfo=timezone.utc),
        ad_block_pos=get_text("adBlockPos"),
        plays=int(get_text("plays") or 0),
        plays_days=int(get_text("playsDays") or 0),
        is_ad=(STATION_ID_TITLE in " ".join((get_text("title") or "").split())),
    )

# returns the current weather
def get_current_weather():
    res = OPENWEATHER_API_SESSION.get(OPENWEATHER_API_URL_BASE, params={
        "lat": CAL_POLY_LAT,
        "lon": CAL_POLY_LON,
        "appid": OPENWEATHER_API_KEY,
    }, timeout=10)

    res.raise_for_status()
    data = res.json()

    weather = data["weather"][0]
    main = data["main"]
    wind = data["wind"]
    sys = data["sys"]

    return WeatherResponse(
        request_id=None,
        request_time=None,
        lon=data["coord"]["lon"],
        lat=data["coord"]["lat"],
        weather_id=weather["id"],
        weather_main=weather["main"],
        weather_description=weather["description"],
        weather_icon=weather["icon"],
        base=data["base"],
        temp=main["temp"],
        feels_like=main["feels_like"],
        temp_min=main["temp_min"],
        temp_max=main["temp_max"],
        pressure=main["pressure"],
        humidity=main["humidity"],
        sea_level=main.get("sea_level"),
        grnd_level=main.get("grnd_level"),
        visibility=data.get("visibility"),
        wind_speed=wind["speed"],
        wind_deg=wind.get("deg"),
        wind_gust=wind.get("gust"),
        clouds=data["clouds"]["all"],
        dt=data["dt"],
        timezone=data["timezone"],
        sys_type=sys.get("type"),
        sys_id=sys.get("id"),
        country=sys["country"],
        sunrise=sys["sunrise"],
        sunset=sys["sunset"],
        id=data["id"],
        name=data["name"],
        cod=data["cod"],
    )

# created on startup
_spotify_client = None
# returns the Spotify client; reads SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET from the .env.
def get_spotify_client():
    global _spotify_client
    if _spotify_client is None:
        _spotify_client = spotipy.Spotify(auth_manager=SpotifyClientCredentials(), requests_timeout=10)
    return _spotify_client

# words that mark a version of a song (clean, radio edit, remastered 2011, ...) rather than a different song
_VERSION_TAG_WORDS = r"(?:clean|dirty|explicit|radio|edit|version|single|album|original|mix|remix|remaster(?:ed)?|v\d*|\d{4})"
_VERSION_TAG = re.compile(rf"\s*{_VERSION_TAG_WORDS}(?:\s+{_VERSION_TAG_WORDS})*\s*", re.IGNORECASE)
_BRACKET_GROUP = re.compile(r"\s*[(\[]([^)\]]*)[)\]]")
_DASH_SUFFIX = re.compile(r"\s+-\s+(.*)$")

# returns the title without version tags like "(Clean)", "[Radio Edit]", "(Remix)" or " - Remastered 2011", for searching APIs.
# a group is only removed if every word in it is a tag, so "(Time Edit)" and "(obli Remix)" are kept.
def search_title(title: str) -> str:
    drop_if_tag = lambda match: "" if _VERSION_TAG.fullmatch(match.group(1)) else match.group(0)
    cleaned = _DASH_SUFFIX.sub(drop_if_tag, _BRACKET_GROUP.sub(drop_if_tag, title)).strip()
    return cleaned or title

# returns the album name of the best Spotify match for the provided KcprResponse, or None if no match is found
def get_album_from_spotify(kcpr_response: KcprResponse) -> str | None:
    # quotes keep multi-word values inside their filter (unquoted, only the first word is filtered).
    # double quotes inside a value would end the quoted string early, so they're removed.
    quote = lambda value: '"' + value.replace('"', "") + '"'

    query = f"track:{quote(search_title(kcpr_response.title))}"
    if kcpr_response.artist:
        query += f" artist:{quote(kcpr_response.artist)}"

    results = get_spotify_client().search(q=query, type="track", limit=1)
    tracks = (results or {}).get("tracks", {}).get("items") or []
    if not tracks:
        return None
    return (tracks[0].get("album") or {}).get("name") or None

# returns track an analysis from the SoundNet API for the provided KcprResponse
def get_track_analysis(kcpr_response: KcprResponse):
    res = SOUNDNET_API_SESSION.get("https://track-analysis.p.rapidapi.com/pktx/analysis", params={
        "song": search_title(kcpr_response.title),
        "artist": kcpr_response.artist,
    }, headers=SOUNDNET_REQUEST_HEADERS, timeout=30)

    if num_requests_remaining := res.headers.get("X-RateLimit-Requests-Remaining"):
        print(f"[SoundNet] Remaining requests: {num_requests_remaining}")

    res.raise_for_status()
    data = res.json()

    return TrackAnalysis(
        request_id=None,
        request_time=None,
        id=data.get("id") or "",
        key=data.get("key") or "",
        mode=data.get("mode") or "",
        camelot=data.get("camelot") or "",
        tempo=data.get("tempo") or 0,
        duration=data.get("duration") or "",
        popularity=data.get("popularity") or 0,
        energy=data.get("energy") or 0,
        danceability=data.get("danceability") or 0,
        happiness=data.get("happiness") or 0,
        acousticness=data.get("acousticness") or 0,
        instrumentalness=data.get("instrumentalness") or 0,
        liveness=data.get("liveness") or 0,
        speechiness=data.get("speechiness") or 0,
        loudness=data.get("loudness") or "",
    )

# returns track datadata from the SoundNet API for the provided KcprResponse 
def get_track_metadata(kcpr_response: KcprResponse):
    # KCPR sometimes leaves the album blank, which makes SoundNet fail; ask Spotify for it instead
    album = kcpr_response.album or get_album_from_spotify(kcpr_response)
    if album is None:
        raise ValueError(f"No album found on Spotify for {kcpr_response.title!r} by {kcpr_response.artist!r}")

    res = SOUNDNET_API_SESSION.get(f"{SOUNDNET_API_URL_BASE}/metadata/track", params={
        "name": search_title(kcpr_response.title),
        "artist": kcpr_response.artist,
        "album": album,
    }, headers=SOUNDNET_REQUEST_HEADERS, timeout=30)

    if num_requests_remaining := res.headers.get("X-RateLimit-Requests-Remaining"):
        print(f"[SoundNet] Remaining requests: {num_requests_remaining}")
        
    res.raise_for_status()
    data = res.json()

    # flattens a list into a " | " delimited string
    flatten = lambda values:  " | ".join(str(value) for value in dict.fromkeys(values) if value is not None and value != "")

    credits = data.get("artistCredit") or []
    artist = (credits[0].get("artist") or {}) if credits else {}
    releases = data.get("releases") or []

    return TrackMetadata(
        request_id=None,
        request_time=None,
        id=data.get("id") or "",
        title=data.get("title") or "",
        length=data.get("length") or 0,
        video=data.get("video", False),
        first_release_date=data.get("firstReleaseDate") or "",
        aliases=flatten(a.get("name") for a in data.get("aliases") or []),
        genres=flatten(g.get("name") for g in data.get("genres") or []),
        artist_name=artist.get("name") or "",
        artist_sort_name=artist.get("sortName") or "",
        artist_type=artist.get("type") or "",
        artist_country=artist.get("country") or "",
        artist_aliases=flatten(a.get("name") for a in artist.get("aliases") or []),
        artist_genres=flatten(g.get("name") for g in artist.get("genres") or []),
        release_titles=flatten(r.get("title") for r in releases),
        release_dates=flatten(r.get("date") for r in releases),
        release_countries=flatten(r.get("country") for r in releases),
        release_statuses=flatten(r.get("status") for r in releases),
        release_qualities=flatten(r.get("quality") for r in releases),
        release_genres=flatten(g.get("name") for r in releases for g in r.get("genres") or []),
        release_languages=flatten((r.get("textRepresentation") or {}).get("language") for r in releases),
        release_scripts=flatten((r.get("textRepresentation") or {}).get("script") for r in releases),
    )

# creates a csv file and writes its respective header if it doesn't already exist.
def ensure_csv_files_exist():
    for file_name, header in CSV_FILE_HEADERS.items():
        if not os.path.exists(f"./{file_name}"):
            print(f"Creating CSV: ./{file_name}")
            with open(f"./{file_name}", "w") as file:
                file.write(f"{header}\n")
        else:
            print(f"Found CSV: ./{file_name}")

# writes an individual dataclass record to the specified file
def log_record(file_name: str, record, record_type):
    with open(file_name, mode="a") as file:
        writer = DataclassWriter(file, [record], record_type)
        writer.write(skip_header=True)

# writes the current app state to respective CSV files. data that couldn't be fetched (None) is skipped.
def log_state(state: AppState):
    records = [
        ("./now_playing.csv", state.now_playing, KcprResponse),
        ("./track_analysis.csv", state.current_track_analysis, TrackAnalysis),
        ("./track_metadata.csv", state.current_track_metadata, TrackMetadata),
        ("./weather.csv", state.current_weather, WeatherResponse),
    ]
    for file_name, record, record_type in records:
        if record is not None:
            log_record(file_name, record, record_type)