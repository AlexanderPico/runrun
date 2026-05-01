from __future__ import annotations

import json
import math
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

REPO = Path('/Users/aimee/.openclaw/git/AlexanderPico/runrun')
DATA_DIR = REPO / 'data'
DATA_DIR.mkdir(exist_ok=True)
JSON_PATH = DATA_DIR / 'athlete-diary.json'
JS_PATH = DATA_DIR / 'athlete-diary.js'
GEOCODE_CACHE_PATH = DATA_DIR / 'geocode-cache.json'
WEATHER_CACHE_PATH = DATA_DIR / 'weather-cache.json'

ATHLETE_ID = 92157185
ATHLETE_PAGE = f'https://www.athlinks.com/athletes/{ATHLETE_ID}'
ATHLINKS_BASE = 'https://alaska.athlinks.com'
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def save_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')


GEOCODE_CACHE: dict[str, Any] = load_json(GEOCODE_CACHE_PATH, {})
WEATHER_CACHE: dict[str, Any] = load_json(WEATHER_CACHE_PATH, {})

WEATHER_START_OVERRIDES = {
    ('Bank of America Chicago Marathon 2010', '2010-10-10'): '2010-10-10T07:30:00',
    ('Davis Turkey Trot', '2022-11-19'): '2022-11-19T08:00:00',
    ('Davis Moonlight Run', '2025-07-12'): '2025-07-12T20:00:00',
    ('J.P. Morgan Chase Corporate Challenge', '2016-09-08'): '2016-09-08T17:00:00',
}

ELEVATION_GAIN_FT_OVERRIDES = {
    ('american river 50-mile endurance run', '50mi trail run'): 6332,
    ('ayala cove trail run 2011', '10mi trail run'): 1380,
    ('ayala cove trail run 2012', '10mi trail run'): 1380,
    ('cinderella trail run', '13.1mi trail run'): 2385,
    ('crystal springs', '13.1mi trail run'): 2190,
    ('crystal springs (summer)', '13.1mi trail run'): 2190,
    ('crystal springs trail run', '13.1mi trail run'): 2190,
    ('golden gate trail run 2012', '13.1mi trail run'): 2550,
    ('leadville trail 10k 2012', '10k trail run'): 475,
    ('montara mountain trail run 2012', '13.1mi trail run'): 2900,
    ('mount diablo trail run', '13.1mi trail run'): 3420,
    ('mount diablo trail run - "when hell freezes over"', '13.1mi trail run'): 4180,
    ('rodeo beach trail run 2009', '8k trail run'): 1055,
    ('salt point trail run', '15k trail run'): 1179,
    ('san lorenzo river trail run', '13.1mi trail run'): 2175,
    ('san lorenzo river trail run 2012', '13.1mi trail run'): 2175,
    ('santa cruz', '13.1mi trail run'): 2425,
    ('santa cruz trail run', '13.1mi trail run'): 2425,
    ('spasm crystal springs trail run', '13.1mi trail run'): 2190,
    ('way too cool', '50k trail run'): 4799,
    ('way too cool 50k', '50k trail run'): 4799,
}


def get_json(url: str, *, params: dict[str, Any] | None = None, timeout: int = 60) -> Any:
    for attempt in range(3):
        try:
            response = SESSION.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError('unreachable')


@dataclass(frozen=True)
class Place:
    city: str
    state: str
    country: str


COUNTRY_CODE_MAP = {
    'USA': 'US',
    'US': 'US',
    'CAN': 'CA',
    'CA': 'CA',
    'DEN': 'DK',
    'DK': 'DK',
}

STATE_NAME_MAP = {
    'AL': 'Alabama',
    'AK': 'Alaska',
    'AZ': 'Arizona',
    'AR': 'Arkansas',
    'CA': 'California',
    'CO': 'Colorado',
    'CT': 'Connecticut',
    'DE': 'Delaware',
    'FL': 'Florida',
    'GA': 'Georgia',
    'HI': 'Hawaii',
    'ID': 'Idaho',
    'IL': 'Illinois',
    'IN': 'Indiana',
    'IA': 'Iowa',
    'KS': 'Kansas',
    'KY': 'Kentucky',
    'LA': 'Louisiana',
    'ME': 'Maine',
    'MD': 'Maryland',
    'MA': 'Massachusetts',
    'MI': 'Michigan',
    'MN': 'Minnesota',
    'MS': 'Mississippi',
    'MO': 'Missouri',
    'MT': 'Montana',
    'NE': 'Nebraska',
    'NV': 'Nevada',
    'NH': 'New Hampshire',
    'NJ': 'New Jersey',
    'NM': 'New Mexico',
    'NY': 'New York',
    'NC': 'North Carolina',
    'ND': 'North Dakota',
    'OH': 'Ohio',
    'OK': 'Oklahoma',
    'OR': 'Oregon',
    'PA': 'Pennsylvania',
    'RI': 'Rhode Island',
    'SC': 'South Carolina',
    'SD': 'South Dakota',
    'TN': 'Tennessee',
    'TX': 'Texas',
    'UT': 'Utah',
    'VT': 'Vermont',
    'VA': 'Virginia',
    'WA': 'Washington',
    'WV': 'West Virginia',
    'WI': 'Wisconsin',
    'WY': 'Wyoming',
    'BC': 'British Columbia',
}

