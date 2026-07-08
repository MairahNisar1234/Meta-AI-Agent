"""
realtime_detector.py
====================
Location: app/agents/realtime_detector.py

What it does
------------
1. Analyses the user's agent spec (plain English description).
2. Decides whether the agent needs real-time / live data.
3. If yes  → picks the right FREE API, writes env vars to the GENERATED
             agent's .env (never the project root .env), and returns
             structured config so coder_node uses the right env-vars.
4. If no   → passes through with no changes.

IMPORTANT: This file NEVER touches the project-root .env.
           It writes only to:  <generated_agents_dir>/<agent_name>/.env
           Your OPENROUTER_API_KEY and TAVILY_API_KEY are always safe.

CHANGELOG (multi-endpoint fix)
-------------------------------
Every category used to expose only ONE url ("live_scores"). That meant any
query implying a different time-frame than "right now" (e.g. "matches
played on the 19th", "stock price last Tuesday", "weather last week",
"news on June 10th") had no endpoint to call and the generated agent would
either hallucinate or just say "not found".

Categories now optionally carry an `"endpoints"` dict inside `api`, e.g.:

    "endpoints": {
        "live":     "...",
        "recent":   "...",
        "upcoming": "...",
    }

`patch_agent_env_file` writes ONE env var per endpoint
(`{CATEGORY}_{ENDPOINT_NAME}_URL`), and the instruction block sent to
coder_node lists all of them explicitly, with code_hint explaining when
each one should be used. This pushes the "pick the right tool based on
the time-frame implied by the query" logic into the generated agent's
tool docstrings, which is what the calling LLM actually uses to choose.

Usage in your LangGraph graph
------------------------------
    from app.agents.realtime_detector import realtime_detector_node

    workflow.add_node("realtime_detector", realtime_detector_node)

    # Wire it between parser and supervisor:
    workflow.add_edge("parser",            "realtime_detector")
    workflow.add_edge("realtime_detector", "supervisor")

State keys read:
    agent_spec   – str / dict / AgentSpec object
    agent_name   – str  (optional — used to build the output path)

State keys written:
    agent_spec      – same type as input, description augmented
    realtime_config – dict with api details, or None
"""

import os
import json
import dataclasses
from datetime import datetime, timezone
from typing import Optional
from dotenv import set_key, dotenv_values

