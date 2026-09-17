"""
tools/flight_tool.py
======================

Wraps the AviationStack API (https://aviationstack.com/) so flight_agent
(agent/nodes.py) can turn a free-text travel request like "flights from
Dhaka to Tokyo" into real flight data.

Important limitation to know about: AviationStack's free/basic tier returns
*live flight status* data (airline, flight number, gate, delay, etc.), not
ticket prices. This file (and the prompts in agent/prompts.py) are written
around that limitation — see the disclaimer text in ``search_flights``
below. Getting actual fares would require a different API (e.g. Amadeus).

The bulk of this file (everything before ``search_flights``) is about one
problem: turning a place name typed in natural language ("Japan", "Tokyo",
"from Bangladesh to Japan") into the 3-letter IATA airport code the
AviationStack API actually expects (e.g. "NRT"). That's why there are three
different lookup dictionaries below — countries, country capitals/main
airports, and specific cities.
"""

import os
import re

import airportsdata
import certifi
import pycountry
import requests
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# Force OpenSSL and Python's ssl module to use certifi's trusted CA bundle
os.environ["SSL_CERT_FILE"] = certifi.where()

# Force the 'requests' library to use certifi's trusted CA bundle for SSL verification
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

# Note: this SSL setup is duplicated from agent/config.py. That's because
# this module is also runnable on its own (see the `if __name__ ==
# "__main__":` block at the bottom) without importing the agent package at
# all, so it needs to guarantee its own certificate setup rather than
# relying on some other module having already done it.

API_KEY = os.getenv("AVIATIONSTACK_API_KEY")

# Set the default city you located, you can modify it
DEFAULT_ORIGIN_IATA = os.getenv("DEFAULT_ORIGIN_IATA", "TPE")

BASE_URL = "https://api.aviationstack.com/v1/flights"

# airportsdata ships a static, offline database of airports keyed by IATA
# code (e.g. AIRPORTS["NRT"] -> {"city": "Tokyo", "country": "JP", ...}).
# Loading it once at import time (instead of per-request) keeps every
# lookup below fast.
AIRPORTS = airportsdata.load("IATA")


# Common ways people refer to a country that don't match pycountry's
# official name exactly (nicknames, abbreviations, or a well-known city used
# to mean "the country"). Checked before falling back to pycountry's lookup.
COUNTRY_ALIASES = {
    "usa": "US",
    "u.s.a": "US",
    "u.s.": "US",
    "america": "US",
    "united states": "US",
    "uk": "GB",
    "u.k.": "GB",
    "britain": "GB",
    "england": "GB",
    "uae": "AE",
    "dubai": "AE",
    "south korea": "KR",
    "korea": "KR",
    "russia": "RU",
    "vietnam": "VN",
    "bangladesh": "BD",
    "india": "IN",
    "japan": "JP",
    "china": "CN",
    "singapore": "SG",
    "malaysia": "MY",
    "thailand": "TH",
    "indonesia": "ID",
    "nepal": "NP",
    "qatar": "QA",
    "saudi arabia": "SA",
    "turkey": "TR",
    "canada": "CA",
    "australia": "AU",
    "germany": "DE",
    "france": "FR",
    "italy": "IT",
    "spain": "ES",
    "taiwan": "TW",
    "taipei": "TW",
}

# When someone names a whole country instead of a specific city (e.g. "fly
# to Japan"), we need to pick one representative airport for that country.
# This maps each supported country code to its busiest/most useful
# international airport, so we don't have to guess.
COUNTRY_MAIN_AIRPORT = {
    "BD": "DAC",
    "IN": "DEL",
    "JP": "NRT",
    "US": "JFK",
    "GB": "LHR",
    "AE": "DXB",
    "SG": "SIN",
    "MY": "KUL",
    "TH": "BKK",
    "ID": "CGK",
    "CN": "PEK",
    "KR": "ICN",
    "NP": "KTM",
    "QA": "DOH",
    "SA": "JED",
    "TR": "IST",
    "CA": "YYZ",
    "AU": "SYD",
    "DE": "FRA",
    "FR": "CDG",
    "IT": "FCO",
    "ES": "MAD",
    "TW": "TPE",
}