SPECIAL_GEOCODES = {
    ('Angel Island', 'CA', 'USA'): {'latitude': 37.8609, 'longitude': -122.4324, 'name': 'Angel Island', 'country_code': 'US', 'timezone': 'America/Los_Angeles'},
    ('Rodeo Beach', 'CA', 'USA'): {'latitude': 37.8324, 'longitude': -122.5353, 'name': 'Rodeo Beach', 'country_code': 'US', 'timezone': 'America/Los_Angeles'},
    ('Los Altos Hills', 'CA', 'USA'): {'latitude': 37.3791, 'longitude': -122.1375, 'name': 'Los Altos Hills', 'country_code': 'US', 'timezone': 'America/Los_Angeles'},
    ('Clayton Ca', 'CA', 'USA'): {'latitude': 37.941, 'longitude': -121.9358, 'name': 'Clayton', 'country_code': 'US', 'timezone': 'America/Los_Angeles'},
    ('Copenhagen, Denmark', 'COP', 'DEN'): {'latitude': 55.6759, 'longitude': 12.5655, 'name': 'Copenhagen', 'country_code': 'DK', 'timezone': 'Europe/Copenhagen'},
}


def iso_date(value: str | None) -> str | None:
    return value[:10] if value else None


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)
    except ValueError:
        return None


def ticks_to_hms(ms: int | float | None) -> str | None:
    if ms is None:
        return None
    seconds = int(round(ms / 1000))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f'{h}:{m:02d}:{s:02d}'


def meters_to_km(meters: float | None) -> float | None:
    return round(meters / 1000, 3) if meters not in (None, 0) else (0 if meters == 0 else None)


def meters_to_miles(meters: float | None) -> float | None:
    return round(meters / 1609.344, 3) if meters not in (None, 0) else (0 if meters == 0 else None)


def normalize_lookup(value: str | None) -> str:
    return ' '.join((value or '').strip().lower().split())


def elevation_gain_ft_for(race_name: str | None, course_pattern: str | None) -> int | None:
    return ELEVATION_GAIN_FT_OVERRIDES.get((normalize_lookup(race_name), normalize_lookup(course_pattern)))


def pace_per_unit(ms: int | None, meters: float | None, unit: str) -> str | None:
    if not ms or not meters:
        return None
    divisor = meters / (1609.344 if unit == 'mile' else 1000)
    if not divisor:
        return None
    seconds = int(round((ms / 1000) / divisor))
    return f'{seconds // 60}:{seconds % 60:02d}'


def rank_pct(rank: int | None, count: int | None) -> float | None:
    if not rank or not count:
        return None
    return round((rank / count) * 100, 1)


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys))
    if not denx or not deny:
        return None
    return round(num / (denx * deny), 3)


def course_for(entry: dict[str, Any]) -> dict[str, Any]:
    target = str(entry.get('EventCourseID') or '')
    courses = entry.get('Race', {}).get('Courses') or []
    for course in courses:
        if str(course.get('EventCourseID') or '') == target:
            return course
    return courses[0] if courses else {}


def normalize_place(city: str | None, state: str | None, country: str | None) -> Place:
    return Place((city or '').strip(), (state or '').strip(), (country or '').strip())


