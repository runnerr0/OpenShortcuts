"""Shared tool definitions for the Morning Briefing agent.

These tools are used across all hosting strategies. Each tool is a plain
Python function that makes an API call and returns structured data.

The TOOL_SCHEMAS list defines the tools in OpenAI function-calling format,
which is also compatible with Bedrock action groups and LangGraph.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta


# --- Tool Schemas (OpenAI function-calling format) ---

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather conditions and forecast for a location. Returns temperature, conditions, humidity, wind, and a short forecast.",
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "Latitude of the location",
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude of the location",
                    },
                },
                "required": ["latitude", "longitude"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "Get top news headlines. Optionally filter by topic/category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "News category: general, business, technology, sports, science, health, entertainment",
                        "enum": [
                            "general",
                            "business",
                            "technology",
                            "sports",
                            "science",
                            "health",
                            "entertainment",
                        ],
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of headlines to return (default 5, max 10)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_calendar_events",
            "description": "Get today's calendar events and meetings. Returns a list of events with times, titles, and locations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (default: today)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_commute_time",
            "description": "Get estimated travel time between two locations in current traffic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin_lat": {"type": "number", "description": "Origin latitude"},
                    "origin_lon": {"type": "number", "description": "Origin longitude"},
                    "destination": {
                        "type": "string",
                        "description": "Destination address or place name",
                    },
                },
                "required": ["origin_lat", "origin_lon", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time_context",
            "description": "Get the current date, time, day of week, and time-of-day context (morning/afternoon/evening).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# --- Tool Implementations ---


def get_weather(latitude, longitude):
    """Fetch weather from Open-Meteo (free, no API key required)."""
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}&longitude={longitude}"
        f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
        f"weather_code,wind_speed_10m"
        f"&daily=temperature_2m_max,temperature_2m_min,weather_code,"
        f"precipitation_probability_max"
        f"&temperature_unit=fahrenheit"
        f"&wind_speed_unit=mph"
        f"&timezone=auto"
        f"&forecast_days=2"
    )
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        current = data.get("current", {})
        daily = data.get("daily", {})

        # Map WMO weather codes to descriptions
        weather_codes = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy",
            3: "Overcast", 45: "Foggy", 48: "Depositing rime fog",
            51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
            61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
            71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
            80: "Slight rain showers", 81: "Moderate rain showers",
            82: "Violent rain showers", 95: "Thunderstorm",
        }
        code = current.get("weather_code", 0)
        condition = weather_codes.get(code, f"Code {code}")

        return {
            "current_temp_f": current.get("temperature_2m"),
            "feels_like_f": current.get("apparent_temperature"),
            "condition": condition,
            "humidity_pct": current.get("relative_humidity_2m"),
            "wind_mph": current.get("wind_speed_10m"),
            "today_high_f": daily.get("temperature_2m_max", [None])[0],
            "today_low_f": daily.get("temperature_2m_min", [None])[0],
            "rain_chance_pct": daily.get("precipitation_probability_max", [None])[0],
            "tomorrow_high_f": daily.get("temperature_2m_max", [None, None])[1] if len(daily.get("temperature_2m_max", [])) > 1 else None,
            "tomorrow_condition": weather_codes.get(
                daily.get("weather_code", [0, 0])[1] if len(daily.get("weather_code", [])) > 1 else 0,
                "Unknown",
            ),
        }
    except Exception as e:
        return {"error": str(e)}


def get_news(category="general", count=5):
    """Fetch news headlines.

    Uses a free news API. In production you'd use NewsAPI, Google News RSS,
    or similar. This implementation uses the Hacker News API as a free
    fallback that needs no API key.
    """
    count = min(count or 5, 10)
    try:
        url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            story_ids = json.loads(resp.read())[:count]

        headlines = []
        for sid in story_ids:
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"
            with urllib.request.urlopen(item_url, timeout=5) as resp:
                item = json.loads(resp.read())
                headlines.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "score": item.get("score", 0),
                    "source": "Hacker News",
                })

        return {"headlines": headlines, "count": len(headlines), "category": category}
    except Exception as e:
        return {"error": str(e), "headlines": []}


def get_calendar_events(date=None):
    """Get calendar events for a given date.

    In a real deployment, this would connect to:
    - Apple Calendar via CalDAV
    - Google Calendar API
    - Microsoft Graph API (Outlook)

    For now, returns a placeholder that the agent can work with.
    The setup wizard would configure the actual calendar source.
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # Placeholder — in production, this calls a real calendar API
    return {
        "date": date,
        "events": [],
        "note": "Calendar integration not configured. Run the setup wizard to connect your calendar.",
    }


def get_commute_time(origin_lat, origin_lon, destination):
    """Get commute time estimate.

    In production, this would use:
    - Google Maps Directions API
    - Apple Maps API (MapKit JS)
    - OpenRouteService (free, open source)

    Returns a placeholder for now.
    """
    return {
        "origin": f"{origin_lat}, {origin_lon}",
        "destination": destination,
        "estimate": "Commute integration not configured. Run the setup wizard to connect a maps provider.",
    }


def get_time_context():
    """Get current time context for the briefing."""
    now = datetime.now()
    hour = now.hour

    if hour < 12:
        greeting = "Good morning"
        period = "morning"
    elif hour < 17:
        greeting = "Good afternoon"
        period = "afternoon"
    else:
        greeting = "Good evening"
        period = "evening"

    return {
        "date": now.strftime("%A, %B %d, %Y"),
        "time": now.strftime("%I:%M %p"),
        "day_of_week": now.strftime("%A"),
        "greeting": greeting,
        "period": period,
    }


# --- Tool dispatcher ---

TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "get_news": get_news,
    "get_calendar_events": get_calendar_events,
    "get_commute_time": get_commute_time,
    "get_time_context": get_time_context,
}


def execute_tool(name, arguments):
    """Execute a tool by name with the given arguments dict."""
    if name not in TOOL_FUNCTIONS:
        return {"error": f"Unknown tool: {name}"}
    try:
        return TOOL_FUNCTIONS[name](**arguments)
    except Exception as e:
        return {"error": f"Tool execution failed: {e}"}