# Same idea as COUNTRY_MAIN_AIRPORT, but for specific cities mentioned by
# name (e.g. "flights to Tokyo"). Checked before the country-level lookup so
# a named city always wins over a same-named/associated country.
CITY_MAIN_AIRPORT = {
    "dhaka": "DAC",
    "delhi": "DEL",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "kolkata": "CCU",
    "chennai": "MAA",
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "tokyo": "NRT",
    "osaka": "KIX",
    "kyoto": "KIX",
    "new york": "JFK",
    "london": "LHR",
    "dubai": "DXB",
    "singapore": "SIN",
    "kuala lumpur": "KUL",
    "bangkok": "BKK",
    "doha": "DOH",
    "istanbul": "IST",
    "toronto": "YYZ",
    "sydney": "SYD",
    "paris": "CDG",
    "rome": "FCO",
    "madrid": "MAD",
    "frankfurt": "FRA",
    "taipei": "TPE",
}


def clean_text(text: str) -> str:
    """
    Normalize free-text input before trying to match it against a place
    name: lowercase it, strip punctuation, collapse extra whitespace, and
    drop filler words that show up in real travel requests
    ("flight", "trip", "budget", "including", ...) but would otherwise
    confuse an exact string match.

    Args:
        text: Raw text, e.g. "flights to Tokyo including hotels".

    Returns:
        str: Cleaned text, e.g. "tokyo".
    """
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    stop_words = [
        "flight",
        "flights",
        "ticket",
        "tickets",
        "trip",
        "travel",
        "plan",
        "complete",
        "days",
        "day",
        "including",
        "hotel",
        "hotels",
        "sightseeing",
        "under",
        "budget",
        "info",
        "information",
    ]
    words = [w for w in text.split() if w not in stop_words]
    return " ".join(words).strip()


def country_name_to_code(text: str):
    """
    Resolve a cleaned piece of text to a 2-letter country code (ISO 3166-1
    alpha-2, e.g. "JP" for Japan).

    Tries three strategies in order, from cheapest/most specific to most
    exhaustive:
        1. A direct hit in COUNTRY_ALIASES (fast dictionary lookup).
        2. pycountry's own name lookup (handles official names precisely).
        3. Scanning every country name to see if it appears anywhere inside
           the text (handles cases like "trip to japan" where clean_text
           already stripped "trip", but this is a safety net for text that
           wasn't pre-cleaned).

    Args:
        text: Free text that may contain a country name.

    Returns:
        str | None: The 2-letter country code, or None if nothing matched.
    """
    text = clean_text(text)

    if text in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[text]

    try:
        country = pycountry.countries.lookup(text)
        return country.alpha_2
    except LookupError:
        pass

    # Detect country name inside longer text
    for country in pycountry.countries:
        country_name = country.name.lower()
        if country_name in text:
            return country.alpha_2

    for alias, code in COUNTRY_ALIASES.items():
        if alias in text:
            return code

    return None


def airport_country_matches(airport: dict, country_code: str) -> bool:
    """
    Check whether an airport record (from AIRPORTS) belongs to the given
    country code.

    airportsdata stores the country either as a 2-letter code already, or
    (depending on the record) as a full country name, so this checks both
    forms rather than assuming one.

    Args:
        airport: One airport record from AIRPORTS, e.g. AIRPORTS["NRT"].
        country_code: 2-letter country code to compare against, e.g. "JP".

    Returns:
        bool: True if the airport's country matches.
    """
    airport_country = str(airport.get("country", "")).upper().strip()

    if airport_country == country_code:
        return True

    try:
        country = pycountry.countries.get(alpha_2=country_code)
        if country and airport_country.lower() == country.name.lower():
            return True
    except Exception:
        pass

    return False