def geocode_place(place: Place) -> dict[str, Any] | None:
    key = f'{place.city}|{place.state}|{place.country}'
    if key in GEOCODE_CACHE:
        return GEOCODE_CACHE[key]
    special = SPECIAL_GEOCODES.get((place.city, place.state, place.country))
    if special:
        GEOCODE_CACHE[key] = special
        return special

    country_code = COUNTRY_CODE_MAP.get(place.country, place.country or None)
    normalized_state = STATE_NAME_MAP.get(place.state.upper(), place.state).lower()
    normalized_city = place.city.split(',')[0].strip().lower()
    candidates = [
        place.city,
        f'{place.city} {place.state}'.strip(),
        f'{place.city} {place.state} {place.country}'.strip(),
        place.city.split(',')[0].strip(),
    ]
    result = None
    for query in dict.fromkeys([c for c in candidates if c]):
        params = {'name': query, 'count': 10, 'language': 'en', 'format': 'json'}
        payload = get_json('https://geocoding-api.open-meteo.com/v1/search', params=params)
        shortlisted: list[tuple[int, dict[str, Any]]] = []
        for item in payload.get('results', []):
            if country_code and item.get('country_code') != country_code:
                continue
            admin1 = (item.get('admin1') or '').lower()
            admin2 = (item.get('admin2') or '').lower()
            name = (item.get('name') or '').lower()
            score = 0
            if normalized_city and normalized_city == name:
                score += 5
            elif normalized_city and normalized_city in name:
                score += 2
            if normalized_state and normalized_state in {admin1, admin2, name}:
                score += 7
            elif normalized_state and normalized_state in admin1:
                score += 4
            elif place.state and place.state.lower() in {admin1, admin2, name}:
                score += 3
            if score <= 0:
                continue
            shortlisted.append((score, item))
        if shortlisted:
            shortlisted.sort(key=lambda pair: pair[0], reverse=True)
            item = shortlisted[0][1]
            result = {
                'latitude': item['latitude'],
                'longitude': item['longitude'],
                'name': item.get('name'),
                'country_code': item.get('country_code'),
                'admin1': item.get('admin1'),
                'timezone': item.get('timezone'),
            }
            break
    GEOCODE_CACHE[key] = result
    return result


def weather_key(lat: float, lon: float, start_dt: datetime, hours: int) -> str:
    return f'{lat:.4f}|{lon:.4f}|{start_dt.isoformat()}|{hours}'


def apply_weather_start_override(race_name: str | None, race_dt: datetime | None) -> datetime | None:
    if not race_name or not race_dt:
        return race_dt
    override = WEATHER_START_OVERRIDES.get((race_name, race_dt.strftime('%Y-%m-%d')))
    return parse_dt(override) if override else race_dt


def touched_hour_prefixes(start_dt: datetime, hours: int) -> list[str]:
    end_dt = start_dt + timedelta(hours=hours)
    cursor = start_dt.replace(minute=0, second=0, microsecond=0)
    prefixes: list[str] = []
    while cursor <= end_dt:
        prefixes.append(cursor.strftime('%Y-%m-%dT%H:00'))
        cursor += timedelta(hours=1)
    return prefixes


def day_period_for_start(start_dt: datetime) -> tuple[str, str]:
    return ('night', 'Night race') if start_dt.time() > datetime.strptime('17:00', '%H:%M').time() else ('day', 'Day race')


