#!/usr/bin/env python3
"""Tests for the Morning Briefing agent tools and HTTP server.

Run:
    python3 test_tools.py

Tests the shared tools with real API calls (weather, news) and validates
the HTTP server can start and handle requests.
"""

import json
import sys
import threading
import time
import urllib.request
import urllib.error
from http.server import HTTPServer

# Import shared tools
from tools import (
    get_weather, get_news, get_calendar_events, get_commute_time,
    get_time_context, execute_tool, TOOL_SCHEMAS,
)
from prompts import SYSTEM_PROMPT, build_user_prompt


# --- Test helpers ---

passed = 0
failed = 0


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


# --- Tool Tests ---

def test_time_context():
    print("\n--- get_time_context ---")
    result = get_time_context()
    test("returns dict", isinstance(result, dict))
    test("has date", "date" in result)
    test("has greeting", "greeting" in result)
    test("has period", result.get("period") in ("morning", "afternoon", "evening"))
    test("has day_of_week", "day_of_week" in result)


def test_weather():
    print("\n--- get_weather (San Francisco) ---")
    result = get_weather(37.7749, -122.4194)
    test("returns dict", isinstance(result, dict))
    test("no error", "error" not in result, result.get("error", ""))
    test("has current_temp_f", "current_temp_f" in result)
    test("has condition", "condition" in result)
    test("has today_high_f", "today_high_f" in result)
    test("has rain_chance_pct", "rain_chance_pct" in result)
    test("temp is reasonable", -50 < result.get("current_temp_f", 999) < 150)


def test_news():
    print("\n--- get_news ---")
    result = get_news("technology", 3)
    test("returns dict", isinstance(result, dict))
    test("no error", "error" not in result, result.get("error", ""))
    test("has headlines list", isinstance(result.get("headlines"), list))
    test("got expected count", len(result.get("headlines", [])) == 3)
    if result.get("headlines"):
        h = result["headlines"][0]
        test("headline has title", "title" in h)
        test("headline has url", "url" in h)


def test_calendar():
    print("\n--- get_calendar_events ---")
    result = get_calendar_events()
    test("returns dict", isinstance(result, dict))
    test("has date", "date" in result)
    test("has events list", isinstance(result.get("events"), list))


def test_commute():
    print("\n--- get_commute_time ---")
    result = get_commute_time(37.7749, -122.4194, "1 Hacker Way, Menlo Park")
    test("returns dict", isinstance(result, dict))
    test("has destination", "destination" in result)


def test_execute_tool_dispatch():
    print("\n--- execute_tool dispatcher ---")
    result = execute_tool("get_time_context", {})
    test("dispatches get_time_context", "greeting" in result)

    result = execute_tool("get_weather", {"latitude": 40.7128, "longitude": -74.0060})
    test("dispatches get_weather (NYC)", "current_temp_f" in result)

    result = execute_tool("nonexistent_tool", {})
    test("unknown tool returns error", "error" in result)


def test_tool_schemas():
    print("\n--- TOOL_SCHEMAS ---")
    test("schemas is a list", isinstance(TOOL_SCHEMAS, list))
    test("has 5 tools", len(TOOL_SCHEMAS) == 5)
    names = {t["function"]["name"] for t in TOOL_SCHEMAS}
    test("has get_weather", "get_weather" in names)
    test("has get_news", "get_news" in names)
    test("has get_time_context", "get_time_context" in names)
    for schema in TOOL_SCHEMAS:
        func = schema["function"]
        test(f"  {func['name']} has description", bool(func.get("description")))
        test(f"  {func['name']} has parameters", "parameters" in func)


# --- Prompt Tests ---

def test_prompts():
    print("\n--- prompts ---")
    test("SYSTEM_PROMPT is non-empty", len(SYSTEM_PROMPT) > 100)
    test("SYSTEM_PROMPT mentions tools", "get_weather" in SYSTEM_PROMPT or "weather" in SYSTEM_PROMPT.lower())

    prompt = build_user_prompt(37.7749, -122.4194, "technology, finance")
    test("user prompt has period", any(p in prompt for p in ("morning", "afternoon", "evening")))
    test("user prompt has location", "37.7749" in prompt)
    test("user prompt has preferences", "technology" in prompt)

    prompt_no_loc = build_user_prompt()
    test("no-location prompt works", "not available" in prompt_no_loc.lower() or "briefing" in prompt_no_loc.lower())


# --- HTTP Server Tests ---

def test_http_server():
    """Test the HTTP server starts and handles requests."""
    print("\n--- HTTP server ---")

    # Import the handler from one of the server implementations
    # We'll use a minimal version to avoid LLM dependencies
    from http.server import BaseHTTPRequestHandler

    class TestHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/briefing":
                self.send_error(404)
                return
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}

            # Instead of calling the LLM, just run the tools and return their output
            time_ctx = execute_tool("get_time_context", {})
            response = json.dumps({
                "briefing": f"Test briefing for {time_ctx.get('period', 'unknown')}",
                "tools_working": True,
                "received": body,
            })
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(response.encode())

        def do_GET(self):
            if self.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"healthy"}')
                return
            self.send_error(404)

        def log_message(self, format, *args):
            pass  # Suppress output during tests

    # Start server in background
    server = HTTPServer(("127.0.0.1", 0), TestHandler)  # port 0 = random
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        # Test health endpoint
        req = urllib.request.Request(f"http://127.0.0.1:{port}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            test("GET /health returns 200", resp.status == 200)
            test("health response is healthy", data.get("status") == "healthy")

        # Test briefing endpoint
        payload = json.dumps({"latitude": 37.7749, "longitude": -122.4194}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/briefing",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            test("POST /briefing returns 200", resp.status == 200)
            test("response has briefing", "briefing" in data)
            test("response has tools_working", data.get("tools_working") is True)
            test("received lat/lon", data.get("received", {}).get("latitude") == 37.7749)

        # Test 404
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/nonexistent")
            urllib.request.urlopen(req, timeout=5)
            test("GET /nonexistent returns 404", False)
        except urllib.error.HTTPError as e:
            test("GET /nonexistent returns 404", e.code == 404)

    finally:
        server.shutdown()


# --- Run all tests ---

if __name__ == "__main__":
    print("OpenShortcuts Morning Briefing — Test Suite")
    print("=" * 50)

    test_time_context()
    test_weather()
    test_news()
    test_calendar()
    test_commute()
    test_execute_tool_dispatch()
    test_tool_schemas()
    test_prompts()
    test_http_server()

    print()
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")

    if failed > 0:
        sys.exit(1)
    else:
        print("All tests passed!")
        sys.exit(0)