def get_best_airport_for_country(country_code: str):
    """
    Pick the single best airport to represent a whole country when the
    traveler only named the country (e.g. "flights from Bangladesh").

    First checks the curated COUNTRY_MAIN_AIRPORT map (fast, and avoids
    picking an obscure regional airport). If the country isn't in that map,
    falls back to scanning every airport in that country and scoring it —
    airports with "international" or "intl" in the name score higher, since
    those are far more likely to have real commercial flight traffic than a
    small domestic airstrip.

    Args:
        country_code: 2-letter country code, e.g. "BD".

    Returns:
        str | None: The chosen IATA airport code, or None if the country
        has no airports in the AIRPORTS database.
    """
    preferred = COUNTRY_MAIN_AIRPORT.get(country_code)

    if preferred and preferred in AIRPORTS:
        return preferred

    candidates = []

    for iata, airport in AIRPORTS.items():
        if not iata:
            continue

        if airport_country_matches(airport, country_code):
            name = str(airport.get("name", "")).lower()
            city = str(airport.get("city", "")).lower()

            score = 0

            if "international" in name:
                score += 50
            if "intl" in name:
                score += 40
            if "capital" in name:
                score += 20
            if city:
                score += 5

            candidates.append((score, iata))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][1]


def resolve_location_to_iata(location: str):
    """
    Converts country/city/airport/IATA into IATA code.

    Examples:
    Bangladesh -> DAC
    Japan -> NRT
    Dhaka -> DAC
    Tokyo -> NRT
    DAC -> DAC

    Resolution order: an exact 3-letter IATA code the traveler already typed
    wins immediately; then a known city (CITY_MAIN_AIRPORT); then a known
    country (via country_name_to_code + get_best_airport_for_country);
    finally, a fuzzy scan across every airport's city/name fields for
    anything not covered by the two curated maps above.
    """

    if not location:
        return None

    raw_location = location.strip()

    # Direct IATA code
    if re.fullmatch(r"[A-Za-z]{3}", raw_location):
        code = raw_location.upper()
        if code in AIRPORTS:
            return code

    location_clean = clean_text(raw_location)

    if not location_clean:
        return None

    # City preferred airport
    if location_clean in CITY_MAIN_AIRPORT:
        return CITY_MAIN_AIRPORT[location_clean]

    # Country preferred airport
    country_code = country_name_to_code(location_clean)
    if country_code:
        airport = get_best_airport_for_country(country_code)
        if airport:
            return airport

    # Exact city match from airport database
    city_matches = []

    for iata, airport in AIRPORTS.items():
        city = str(airport.get("city", "")).lower().strip()
        name = str(airport.get("name", "")).lower().strip()

        score = 0

        if city == location_clean:
            score += 100
        elif location_clean in city:
            score += 70

        if location_clean in name:
            score += 50

        if "international" in name:
            score += 10

        if score > 0:
            city_matches.append((score, iata))

    if city_matches:
        city_matches.sort(reverse=True)
        return city_matches[0][1]

    return None


def find_location_mentions(query: str):
    """
    Finds country or city names inside a natural language query.

    This is the fallback used by parse_route() when the query doesn't match
    any of the more specific patterns ("from X to Y", "flights to X", ...):
    it just scans the whole query for any recognizable place name, in the
    order they appear, and lets the caller decide what to do with them.
    """

    q = query.lower()
    mentions = []

    # Country aliases
    for alias in COUNTRY_ALIASES:
        if re.search(rf"\b{re.escape(alias)}\b", q):
            mentions.append(alias)

    # Country names from pycountry
    for country in pycountry.countries:
        name = country.name.lower()
        if len(name) >= 4 and re.search(rf"\b{re.escape(name)}\b", q):
            mentions.append(name)

    # City names from our preferred city map
    for city in CITY_MAIN_AIRPORT:
        if re.search(rf"\b{re.escape(city)}\b", q):
            mentions.append(city)

    # Remove duplicate while keeping order
    unique_mentions = []
    for item in mentions:
        if item not in unique_mentions:
            unique_mentions.append(item)

    return unique_mentions