def summarize_weather(payload: dict[str, Any], start_dt: datetime, hours: int) -> dict[str, Any] | None:
    hourly = payload.get('hourly') or {}
    times = hourly.get('time') or []
    if not times:
        return None
    race_date = start_dt.strftime('%Y-%m-%d')
    target_prefixes = touched_hour_prefixes(start_dt, hours)
    indices = [i for i, t in enumerate(times) if t in target_prefixes]
    if not indices:
        indices = [i for i, t in enumerate(times) if t.startswith(f'{race_date}T')][: max(len(target_prefixes), 1)]
    if not indices:
        return None

    def values(name: str) -> list[float]:
        series = hourly.get(name) or []
        return [series[i] for i in indices if i < len(series) and series[i] is not None]

    temp = values('temperature_2m')
    apparent = values('apparent_temperature')
    humidity = values('relative_humidity_2m')
    precip = values('precipitation')
    rain = values('rain')
    snowfall = values('snowfall')
    wind = values('wind_speed_10m')
    cloud = values('cloud_cover')
    day_period, day_period_label = day_period_for_start(start_dt)

    return {
        'source': 'open-meteo',
        'timezone': payload.get('timezone'),
        'race_window_hours': hours,
        'window_start_local': start_dt.isoformat(timespec='minutes'),
        'window_end_local': (start_dt + timedelta(hours=hours)).isoformat(timespec='minutes'),
        'hour_count': len(indices),
        'day_period': day_period,
        'day_period_label': day_period_label,
        'temperature_f_start': temp[0] if temp else None,
        'temperature_f_avg': round(statistics.fmean(temp), 1) if temp else None,
        'temperature_f_max': round(max(temp), 1) if temp else None,
        'apparent_temperature_f_avg': round(statistics.fmean(apparent), 1) if apparent else None,
        'humidity_pct_avg': round(statistics.fmean(humidity), 1) if humidity else None,
        'precipitation_in_total': round(sum(precip), 3) if precip else 0.0,
        'rain_in_total': round(sum(rain), 3) if rain else 0.0,
        'snowfall_in_total': round(sum(snowfall), 3) if snowfall else 0.0,
        'wind_mph_avg': round(statistics.fmean(wind), 1) if wind else None,
        'wind_mph_max': round(max(wind), 1) if wind else None,
        'cloud_cover_pct_avg': round(statistics.fmean(cloud), 1) if cloud else None,
        'condition_flags': {
            'rainy': bool(sum(rain) > 0.02 if rain else False),
            'snowy': bool(sum(snowfall) > 0 if snowfall else False),
            'hot': bool((statistics.fmean(temp) if temp else 0) >= 68),
            'cold': bool((statistics.fmean(temp) if temp else 999) <= 45),
            'windy': bool((statistics.fmean(wind) if wind else 0) >= 12),
            'humid': bool((statistics.fmean(humidity) if humidity else 0) >= 75),
        },
        'hourly_sample': [
            {
                'time': times[i],
                'temperature_f': hourly.get('temperature_2m', [None])[i],
                'apparent_temperature_f': hourly.get('apparent_temperature', [None])[i],
                'humidity_pct': hourly.get('relative_humidity_2m', [None])[i],
                'rain_in': hourly.get('rain', [None])[i],
                'precipitation_in': hourly.get('precipitation', [None])[i],
                'wind_mph': hourly.get('wind_speed_10m', [None])[i],
                'cloud_cover_pct': hourly.get('cloud_cover', [None])[i],
            }
            for i in indices
        ],
        'api_url': 'https://archive-api.open-meteo.com/v1/archive?' + urlencode({
            'latitude': payload.get('latitude'),
            'longitude': payload.get('longitude'),
            'start_date': race_date,
            'end_date': race_date,
            'hourly': 'temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,rain,snowfall,wind_speed_10m,cloud_cover',
            'temperature_unit': 'fahrenheit',
            'wind_speed_unit': 'mph',
            'precipitation_unit': 'inch',
            'timezone': payload.get('timezone') or 'auto',
        }),
    }


def fetch_weather(geo: dict[str, Any] | None, race_dt: datetime | None, finish_time_ms: int | None, race_name: str | None = None) -> dict[str, Any] | None:
    if not geo or not race_dt:
        return None
    race_dt = apply_weather_start_override(race_name, race_dt)
    race_date = race_dt.strftime('%Y-%m-%d')
    hours = max(1, min(6, int(math.ceil((finish_time_ms or 7200000) / 3600000))))
    key = weather_key(geo['latitude'], geo['longitude'], race_dt, hours)
    if key in WEATHER_CACHE:
        cached = dict(WEATHER_CACHE[key])
        if 'day_period' not in cached or 'day_period_label' not in cached:
            day_period, day_period_label = day_period_for_start(race_dt)
            cached['day_period'] = day_period
            cached['day_period_label'] = day_period_label
            WEATHER_CACHE[key] = cached
        return cached
    params = {
        'latitude': geo['latitude'],
        'longitude': geo['longitude'],
        'start_date': race_date,
        'end_date': race_date,
        'hourly': 'temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,rain,snowfall,wind_speed_10m,cloud_cover',
        'temperature_unit': 'fahrenheit',
        'wind_speed_unit': 'mph',
        'precipitation_unit': 'inch',
        'timezone': geo.get('timezone') or 'auto',
    }
    payload = get_json('https://archive-api.open-meteo.com/v1/archive', params=params)
    payload['latitude'] = geo['latitude']
    payload['longitude'] = geo['longitude']
    summary = summarize_weather(payload, race_dt, hours)
    WEATHER_CACHE[key] = summary
    time.sleep(0.08)
    return summary


def bin_label(value: float | None, *, cuts: list[tuple[float, str]], default: str) -> str:
    if value is None:
        return default
    for cutoff, label in cuts:
        if value < cutoff:
            return label
    return cuts[-1][1]