# ── Import settings so we know where generated agents live ───────────────────
# Lazy import to avoid circular imports at module load time
def _get_generated_agents_dir() -> str:
    from app.core.config import settings
    return settings.generated_agents_dir


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY
# ─────────────────────────────────────────────────────────────────────────────
REALTIME_REGISTRY = {

    "cricket": {
        "triggers": [
            "cricket", "ipl", "psl", "bbl", "t20", "odi", "test match",
            "score", "wicket", "batting", "bowling", "over", "run rate",
            "espncricinfo", "cricbuzz", "cpl", "bcci", "pcb",
        ],
        "api": {
            "name":          "Cricbuzz (unofficial, free)",
            "base_url":      "https://cricbuzz-cricket.p.rapidapi.com",
            "live_scores":   "https://cricbuzz-cricket.p.rapidapi.com/matches/v1/live",
            "endpoints": {
                "live":     "https://cricbuzz-cricket.p.rapidapi.com/matches/v1/live",
                "recent":   "https://cricbuzz-cricket.p.rapidapi.com/matches/v1/recent",
                "upcoming": "https://cricbuzz-cricket.p.rapidapi.com/matches/v1/upcoming",
            },
            "requires_key":  True,
            "key_env_var":   "CRICBUZZ_RAPIDAPI_KEY",
            "host_env_var":  "CRICBUZZ_RAPIDAPI_HOST",
            "host_value":    "cricbuzz-cricket.p.rapidapi.com",
            "signup_url":    "https://rapidapi.com/cricketapilive/api/cricbuzz-cricket",
            "free_tier":     "500 requests / month",
            "fallback_url":  "https://www.espncricinfo.com/live-cricket-score",
            "fallback_type": "scrape",
        },
        "code_hint": (
            "Cricbuzz splits matches across THREE separate endpoints — there is NO "
            "date-filter query param on any of them. Build THREE separate tool "
            "functions, not one:\n"
            "  1. fetch_live_cricket()    -> CRICKET_LIVE_URL. Matches happening right now.\n"
            "  2. fetch_recent_cricket()  -> CRICKET_RECENT_URL. Matches that already "
            "finished — use this for 'on <date>', 'yesterday', 'last match' queries.\n"
            "  3. fetch_upcoming_cricket()-> CRICKET_UPCOMING_URL. Scheduled/future matches.\n"
            "Give each tool a clear, distinct docstring describing exactly when to use it — "
            "the calling LLM picks the tool based on the docstring, so vague docstrings "
            "cause the wrong tool to be picked.\n"
            "All three endpoints return the same nested shape: "
            "typeMatches[].seriesMatches[].seriesAdWrapper.matches[].matchInfo, where "
            "matchInfo.startDate / matchInfo.endDate are EPOCH MILLISECONDS as STRINGS "
            "(not ISO dates). Each tool MUST convert startDate via "
            "datetime.fromtimestamp(int(startDate)/1000) and filter results to what the "
            "tool's purpose promises — never just dump the raw payload back.\n"
            "If the key is missing, fall back to scraping "
            "https://www.espncricinfo.com/live-cricket-score with requests+BeautifulSoup."
        ),
        "tool_template": '''
# ── Cricbuzz helpers ──────────────────────────────────────────────────────────
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

CRICKET_LIVE_URL     = os.getenv("CRICKET_LIVE_URL",     "https://cricbuzz-cricket.p.rapidapi.com/matches/v1/live")
CRICKET_RECENT_URL   = os.getenv("CRICKET_RECENT_URL",   "https://cricbuzz-cricket.p.rapidapi.com/matches/v1/recent")
CRICKET_UPCOMING_URL = os.getenv("CRICKET_UPCOMING_URL", "https://cricbuzz-cricket.p.rapidapi.com/matches/v1/upcoming")
CRICBUZZ_RAPIDAPI_KEY  = os.getenv("CRICBUZZ_RAPIDAPI_KEY", "")
CRICBUZZ_RAPIDAPI_HOST = os.getenv("CRICBUZZ_RAPIDAPI_HOST", "cricbuzz-cricket.p.rapidapi.com")

def _call_cricbuzz(url: str) -> dict:
    if not CRICBUZZ_RAPIDAPI_KEY or CRICBUZZ_RAPIDAPI_KEY.startswith("YOUR_"):
        raise RuntimeError("CRICBUZZ_RAPIDAPI_KEY not configured")
    headers = {
        "X-RapidAPI-Key": CRICBUZZ_RAPIDAPI_KEY,
        "X-RapidAPI-Host": CRICBUZZ_RAPIDAPI_HOST,
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()

def _fallback_scrape() -> str:
    try:
        resp = requests.get("https://www.espncricinfo.com/live-cricket-score", timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        headlines = [h.get_text(strip=True) for h in soup.select("h1,h2,h3")][:5]
        return " | ".join(headlines) or "No headlines found"
    except Exception as e:
        return f"Fallback scrape error: {e}"

def _iter_matches(data: dict):
    for tm in data.get("typeMatches", []):
        for sm in tm.get("seriesMatches", []):
            for m in sm.get("seriesAdWrapper", {}).get("matches", []):
                yield m

@tool
def fetch_live_cricket(team: str = None) -> str:
    """Fetch matches currently in progress, optionally filtered by team name."""
    try:
        data = _call_cricbuzz(CRICKET_LIVE_URL)
    except Exception as e:
        log.warning("Cricbuzz live failed (%s). Falling back.", e)
        return f"[fallback] {_fallback_scrape()} | updated: {datetime.now(timezone.utc).isoformat()}"
    matches = []
    for m in _iter_matches(data):
        info = m.get("matchInfo", {})
        state = (info.get("state") or "").lower()
        if "progress" not in state and "innings break" not in state and "stumps" not in state:
            continue
        t1 = info.get("team1", {}).get("teamName", "")
        t2 = info.get("team2", {}).get("teamName", "")
        if team and team.lower() not in t1.lower() and team.lower() not in t2.lower():
            continue
        start = datetime.fromtimestamp(int(info.get("startDate", "0")) / 1000)
        matches.append({"team1": t1, "team2": t2, "state": info.get("state"),
                        "status": info.get("status"), "start": start.isoformat()})
    return str({"matches": matches, "last_updated": datetime.now(timezone.utc).isoformat()})

@tool
def fetch_recent_cricket(team: str = None, date: str = None) -> str:
    """Fetch finished matches, optionally filtered by team name and/or a YYYY-MM-DD date."""
    try:
        data = _call_cricbuzz(CRICKET_RECENT_URL)
    except Exception as e:
        log.warning("Cricbuzz recent failed (%s). Falling back.", e)
        return f"[fallback] {_fallback_scrape()} | updated: {datetime.now(timezone.utc).isoformat()}"
    matches = []
    for m in _iter_matches(data):
        info = m.get("matchInfo", {})
        state = (info.get("state") or "").lower()
        if "complete" not in state:
            continue
        t1 = info.get("team1", {}).get("teamName", "")
        t2 = info.get("team2", {}).get("teamName", "")
        if team and team.lower() not in t1.lower() and team.lower() not in t2.lower():
            continue
        start = datetime.fromtimestamp(int(info.get("startDate", "0")) / 1000)
        if date and start.strftime("%Y-%m-%d") != date:
            continue
        end = datetime.fromtimestamp(int(info.get("endDate", "0")) / 1000)
        matches.append({"team1": t1, "team2": t2, "result": info.get("status"),
                        "start": start.isoformat(), "end": end.isoformat()})
    return str({"matches": matches, "last_updated": datetime.now(timezone.utc).isoformat()})

@tool
def fetch_upcoming_cricket(team: str = None) -> str:
    """Fetch scheduled/future matches, optionally filtered by team name."""
    try:
        data = _call_cricbuzz(CRICKET_UPCOMING_URL)
    except Exception as e:
        log.warning("Cricbuzz upcoming failed (%s). Falling back.", e)
        return f"[fallback] {_fallback_scrape()} | updated: {datetime.now(timezone.utc).isoformat()}"
    matches = []
    for m in _iter_matches(data):
        info = m.get("matchInfo", {})
        state = (info.get("state") or "").lower()
        if state and "preview" not in state and "toss" not in state and "scheduled" not in state:
            continue
        t1 = info.get("team1", {}).get("teamName", "")
        t2 = info.get("team2", {}).get("teamName", "")
        if team and team.lower() not in t1.lower() and team.lower() not in t2.lower():
            continue
        start = datetime.fromtimestamp(int(info.get("startDate", "0")) / 1000)
        matches.append({"team1": t1, "team2": t2, "start": start.isoformat()})
    return str({"matches": matches, "last_updated": datetime.now(timezone.utc).isoformat()})
''',
    },

    "stocks": {
        "triggers": [
            "stock", "share price", "market", "nasdaq", "nyse", "nse", "bse",
            "crypto", "bitcoin", "btc", "ethereum", "trading", "portfolio", "ticker",
        ],
        "api": {
            "name":          "Alpha Vantage (free tier)",
            "base_url":      "https://www.alphavantage.co/query",
            "live_scores":   "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={key}",
            "endpoints": {
                "quote": "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={key}",
                "daily": "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={key}",
            },
            "requires_key":  True,
            "key_env_var":   "ALPHAVANTAGE_API_KEY",
            "signup_url":    "https://www.alphavantage.co/support/#api-key",
            "free_tier":     "25 requests / day",
            "fallback_url":  "https://finance.yahoo.com/quote/{symbol}",
            "fallback_type": "scrape",
        },
        "code_hint": (
            "Build TWO separate tool functions:\n"
            "  1. fetch_stock_quote(symbol) -> STOCKS_QUOTE_URL (GLOBAL_QUOTE). Use ONLY "
            "for 'current price right now' queries.\n"
            "  2. fetch_stock_history(symbol, date) -> STOCKS_DAILY_URL (TIME_SERIES_DAILY). "
            "Use for ANY query mentioning a specific past date, 'yesterday', 'last week', etc. "
            "The response has a 'Time Series (Daily)' dict KEYED BY DATE STRING ('YYYY-MM-DD') "
            "— look up the requested date directly. If the market was closed that day "
            "(weekend/holiday), fall back to the nearest earlier trading date present in the dict "
            "and say so explicitly in the response.\n"
            "Alpha Vantage free tier is capped at 25 requests/day — never call both tools "
            "for a single query unless the user's question genuinely needs both.\n"
            "If the key is missing or a call errors, scrape Yahoo Finance for the ticker instead."
        ),
    },

    "weather": {
        "triggers": [
            "weather", "forecast", "temperature", "rain", "humidity", "wind",
            "climate", "storm", "snow", "sunshine", "uv index", "air quality",
        ],
        "api": {
            "name":          "Open-Meteo (completely free, no key)",
            "base_url":      "https://api.open-meteo.com/v1/forecast",
            "live_scores":   (
                "https://api.open-meteo.com/v1/forecast"
                "?latitude={lat}&longitude={lon}"
                "&current=temperature_2m,relative_humidity_2m,"
                "wind_speed_10m,weather_code,precipitation"
                "&timezone=auto"
            ),
            "endpoints": {
                "forecast": (
                    "https://api.open-meteo.com/v1/forecast"
                    "?latitude={lat}&longitude={lon}"
                    "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code,precipitation"
                    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"
                    "&timezone=auto"
                ),
                "historical": (
                    "https://archive-api.open-meteo.com/v1/archive"
                    "?latitude={lat}&longitude={lon}"
                    "&start_date={date}&end_date={date}"
                    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"
                    "&timezone=auto"
                ),
            },
            "requires_key":  False,
            "key_env_var":   None,
            "signup_url":    "https://open-meteo.com/",
            "free_tier":     "Unlimited (non-commercial)",
            "fallback_url":  "https://wttr.in/{city}?format=j1",
            "fallback_type": "json",
        },
        "code_hint": (
            "Geocode the city name FIRST using "
            "https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1 "
            "to get lat/lon — every other call depends on this.\n"
            "Build TWO tool functions:\n"
            "  1. fetch_weather_forecast(city, date=None) -> WEATHER_FORECAST_URL. Use for "
            "'today' or any FUTURE date (Open-Meteo forecasts up to ~16 days ahead). If a "
            "specific future date is given, find the matching entry in the 'daily' arrays "
            "(they're parallel arrays indexed by position, with 'time' holding the date strings).\n"
            "  2. fetch_weather_historical(city, date) -> WEATHER_HISTORICAL_URL. Use for ANY "
            "PAST date — the live forecast endpoint does NOT have past data, this separate "
            "Archive API does. Pass the date as start_date AND end_date (both required, same value).\n"
            "Decide which tool to call by comparing the requested date to today's date — "
            "do this comparison in code, don't ask the LLM to guess.\n"
            "weather_code is a WMO numeric code — map it to a human description (0=clear, "
            "1-3=partly cloudy, 45/48=fog, 51-67=rain, 71-77=snow, 80-99=thunderstorm) rather "
            "than returning the raw number."
        ),
    },

    "news": {
        "triggers": [
            "news", "headline", "breaking", "latest news", "article",
            "rss", "feed", "media", "journalist", "press",
        ],
        "api": {
            "name":          "NewsAPI.org (free developer tier)",
            "base_url":      "https://newsapi.org/v2",
            "live_scores":   "https://newsapi.org/v2/top-headlines?q={query}&apiKey={key}",
            "endpoints": {
                "top_headlines": "https://newsapi.org/v2/top-headlines?q={query}&apiKey={key}",
                "everything":    "https://newsapi.org/v2/everything?q={query}&from={from_date}&to={to_date}&sortBy=publishedAt&apiKey={key}",
            },
            "requires_key":  True,
            "key_env_var":   "NEWSAPI_KEY",
            "signup_url":    "https://newsapi.org/register",
            "free_tier":     "100 requests / day (developer)",
            "fallback_url":  "https://news.google.com/rss/search?q={query}&hl=en",
            "fallback_type": "rss",
        },
        "code_hint": (
            "Build TWO tool functions:\n"
            "  1. fetch_top_headlines(query) -> NEWS_TOP_HEADLINES_URL. Use for 'breaking', "
            "'latest', 'right now' queries with NO date mentioned. This endpoint does NOT "
            "support date filtering — don't try to pass dates to it.\n"
            "  2. fetch_news_by_date(query, date) -> NEWS_EVERYTHING_URL. Use whenever a "
            "specific date or date range is mentioned ('on June 10th', 'last week', etc). "
            "Set both from_date and to_date to the requested date (or range) in YYYY-MM-DD "
            "format — this is the ONLY NewsAPI endpoint that supports date filtering.\n"
            "Extract from results: title, source, publishedAt, url, description.\n"
            "If the key is missing or a call errors, parse the Google News RSS feed with "
            "the feedparser library instead (note: RSS fallback can't reliably filter by "
            "exact past date — say so if you fall back to it)."
        ),
    },

    "sports_general": {
        "triggers": [
            "football", "soccer", "basketball", "nba", "nfl", "tennis",
            "formula 1", "f1", "rugby", "hockey", "baseball", "esports",
            "live score", "fixture", "standings", "league table",
        ],
        "api": {
            "name":          "TheSportsDB (free tier)",
            "base_url":      "https://www.thesportsdb.com/api/v1/json/3",
            "live_scores":   "https://www.thesportsdb.com/api/v1/json/3/livescore.php",
            "endpoints": {
                "live":          "https://www.thesportsdb.com/api/v1/json/3/livescore.php",
                "recent":        "https://www.thesportsdb.com/api/v1/json/3/eventspastleague.php?id={league_id}",
                "upcoming":      "https://www.thesportsdb.com/api/v1/json/3/eventsnextleague.php?id={league_id}",
                "search_league": "https://www.thesportsdb.com/api/v1/json/3/search_all_leagues.php?s={sport}",
                "search_team":   "https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={team_name}",
            },
            "requires_key":  False,
            "key_env_var":   "SPORTSDB_API_KEY",
            "signup_url":    "https://www.thesportsdb.com/api.php",
            "free_tier":     "Free tier available (key=3 for testing)",
            "fallback_url":  "https://www.thesportsdb.com/api/v1/json/3/livescore.php",
            "fallback_type": "json",
        },
        "code_hint": (
            "IMPORTANT: recent/upcoming endpoints need a LEAGUE ID, not a name — TheSportsDB "
            "does not accept league/team names directly on those endpoints. Build a small "
            "ID-resolution step BEFORE calling them:\n"
            "  0. resolve_league_id(sport_or_league_name) -> SPORTS_GENERAL_SEARCH_LEAGUE_URL. "
            "Cache the result in memory per run — don't re-resolve on every call.\n"
            "Then build THREE tool functions:\n"
            "  1. fetch_live_sports() -> SPORTS_GENERAL_LIVE_URL. Matches in progress right now. "
            "Note: this endpoint is unreliable for many leagues on the free tier and may "
            "return an empty list even when matches ARE live — treat an empty response as "
            "'no data available' rather than 'no matches', and consider falling back to "
            "'recent' if the live endpoint comes back empty.\n"
            "  2. fetch_recent_sports(league_name) -> resolve the ID, then call "
            "SPORTS_GENERAL_RECENT_URL with that id. Use for 'played on <date>' or 'results' queries.\n"
            "  3. fetch_upcoming_sports(league_name) -> resolve the ID, then call "
            "SPORTS_GENERAL_UPCOMING_URL with that id. Use for fixture/schedule queries.\n"
            "Each event has 'dateEvent' as a plain 'YYYY-MM-DD' string (no epoch math needed "
            "here, unlike Cricbuzz) — filter directly against the requested date."
        ),
    },

    "currency": {
        "triggers": [
            "currency", "exchange rate", "usd", "eur", "gbp", "pkr", "inr",
            "conversion", "fx rate", "forex",
        ],
        "api": {
            "name":          "ExchangeRate-API + Frankfurter (both free)",
            "base_url":      "https://open.er-api.com/v6/latest",
            "live_scores":   "https://open.er-api.com/v6/latest/{base_currency}",
            "endpoints": {
                "latest":     "https://open.er-api.com/v6/latest/{base_currency}",
                "historical": "https://api.frankfurter.app/{date}?from={base_currency}",
            },
            "requires_key":  False,
            "key_env_var":   None,
            "signup_url":    "https://www.exchangerate-api.com/",
            "free_tier":     "open.er-api: 1500 req/month, no key. Frankfurter: unlimited, no key.",
            "fallback_url":  "https://open.er-api.com/v6/latest/USD",
            "fallback_type": "json",
        },
        "code_hint": (
            "open.er-api.com only ever returns the LATEST rate — it has no historical data, "
            "so a second provider (Frankfurter) is wired in just for past dates.\n"
            "Build TWO tool functions:\n"
            "  1. fetch_latest_rates(base_currency) -> CURRENCY_LATEST_URL. Use for 'current/"
            "today's' exchange rate queries.\n"
            "  2. fetch_historical_rates(base_currency, date) -> CURRENCY_HISTORICAL_URL. Use "
            "whenever a specific past date is mentioned. date must be 'YYYY-MM-DD' in the URL "
            "path itself (not a query param). Frankfurter has data back to 1999 only — if an "
            "older date is requested, say the data isn't available rather than guessing.\n"
            "Both return a flat 'rates' dict keyed by currency code — extract directly, no "
            "nested parsing needed."
        ),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# KEYWORD DETECTOR  (no LLM call — fast & free)
# ─────────────────────────────────────────────────────────────────────────────

def detect_realtime_category(spec_text: str) -> Optional[str]:
    """
    Returns the best-matching category key from REALTIME_REGISTRY,
    or None if the spec doesn't seem to need real-time data.
    """
    text_lower = spec_text.lower()

    realtime_signals = [
        "live", "real-time", "real time", "current", "latest", "today",
        "right now", "streaming", "up to date", "up-to-date", "breaking",
        "score", "price", "rate",
    ]
    has_signal = any(s in text_lower for s in realtime_signals)

    scores = {}
    for category, config in REALTIME_REGISTRY.items():
        hits = sum(1 for t in config["triggers"] if t in text_lower)
        if hits > 0:
            scores[category] = hits

    if not scores:
        return None

    best = max(scores, key=scores.get)

    # Avoid false positives: need a realtime signal OR multiple trigger hits
    if not has_signal and scores[best] == 1:
        return None

    return best


# ─────────────────────────────────────────────────────────────────────────────
# AGENT ENV PATH RESOLVER
# Returns the .env path inside the generated agent's folder — NEVER project root
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_agent_env_path(state: dict) -> str:
    """
    Determines where to write the generated agent's .env file.

    Priority:
      1. state["agent_name"]  → <generated_agents_dir>/<agent_name>/.env
      2. state["output_dir"]  → <output_dir>/.env
      3. Fallback             → <generated_agents_dir>/current_agent/.env

    NEVER writes to the project root .env.
    """
    generated_agents_dir = _get_generated_agents_dir()

    # Priority 1: agent_name from state, OR from the AgentSpec object itself
    agent_name = state.get("agent_name")
    if not agent_name:
        spec = state.get("agent_spec")
        if hasattr(spec, "agent_name") and spec.agent_name:
            agent_name = spec.agent_name
        elif isinstance(spec, dict):
            agent_name = spec.get("agent_name")
    if agent_name:
        agent_dir = os.path.join(generated_agents_dir, str(agent_name))
        os.makedirs(agent_dir, exist_ok=True)
        return os.path.join(agent_dir, ".env")

    # Priority 2: explicit output_dir in state
    output_dir = state.get("output_dir")
    if output_dir and os.path.isabs(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, ".env")

    # Priority 3: fallback — use a staging folder, NOT project root
    fallback_dir = os.path.join(generated_agents_dir, "current_agent")
    os.makedirs(fallback_dir, exist_ok=True)
    return os.path.join(fallback_dir, ".env")


# ─────────────────────────────────────────────────────────────────────────────
# .ENV PATCHER  — writes only to the generated agent's .env
# ─────────────────────────────────────────────────────────────────────────────

def patch_agent_env_file(category: str, api_config: dict, env_path: str) -> dict:
    """
    Writes required env vars into the GENERATED AGENT's .env file.
    Never touches the project-root .env.
    Returns a dict of what was written.

    If api_config has an "endpoints" dict, ONE env var is written per
    endpoint: {CATEGORY}_{ENDPOINT_NAME}_URL (e.g. CRICKET_RECENT_URL).
    Otherwise falls back to the old single {CATEGORY}_LIVE_URL behavior.
    """
    written = {}

    # Create file if it doesn't exist
    if not os.path.exists(env_path):
        open(env_path, "w").close()

    existing = dotenv_values(env_path)

    def _write(var, val):
        """Only write if var is missing or empty — never overwrite existing real keys."""
        if var not in existing or not existing[var]:
            set_key(env_path, var, val)
            written[var] = val

    _write(f"{category.upper()}_BASE_URL",     api_config.get("base_url", ""))
    _write(f"{category.upper()}_FALLBACK_URL", api_config.get("fallback_url", ""))

    endpoints = api_config.get("endpoints")
    if endpoints:
        for ep_name, ep_url in endpoints.items():
            _write(f"{category.upper()}_{ep_name.upper()}_URL", ep_url)
    else:
        # Backward-compatible path for any category without "endpoints"
        _write(f"{category.upper()}_LIVE_URL", api_config.get("live_scores", ""))

    key_var = api_config.get("key_env_var")
    if key_var:
        _write(key_var, f"YOUR_{key_var}_HERE")

    host_var = api_config.get("host_env_var")
    if host_var:
        _write(host_var, api_config.get("host_value", ""))

    set_key(env_path, "REALTIME_CONFIGURED_AT", datetime.now(timezone.utc).isoformat())
    return written


# ─────────────────────────────────────────────────────────────────────────────
# SPEC AUGMENTER  — preserves the original type (str / dict / AgentSpec)
# ─────────────────────────────────────────────────────────────────────────────

def _augment_spec(original_spec, instruction: str):
    """
    Appends the realtime instruction into AgentSpec.reasoning (the only
    free-text field on AgentSpec, excluded from user output).
    Falls back gracefully for dicts and plain strings.
    """
    if hasattr(original_spec, "agent_name"):
        # AgentSpec (Pydantic v2) — append to reasoning field
        if hasattr(original_spec, "model_copy"):
            return original_spec.model_copy(
                update={"reasoning": (original_spec.reasoning or "") + instruction}
            )
        # Pydantic v1 — mutate in place
        try:
            original_spec.reasoning = (original_spec.reasoning or "") + instruction
            return original_spec
        except (AttributeError, TypeError):
            pass
        return original_spec  # frozen — return as-is, coder gets realtime_config

    if hasattr(original_spec, "description"):
        # Generic pydantic with description field
        if hasattr(original_spec, "model_copy"):
            return original_spec.model_copy(
                update={"description": (original_spec.description or "") + instruction}
            )
        try:
            original_spec.description = (original_spec.description or "") + instruction
            return original_spec
        except (AttributeError, TypeError):
            pass
        if dataclasses.is_dataclass(original_spec):
            return dataclasses.replace(
                original_spec,
                description=(original_spec.description or "") + instruction,
            )
        return original_spec

    if isinstance(original_spec, dict):
        # Prefer agent_name key, fall back to description
        key = "reasoning" if "reasoning" in original_spec else "description"
        return {**original_spec, key: original_spec.get(key, "") + instruction}

    # Plain string
    return str(original_spec) + instruction


# ─────────────────────────────────────────────────────────────────────────────
# LANGGRAPH NODE
# ─────────────────────────────────────────────────────────────────────────────

def realtime_detector_node(state: dict) -> dict:
    """
    LangGraph node.

    Reads  : state["agent_spec"]   – the agent description
             state["agent_name"]   – used to resolve the output .env path
    Writes : state["agent_spec"]   – same type, description augmented
             state["realtime_config"] – dict or None
    """
    original_spec = state.get("agent_spec", "")

    # ── Extract plain text for keyword matching ──────────────────────────────
    if hasattr(original_spec, "agent_name"):
        # AgentSpec — combine agent_name + reasoning for keyword detection
        spec_text = " ".join(filter(None, [
            getattr(original_spec, "agent_name", "") or "",
            getattr(original_spec, "reasoning", "") or "",
            " ".join(getattr(original_spec, "tools_needed", []) or []),
        ]))
    elif hasattr(original_spec, "description"):
        spec_text = (getattr(original_spec, "description", "") or "") + \
                    " " + (getattr(original_spec, "name", "") or "")
    elif isinstance(original_spec, dict):
        spec_text = " ".join(filter(None, [
            original_spec.get("agent_name", ""),
            original_spec.get("description", ""),
            original_spec.get("name", ""),
            original_spec.get("reasoning", ""),
        ]))
    else:
        spec_text = str(original_spec)

    print(f"\n[realtime_detector] Analysing spec: {spec_text[:120]}...")

    # ── Detect ───────────────────────────────────────────────────────────────
    category = detect_realtime_category(spec_text)

    if category is None:
        print("[realtime_detector] No real-time data needed — passing through.")
        return {**state, "realtime_config": None}

    api_config = REALTIME_REGISTRY[category]["api"]
    code_hint  = REALTIME_REGISTRY[category]["code_hint"]

    print(f"[realtime_detector] Detected category : {category}")
    print(f"[realtime_detector] API               : {api_config['name']}")

    # Resolve the GENERATED AGENT's .env path 
    agent_env_path = _resolve_agent_env_path(state)
    print(f"[realtime_detector] Writing .env to   : {agent_env_path}")

    # Patch the generated agent's .env 
    written_vars = patch_agent_env_file(category, api_config, agent_env_path)
    print(f"[realtime_detector] Wrote vars        : {list(written_vars.keys())}")

    #  Build realtime_config for coder_node
    realtime_config = {
        "category":         category,
        "api_name":         api_config["name"],
        "base_url":         api_config["base_url"],
        "live_url":         api_config["live_scores"],
        "endpoints":        api_config.get("endpoints", {}),
        "fallback_url":     api_config.get("fallback_url", ""),
        "fallback_type":    api_config.get("fallback_type", ""),
        "requires_key":     api_config["requires_key"],
        "key_env_var":      api_config.get("key_env_var"),
        "signup_url":       api_config.get("signup_url", ""),
        "free_tier":        api_config.get("free_tier", ""),
        "agent_env_path":   agent_env_path,
        "env_vars_written": written_vars,
        "code_hint":        code_hint,
        "tool_template":    REALTIME_REGISTRY[category].get("tool_template", ""),
    }

    #  Build the endpoints listing for the instruction block
    endpoints = api_config.get("endpoints")
    if endpoints:
        endpoints_block = "\n".join(
            f"{ep_name.replace('_', ' ').capitalize()} endpoint : {ep_url}"
            for ep_name, ep_url in endpoints.items()
        )
    else:
        endpoints_block = f"Live endpoint  : {api_config['live_scores']}"

    # Build instruction block for coder_node 
    realtime_instruction = f"""

=== REAL-TIME DATA REQUIREMENTS (auto-detected) ===
Category       : {category}
API to use     : {api_config['name']}
Base URL       : {api_config['base_url']}
{endpoints_block}
Fallback URL   : {api_config.get('fallback_url', 'N/A')}
Fallback type  : {api_config.get('fallback_type', 'N/A')}
Requires key   : {api_config['requires_key']}
Key env var    : {api_config.get('key_env_var', 'None')}
Signup (free)  : {api_config.get('signup_url', 'N/A')}
Free tier      : {api_config.get('free_tier', 'N/A')}

CODING INSTRUCTIONS:
{code_hint}

IMPORTANT RULES FOR GENERATED agent.py:
1. ALWAYS load env vars with python-dotenv at the top of agent.py.
2. NEVER hardcode URLs or API keys — always use os.getenv("VAR_NAME").
3. ALWAYS implement the fallback if the primary API key is missing or errors.
4. EVERY tool MUST make a real HTTP request — never simulate data.
5. If the API key placeholder starts with "YOUR_", warn the user and use fallback.
6. Add a "last_updated" timestamp to every live data response.
7. If multiple endpoints/tools are listed above, register ALL of them with the LLM
   and write a DISTINCT, SPECIFIC docstring for each — the calling LLM chooses
   which tool to call based on the docstring text, not on this instruction block.
=== END REAL-TIME DATA REQUIREMENTS ===
"""

    # Augment spec — PRESERVING ORIGINAL TYPE
    augmented_spec = _augment_spec(original_spec, realtime_instruction)
    print("[realtime_detector] Spec augmented — type preserved.")

    return {
        **state,
        "agent_spec":      augmented_spec,
        "realtime_config": realtime_config,
    }



# STANDALONE TEST  (python -m app.agents.realtime_detector

if __name__ == "__main__":
    test_cases = [
        "Build a cricket live score agent that shows PSL matches and batting stats",
        "Create a weather forecast agent for Pakistani cities",
        "Make a stock price tracker for NASDAQ",
        "Build a simple chatbot that answers general questions",
        "News aggregator that shows breaking headlines from Pakistan",
        "Currency converter with live PKR to USD rates",
        "Football live score and fixtures agent for the Premier League",
    ]

    print("=" * 60)
    print("REALTIME DETECTOR — standalone test (keyword detection only)")
    print("=" * 60)

    for spec in test_cases:
        print(f"\nSpec: \"{spec}\"")
        cat = detect_realtime_category(spec)
        if cat:
            api = REALTIME_REGISTRY[cat]["api"]
            print(f"  → Category : {cat}")
            print(f"  → API      : {api['name']}")
            endpoints = api.get("endpoints")
            if endpoints:
                for ep_name, ep_url in endpoints.items():
                    print(f"  → {ep_name:10s}: {ep_url}")
            else:
                print(f"  → Live URL : {api['live_scores']}")
            print(f"  → Key var  : {api.get('key_env_var', 'None (free)')}")
        else:
            print("  → No real-time data needed")

    print("\n" + "=" * 60)
    print("Testing _resolve_agent_env_path with mock states...")
    print("=" * 60)

    import tempfile

    # Simulate what the node would do with agent_name in state
    mock_generated_dir = tempfile.mkdtemp()

    # Monkey-patch _get_generated_agents_dir for testing
    _orig = _get_generated_agents_dir
    def _get_generated_agents_dir():
        return mock_generated_dir

    state_with_name    = {"agent_spec": "cricket agent", "agent_name": "cricket_bot"}
    state_with_dir     = {"agent_spec": "weather agent", "output_dir": os.path.join(mock_generated_dir, "weather_bot")}
    state_no_hint      = {"agent_spec": "news agent"}

    for label, st in [
        ("agent_name in state", state_with_name),
        ("output_dir in state", state_with_dir),
        ("no hint (fallback)",  state_no_hint),
    ]:
        path = _resolve_agent_env_path(st)
        in_root = not path.startswith(mock_generated_dir)
        print(f"\n  [{label}]")
        print(f"    .env path  : {path}")
        print(f"    Root safe? : {'✅ YES' if not in_root else '❌ NO — would corrupt project!'}")

    # Restore
    _get_generated_agents_dir = _orig
    print("\nAll tests done.")