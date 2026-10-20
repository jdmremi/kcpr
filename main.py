from dataclasses import dataclass, fields
from dataclass_csv import DataclassWriter
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
import requests
import xml.etree.ElementTree as ET

# load env vars
load_dotenv()

@dataclass
class KcprResponse:
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
    visibility: int
    wind_speed: float
    wind_deg: int
    wind_gust: float | None
    clouds: int
    dt: int
    timezone: int
    sys_type: int
    sys_id: int
    country: str
    sunrise: int
    sunset: int
    id: int
    name: str
    cod: int

@dataclass
class TrackAnalysis:
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

OPENWEATHER_API_KEY: str = os.environ["OPENWEATHER_API_KEY"]
SOUNDNET_API_KEY: str = os.environ["SOUNDNET_API_KEY"]

KCPR_NOW_PLAYING_URL: str = "https://streamdb8web.securenetsystems.net/player_status_update/KCPR1.xml"

# use safari user agent to "mimic" a browser request... this doesn't mimic browser requests entirely but is okay enough
KCPR_REQUEST_HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.6.2 Safari/605.1.15",
}

# latitude/longitude of cal poly graphic arts building
CAL_POLY_LAT, CAL_POLY_LON = 35.29929042318235, -120.66171542472954
OPENWEATHER_API_URL_BASE: str = "https://api.openweathermap.org/data/2.5/weather"

SOUNDNET_API_URL_BASE: str = "https://track-analysis.p.rapidapi.com/pktx"
SOUNDNET_REQUEST_HEADERS: dict[str, str] = {
    "x-rapidapi-host": "track-analysis.p.rapidapi.com",
    "x-rapidapi-key": SOUNDNET_API_KEY,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.6.2 Safari/605.1.15",
    "accept": "application/json",
}

# headers for csv
KCPR_CSV_HEADER: str = ",".join([f.name for f in fields(KcprResponse)])
TRACK_ANALYSIS_CSV_HEADER: str = ",".join([f.name for f in fields(TrackAnalysis)])
TRACK_METADATA_CSV_HEADER: str = ",".join([f.name for f in fields(TrackMetadata)])
WEATHER_CSV_HEADER: str = ",".join([f.name for f in fields(WeatherResponse)])

# returns the currently playing song from KCPR.
def get_now_playing(session: requests.Session):
    res = session.get(KCPR_NOW_PLAYING_URL, headers=KCPR_REQUEST_HEADERS, timeout=10)

    res.raise_for_status()
    data = ET.fromstring(res.content)

    # strips whitespace from tag value
    def get_text(tag: str) -> str | None:
        value = data.findtext(tag)
        return value.strip() or None if value is not None else None

    return KcprResponse(
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
        is_ad=("KCPR Cal Poly Radio. Where Different Matters." in (get_text("title") or "")),
    )

# returns the current weather
def get_current_weather():
    res = requests.get(OPENWEATHER_API_URL_BASE, params={
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
        visibility=data["visibility"],
        wind_speed=wind["speed"],
        wind_deg=wind["deg"],
        wind_gust=wind.get("gust"),
        clouds=data["clouds"]["all"],
        dt=data["dt"],
        timezone=data["timezone"],
        sys_type=sys["type"],
        sys_id=sys["id"],
        country=sys["country"],
        sunrise=sys["sunrise"],
        sunset=sys["sunset"],
        id=data["id"],
        name=data["name"],
        cod=data["cod"],
    )

# returns track an analysis from the SoundNet API for the provided KcprResponse
def get_track_analysis(session: requests.Session, kcpr_response: KcprResponse):
    res = session.get("https://track-analysis.p.rapidapi.com/pktx/analysis", params={
        "song": kcpr_response.title,
        "artist": kcpr_response.artist,
    }, headers=SOUNDNET_REQUEST_HEADERS, timeout=10)

    res.raise_for_status()
    data = res.json()

    return TrackAnalysis(
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
def get_track_metadata(session: requests.Session, kcpr_response: KcprResponse):
    res = session.get(f"{SOUNDNET_API_URL_BASE}/metadata/track", params={
        "name": kcpr_response.title,
        "artist": kcpr_response.artist,
        "album": kcpr_response.album,
    }, headers=SOUNDNET_REQUEST_HEADERS, timeout=10)

    res.raise_for_status()
    data = res.json()

    # flattens a list into a " | " delimited string
    flatten = lambda values:  " | ".join(str(value) for value in dict.fromkeys(values) if value is not None and value != "")

    credits = data.get("artistCredit") or []
    artist = (credits[0].get("artist") or {}) if credits else {}
    releases = data.get("releases") or []

    return TrackMetadata(
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

def log_record(file_name: str, record: KcprResponse | WeatherResponse):
    with open(file_name, mode="a") as file:
        writer = DataclassWriter(file, [record], type(record))
        writer.write()