def avg_or_none(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    return round(statistics.fmean(values), 2) if values else None


def build() -> dict[str, Any]:
    profile = get_json(f'{ATHLINKS_BASE}/Athletes/Api/{ATHLETE_ID}')['Result']
    summary = get_json(f'{ATHLINKS_BASE}/Athletes/Api/{ATHLETE_ID}/Summary')['Result']
    races_resp = get_json(f'{ATHLINKS_BASE}/athletes/api/{ATHLETE_ID}/Races')['Result']
    races = races_resp['raceEntries']['List']

    normalized_results: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for entry in races:
        race = entry.get('Race') or {}
        course = course_for(entry)
        meters = course.get('DistUnit')
        race_dt = parse_dt(race.get('RaceDate'))
        place = normalize_place(race.get('City') or entry.get('City'), race.get('StateProvAbbrev') or entry.get('StateProv'), race.get('CountryID3') or entry.get('CountryID3'))
        geo = geocode_place(place)
        weather = fetch_weather(geo, race_dt, entry.get('Ticks'), race.get('RaceName') or race.get('EventName'))
        elevation_gain_ft = elevation_gain_ft_for(race.get('RaceName'), course.get('CoursePattern'))
        normalized_results.append({
            'entry_id': entry.get('EntryID'),
            'entry_unique_id': entry.get('EntryUniqueID'),
            'athlete_id': entry.get('RacerID') or profile.get('RacerID'),
            'event_id': entry.get('EventID'),
            'event_course_id': entry.get('EventCourseID'),
            'course_id': entry.get('CourseID') or course.get('CourseID'),
            'master_event_id': race.get('MasterEventID'),
            'race_id': race.get('RaceID'),
            'race_name': race.get('RaceName'),
            'master_name': race.get('MasterName'),
            'course_name': entry.get('CourseName') or course.get('CourseName'),
            'course_pattern': course.get('CoursePattern'),
            'course_pattern_id': course.get('CoursePatternID'),
            'race_category_id': course.get('RaceCatID'),
            'race_category': course.get('RaceCatDesc'),
            'distance_meters': meters,
            'distance_km': meters_to_km(meters),
            'distance_miles': meters_to_miles(meters),
            'elevation_gain_ft': elevation_gain_ft,
            'race_date': race.get('RaceDate'),
            'race_date_local': iso_date(race.get('RaceDate')),
            'status': 'completed' if race_dt and race_dt <= now else 'upcoming',
            'finish_time_ms': entry.get('Ticks'),
            'finish_time': entry.get('TicksString') or ticks_to_hms(entry.get('Ticks')),
            'pace_per_mile': pace_per_unit(entry.get('Ticks'), meters, 'mile'),
            'pace_per_km': pace_per_unit(entry.get('Ticks'), meters, 'km'),
            'pace_seconds_per_mile': round((entry.get('Ticks') or 0) / 1000 / (meters / 1609.344), 2) if entry.get('Ticks') and meters else None,
            'pace_seconds_per_km': round((entry.get('Ticks') or 0) / 1000 / (meters / 1000), 2) if entry.get('Ticks') and meters else None,
            'rank_overall': entry.get('RankO') or entry.get('Rank'),
            'rank_gender': entry.get('RankG'),
            'rank_age_group': entry.get('RankA'),
            'field_size_overall': entry.get('CountO'),
            'field_size_gender': entry.get('CountG'),
            'field_size_age_group': entry.get('CountA'),
            'overall_percentile': rank_pct(entry.get('RankO') or entry.get('Rank'), entry.get('CountO')),
            'gender_percentile': rank_pct(entry.get('RankG'), entry.get('CountG')),
            'age_group_percentile': rank_pct(entry.get('RankA'), entry.get('CountA')),
            'bib': entry.get('BibNum'),
            'age_on_race_day': entry.get('Age'),
            'gender': entry.get('Gender'),
            'city': race.get('City') or entry.get('City'),
            'state': race.get('StateProvAbbrev') or entry.get('StateProv'),
            'state_name': race.get('StateProvName'),
            'country': race.get('CountryID3') or entry.get('CountryID3'),
            'country_name': race.get('CountryName'),
            'is_virtual': bool(entry.get('IsVirtual')),
            'is_member_result': bool(entry.get('IsMember')),
            'points': entry.get('Points'),
            'geo': geo,
            'weather': weather,
            'source_urls': {
                'athlete': ATHLETE_PAGE,
                'profile_api': f'{ATHLINKS_BASE}/Athletes/Api/{ATHLETE_ID}',
                'summary_api': f'{ATHLINKS_BASE}/Athletes/Api/{ATHLETE_ID}/Summary',
                'races_api': f'{ATHLINKS_BASE}/athletes/api/{ATHLETE_ID}/Races',
            },
            'raw_entry': entry,
            'raw_course': course,
        })

    normalized_results.sort(key=lambda r: r['race_date'] or '', reverse=True)
    completed = [r for r in normalized_results if r['status'] == 'completed']
    completed_dates = [r['race_date_local'] for r in completed if r['race_date_local']]
    first_date = min(completed_dates) if completed_dates else None
    last_date = max(completed_dates) if completed_dates else None
    years_active = int(last_date[:4]) - int(first_date[:4]) + 1 if first_date and last_date else None

    personal_records = []
    for pr in summary.get('distanceSummary') or []:
        cp = pr.get('CoursePattern') or {}
        rating = pr.get('Rating') or {}
        personal_records.append({
            'event_name': pr.get('EventName'),
            'event_date': iso_date(pr.get('EventDate')),
            'distance_label': cp.get('OuterName') or cp.get('Description'),
            'distance_description': cp.get('Description'),
            'distance_meters': cp.get('Distance'),
            'distance_km': meters_to_km(cp.get('Distance')),
            'distance_miles': meters_to_miles(cp.get('Distance')),
            'course_pattern_id': cp.get('Id'),
            'course_category': cp.get('CourseCategoryFull'),
            'result_count': rating.get('ResultCount'),
            'best_time_ms': rating.get('BestTicks'),
            'best_time': ticks_to_hms(rating.get('BestTicks')),
            'average_time_ms': rating.get('AverageTicks'),
            'average_time': ticks_to_hms(rating.get('AverageTicks')),
            'rating_overall_top_percent': rating.get('RatingO'),
            'rating_age_top_percent': rating.get('RatingA'),
            'rating_gender_top_percent': rating.get('RatingG'),
            'best_event_id': rating.get('BestEventID'),
            'best_course_id': rating.get('BestCourseID'),
            'best_entry_id': rating.get('BestEntryID'),
            'best_event_course_id': rating.get('BestECID'),
            'raw': pr,
        })
    personal_records.sort(key=lambda r: (r['distance_meters'] or 0), reverse=True)

    category_counter = Counter(r.get('race_category') or 'Unknown' for r in normalized_results)
    distance_counter = Counter(r.get('course_pattern') or r.get('course_name') or 'Unknown' for r in normalized_results)
    state_counter = Counter((r.get('state_name') or r.get('state') or 'Unknown') for r in normalized_results)

    year_rows = defaultdict(lambda: {'race_count': 0, 'miles': 0.0, 'best_time_ms': None, 'road_count': 0, 'trail_count': 0})
    for r in completed:
        year = (r.get('race_date_local') or '0000')[:4]
        row = year_rows[year]
        row['race_count'] += 1
        row['miles'] += float(r.get('distance_miles') or 0)
        if r.get('race_category') == 'Running':
            row['road_count'] += 1
        if r.get('race_category') == 'Trail Running':
            row['trail_count'] += 1
        if r.get('finish_time_ms') and (row['best_time_ms'] is None or r['finish_time_ms'] < row['best_time_ms']):
            row['best_time_ms'] = r['finish_time_ms']

    yearly = []
    for year in sorted(year_rows):
        row = year_rows[year]
        yearly.append({
            'year': int(year),
            'race_count': row['race_count'],
            'miles': round(row['miles'], 1),
            'best_time_ms': row['best_time_ms'],
            'best_time': ticks_to_hms(row['best_time_ms']) if row['best_time_ms'] else None,
            'road_count': row['road_count'],
            'trail_count': row['trail_count'],
        })

    best_by_pattern = {}
    pattern_baselines: dict[str, list[float]] = defaultdict(list)
    for r in completed:
        if r.get('pace_seconds_per_mile') and r.get('course_pattern'):
            pattern_baselines[r['course_pattern']].append(r['pace_seconds_per_mile'])
    pattern_avg = {k: statistics.fmean(v) for k, v in pattern_baselines.items() if len(v) >= 3}

    for r in completed:
        key = (r.get('course_pattern') or r.get('course_name') or 'Unknown', r.get('distance_meters') or 0)
        cur = best_by_pattern.get(key)
        if r.get('finish_time_ms') and (cur is None or r['finish_time_ms'] < cur['best_time_ms']):
            best_by_pattern[key] = {
                'label': key[0],
                'distance_meters': key[1],
                'distance_km': r.get('distance_km'),
                'distance_miles': r.get('distance_miles'),
                'best_time_ms': r['finish_time_ms'],
                'best_time': r['finish_time'],
                'race_name': r['race_name'],
                'race_date': r['race_date_local'],
                'race_category': r['race_category'],
            }
        baseline = pattern_avg.get(r.get('course_pattern') or '')
        if baseline and r.get('pace_seconds_per_mile'):
            r['pace_vs_pattern_baseline_pct'] = round(((r['pace_seconds_per_mile'] - baseline) / baseline) * 100, 1)
        else:
            r['pace_vs_pattern_baseline_pct'] = None

    weather_results = [r for r in completed if r.get('weather') and r.get('pace_seconds_per_mile')]
    with_weather = len(weather_results)

    temp_bins = defaultdict(list)
    rain_bins = defaultdict(list)
    wind_bins = defaultdict(list)
    humidity_bins = defaultdict(list)
    scatter = []
    for r in weather_results:
        weather = r['weather']
        temp = weather.get('temperature_f_avg')
        rain = weather.get('rain_in_total')
        wind = weather.get('wind_mph_avg')
        humidity = weather.get('humidity_pct_avg')
        pace = r['pace_seconds_per_mile']
        delta = r.get('pace_vs_pattern_baseline_pct')
        temp_bins[bin_label(temp, cuts=[(45, '<45°F'), (55, '45–54°F'), (65, '55–64°F'), (75, '65–74°F'), (999, '75°F+')], default='Unknown')].append((pace, delta))
        rain_bins['Rainy' if (rain or 0) > 0.02 else 'Dry'].append((pace, delta))
        wind_bins[bin_label(wind, cuts=[(6, '<6 mph'), (10, '6–9 mph'), (14, '10–13 mph'), (999, '14+ mph')], default='Unknown')].append((pace, delta))
        humidity_bins[bin_label(humidity, cuts=[(50, '<50%'), (65, '50–64%'), (75, '65–74%'), (999, '75%+')], default='Unknown')].append((pace, delta))
        scatter.append({
            'race_name': r['race_name'],
            'race_date': r['race_date_local'],
            'course_pattern': r['course_pattern'],
            'day_period': weather.get('day_period'),
            'day_period_label': weather.get('day_period_label'),
            'temperature_f': temp,
            'rain_in': rain,
            'wind_mph': wind,
            'humidity_pct': humidity,
            'elevation_gain_ft': r.get('elevation_gain_ft'),
            'pace_seconds_per_mile': pace,
            'pace_vs_pattern_baseline_pct': delta,
        })

    def summarize_bucket(source: dict[str, list[tuple[float, float | None]]]) -> list[dict[str, Any]]:
        out = []
        for label, pairs in source.items():
            paces = [p for p, _ in pairs]
            deltas = [d for _, d in pairs if d is not None]
            out.append({
                'label': label,
                'race_count': len(pairs),
                'avg_pace_seconds_per_mile': round(statistics.fmean(paces), 1) if paces else None,
                'avg_pace_vs_pattern_baseline_pct': round(statistics.fmean(deltas), 1) if deltas else None,
            })
        return out

    correlations = {
        'temperature_vs_pace_seconds_per_mile': pearson([r['weather']['temperature_f_avg'] for r in weather_results if r['weather'].get('temperature_f_avg') is not None], [r['pace_seconds_per_mile'] for r in weather_results if r['weather'].get('temperature_f_avg') is not None]),
        'wind_vs_pace_seconds_per_mile': pearson([r['weather']['wind_mph_avg'] for r in weather_results if r['weather'].get('wind_mph_avg') is not None], [r['pace_seconds_per_mile'] for r in weather_results if r['weather'].get('wind_mph_avg') is not None]),
        'humidity_vs_pace_seconds_per_mile': pearson([r['weather']['humidity_pct_avg'] for r in weather_results if r['weather'].get('humidity_pct_avg') is not None], [r['pace_seconds_per_mile'] for r in weather_results if r['weather'].get('humidity_pct_avg') is not None]),
    }

    payload = {
        'meta': {
            'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'repo': str(REPO),
            'source_site': 'Athlinks',
            'athlete_page': ATHLETE_PAGE,
            'source_apis': {
                'profile': f'{ATHLINKS_BASE}/Athletes/Api/{ATHLETE_ID}',
                'summary': f'{ATHLINKS_BASE}/Athletes/Api/{ATHLETE_ID}/Summary',
                'races': f'{ATHLINKS_BASE}/athletes/api/{ATHLETE_ID}/Races',
            },
            'weather_sources': {
                'geocoding': 'https://geocoding-api.open-meteo.com/v1/search',
                'archive': 'https://archive-api.open-meteo.com/v1/archive',
            },
            'scrape_scope': ['Overview', 'Results', 'Stats'],
            'notes': [
                'Athlinks profile API reports Elisa Park as age 45; requested diary persona is 46-year-old female.',
                'EventDate was blank in race entries, so Race.RaceDate was used for chronology.',
                'Historical weather is inferred from Open-Meteo archive data using geocoded race city/state/country plus the race start hour and a capped finish-duration window.',
                'Trail elevation_gain_ft is manually filled where official course pages or race PDFs exposed trustworthy climb totals.',
                'A local JS mirror is generated from this JSON so the diary opens under file:// without fetch/CORS issues.',
            ],
        },
        'athlete': {
            'athlete_id': profile.get('RacerID'),
            'display_name': profile.get('DisplayName'),
            'first_name': profile.get('FName'),
            'last_name': profile.get('LName'),
            'gender': 'Female' if profile.get('Gender') == 'F' else profile.get('Gender'),
            'requested_age': 46,
            'athlinks_display_age': profile.get('Age'),
            'city': profile.get('City'),
            'state': profile.get('StateProvAbbrev'),
            'state_name': profile.get('StateProvName'),
            'country': profile.get('CountryID3'),
            'country_name': profile.get('CountryName'),
            'join_date': profile.get('JoinDate'),
            'is_member': profile.get('IsMember'),
            'result_count': profile.get('ResultCount'),
            'aesthetic': 'clean white background with Quince-inspired warm neutrals and black cat detail',
        },
        'overview': {
            'total_races': summary.get('resultsSummary', {}).get('TotalRaces'),
            'miles_raced': round(summary.get('resultsSummary', {}).get('MilesRaced', 0), 1),
            'kilometers_raced': round(summary.get('resultsSummary', {}).get('MilesRaced', 0) * 1.609344, 1),
            'years_active': years_active,
            'first_race_date': first_date,
            'latest_race_date': last_date,
            'upcoming_race_count': len([r for r in normalized_results if r['status'] == 'upcoming']),
            'road_races': category_counter.get('Running', 0),
            'trail_races': category_counter.get('Trail Running', 0),
            'adventure_races': category_counter.get('Adventure Racing', 0),
            'race_categories': [{'label': label, 'count': count} for label, count in sorted(category_counter.items(), key=lambda kv: (-kv[1], kv[0]))],
            'weather_coverage_count': with_weather,
            'weather_coverage_pct': round((with_weather / len(completed)) * 100, 1) if completed else 0,
        },
        'stats': {
            'personal_records': personal_records,
            'yearly_breakdown': yearly,
            'best_by_pattern': sorted(best_by_pattern.values(), key=lambda r: (r['distance_meters'] or 0), reverse=True),
            'top_course_patterns': [{'label': label, 'count': count} for label, count in distance_counter.most_common(12)],
            'top_states': [{'label': label, 'count': count} for label, count in state_counter.most_common(10)],
            'weather_analysis': {
                'coverage_count': with_weather,
                'coverage_note': 'Only completed races with resolvable geocodes and archive weather are included.',
                'temperature_bins': summarize_bucket(temp_bins),
                'rain_comparison': summarize_bucket(rain_bins),
                'wind_bins': summarize_bucket(wind_bins),
                'humidity_bins': summarize_bucket(humidity_bins),
                'correlations': correlations,
                'scatter_points': scatter,
                'notable_races': {
                    'hottest': max((r for r in weather_results if r['weather'].get('temperature_f_avg') is not None), key=lambda r: r['weather']['temperature_f_avg'], default=None),
                    'coldest': min((r for r in weather_results if r['weather'].get('temperature_f_avg') is not None), key=lambda r: r['weather']['temperature_f_avg'], default=None),
                    'wettest': max((r for r in weather_results if r['weather'].get('rain_in_total') is not None), key=lambda r: r['weather']['rain_in_total'], default=None),
                    'windiest': max((r for r in weather_results if r['weather'].get('wind_mph_avg') is not None), key=lambda r: r['weather']['wind_mph_avg'], default=None),
                },
            },
        },
        'results': normalized_results,
        'raw': {
            'profile': profile,
            'summary': summary,
            'races_metadata': {
                'raceEntries_MasterCount': races_resp['raceEntries'].get('MasterCount'),
                'inReviewRaceEntries_count': len(races_resp.get('inReviewRaceEntries') or []),
                'unofficialEntries_count': len(races_resp.get('unofficialEntries') or []),
            },
        },
    }
    return payload


def main() -> None:
    payload = build()
    save_json(GEOCODE_CACHE_PATH, GEOCODE_CACHE)
    save_json(WEATHER_CACHE_PATH, WEATHER_CACHE)
    JSON_PATH.write_text(json.dumps(payload, indent=2) + '\n')
    JS_PATH.write_text('globalThis.RUNRUN_DIARY_DATA = ' + json.dumps(payload, indent=2) + ';\n')
    print(json.dumps({
        'json_path': str(JSON_PATH),
        'js_path': str(JS_PATH),
        'geocode_cache_path': str(GEOCODE_CACHE_PATH),
        'weather_cache_path': str(WEATHER_CACHE_PATH),
        'results': len(payload['results']),
        'weather_coverage_count': payload['overview']['weather_coverage_count'],
        'weather_coverage_pct': payload['overview']['weather_coverage_pct'],
    }, indent=2))


if __name__ == '__main__':
    main()