def parse_route(query: str):
    """
    Figure out the departure and arrival airports (if any) from a free-text
    travel request.

    Tries several patterns in order, from most to least specific:
    1. Explicit "all flights" / "global flights" wording -> no filtering.
    2. Two literal IATA codes typed in the query (e.g. "DAC to NRT").
    3. "from X to Y" phrasing.
    4. "to Y from X" phrasing.
    5. "from X" only (destination unspecified).
    6. "to Y" only (origin unspecified).
    7. Last resort: scan the whole query for any place names at all
       (find_location_mentions) and guess based on how many were found.

    Returns:
    dep_iata, arr_iata

    Can return:
    None, None  -> global live flights
    DAC, NRT    -> filtered route
    DAC, None   -> all flights from DAC
    None, NRT   -> all flights to NRT
    """

    q = query.strip()
    q_lower = q.lower()

    # Global / all-country query
    global_keywords = [
        "all country",
        "all countries",
        "global flight",
        "global flights",
        "all flight",
        "all flights",
        "worldwide flight",
        "worldwide flights",
    ]

    if any(keyword in q_lower for keyword in global_keywords):
        return None, None

    # Direct IATA code route: DAC to NRT
    codes = re.findall(r"\b[A-Z]{3}\b", q)

    if len(codes) >= 2:
        dep = codes[0].upper()
        arr = codes[1].upper()
        return dep, arr

    # Pattern: from X to Y
    match = re.search(
        r"\bfrom\s+(.+?)\s+\bto\s+(.+?)(?:\s+(?:on|for|under|including|with|in|at)\b|[.!?]|$)",
        q_lower,
    )

    if match:
        origin_text = match.group(1)
        dest_text = match.group(2)

        dep_iata = resolve_location_to_iata(origin_text)
        arr_iata = resolve_location_to_iata(dest_text)

        return dep_iata, arr_iata

    # Pattern: to Y from X
    match = re.search(
        r"\bto\s+(.+?)\s+\bfrom\s+(.+?)(?:\s+(?:on|for|under|including|with|in|at)\b|[.!?]|$)",
        q_lower,
    )

    if match:
        dest_text = match.group(1)
        origin_text = match.group(2)

        dep_iata = resolve_location_to_iata(origin_text)
        arr_iata = resolve_location_to_iata(dest_text)

        return dep_iata, arr_iata

    # Pattern: flights from X
    match = re.search(r"\bfrom\s+(.+?)(?:[.!?]|$)", q_lower)

    if match:
        origin_text = match.group(1)
        dep_iata = resolve_location_to_iata(origin_text)
        return dep_iata, None

    # Pattern: flights to X
    match = re.search(r"\bto\s+(.+?)(?:[.!?]|$)", q_lower)

    if match:
        dest_text = match.group(1)
        arr_iata = resolve_location_to_iata(dest_text)
        return None, arr_iata

    # Fallback: find country/city mentions
    mentions = find_location_mentions(q)

    if len(mentions) >= 2:
        dep_iata = resolve_location_to_iata(mentions[0])
        arr_iata = resolve_location_to_iata(mentions[1])
        return dep_iata, arr_iata

    if len(mentions) == 1:
        arr_iata = resolve_location_to_iata(mentions[0])
        return DEFAULT_ORIGIN_IATA, arr_iata

    return None, None


def format_flight(flight: dict):
    """
    Turn one raw AviationStack flight record (a nested dict) into a
    readable, LLM-friendly text block.

    Every field uses ``... or "Unknown ..."`` fallbacks because
    AviationStack frequently returns null for fields that simply weren't
    reported for a given flight (e.g. gate assignment before boarding) —
    without the fallback, this would print the literal string "None" which
    reads badly once it lands inside the itinerary/final prompts.

    Args:
        flight: One item from AviationStack's ``data`` list.

    Returns:
        str: A multi-line, human-readable summary of the flight.
    """
    airline = flight.get("airline", {}).get("name") or "Unknown airline"
    flight_number = flight.get("flight", {}).get("iata") or "Unknown flight number"
    status = flight.get("flight_status") or "Unknown"

    dep = flight.get("departure", {}) or {}
    arr = flight.get("arrival", {}) or {}

    dep_airport = dep.get("airport") or "Unknown departure airport"
    dep_iata = dep.get("iata") or "Unknown"
    dep_terminal = dep.get("terminal") or "N/A"
    dep_gate = dep.get("gate") or "N/A"
    dep_scheduled = dep.get("scheduled") or "Unknown"
    dep_delay = dep.get("delay")
    dep_delay_text = f"{dep_delay} minutes" if dep_delay is not None else "N/A"

    arr_airport = arr.get("airport") or "Unknown arrival airport"
    arr_iata = arr.get("iata") or "Unknown"
    arr_terminal = arr.get("terminal") or "N/A"
    arr_gate = arr.get("gate") or "N/A"
    arr_scheduled = arr.get("scheduled") or "Unknown"
    arr_delay = arr.get("delay")
    arr_delay_text = f"{arr_delay} minutes" if arr_delay is not None else "N/A"

    return f"""
Airline: {airline}
Flight: {flight_number}
Status: {status}

Departure:
- Airport: {dep_airport}
- IATA: {dep_iata}
- Terminal: {dep_terminal}
- Gate: {dep_gate}
- Scheduled: {dep_scheduled}
- Delay: {dep_delay_text}

Arrival:
- Airport: {arr_airport}
- IATA: {arr_iata}
- Terminal: {arr_terminal}
- Gate: {arr_gate}
- Scheduled: {arr_scheduled}
- Delay: {arr_delay_text}
""".strip()


def search_flights(query: str, limit: int = 10):
    """
    Main entry point used by agent/nodes.py::flight_agent.

    Parses the departure/arrival airports out of ``query`` (see
    parse_route), calls the AviationStack ``/flights`` endpoint, and
    returns a plain-text summary ready to drop into an LLM prompt. Every
    failure path (missing API key, network error, bad JSON, API-side
    error, empty results) returns a descriptive string instead of raising,
    so a flight-lookup problem never crashes the whole agent pipeline —
    the LLM will just see and explain the failure to the traveler.

    Args:
        query: The traveler's free-text request.
        limit: Maximum number of flights to fetch/format (AviationStack
            caps this at 100 per request regardless of what's passed).

    Returns:
        str: A human-readable summary of matching flights, or an
        explanatory message if none were found or something went wrong.
    """
    if not API_KEY:
        return (
            "Flight API error: AVIATIONSTACK_API_KEY is missing.\n"
            "Please add this in your .env file:\n"
            "AVIATIONSTACK_API_KEY=your_api_key_here"
        )

    dep_iata, arr_iata = parse_route(query)

    params = {
        "access_key": API_KEY,
        "limit": min(limit, 100),
    }

    if dep_iata:
        params["dep_iata"] = dep_iata

    if arr_iata:
        params["arr_iata"] = arr_iata

    try:
        response = requests.get(BASE_URL, params=params, timeout=30)
        data = response.json()
    except requests.exceptions.RequestException as e:
        return f"Flight API request failed: {e}"
    except ValueError:
        return "Flight API returned invalid JSON."

    if "error" in data:
        error = data["error"]
        return (
            "Flight API error:\n"
            f"Code: {error.get('code', 'Unknown')}\n"
            f"Message: {error.get('message', 'Unknown error')}"
        )

    flight_data = data.get("data", [])

    if not flight_data:
        route_text = ""

        if dep_iata and arr_iata:
            route_text = f" for route {dep_iata} to {arr_iata}"
        elif dep_iata:
            route_text = f" from {dep_iata}"
        elif arr_iata:
            route_text = f" to {arr_iata}"

        return (
            f"No live flight data found{route_text}.\n\n"
            "Note: AviationStack provides live/status flight data, not ticket prices. "
            "For actual fare prices, use a flight-pricing API such as Amadeus."
        )

    route_info = "Global live flights"

    if dep_iata and arr_iata:
        route_info = f"Live flights from {dep_iata} to {arr_iata}"
    elif dep_iata:
        route_info = f"Live flights from {dep_iata}"
    elif arr_iata:
        route_info = f"Live flights to {arr_iata}"

    formatted_flights = [format_flight(flight) for flight in flight_data[:limit]]

    return f"{route_info}\n\n" + "\n\n---\n\n".join(formatted_flights)


if __name__ == "__main__":
    # Lets you sanity-check this module on its own, without starting the
    # full FastAPI app or the LangGraph pipeline:
    #     uv run python tools/flight_tool.py
    print(search_flights("Plan a 7 days Japan trip from Bangladesh"))
    print("\n" + "=" * 80 + "\n")
    print(search_flights("all country flight info"))
