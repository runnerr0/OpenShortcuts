#!/usr/bin/env python3
"""Morning Briefing agent using OpenAI Responses API.

A lightweight HTTP server that:
1. Receives a request from the iOS Shortcut
2. Calls OpenAI's Responses API with tools defined
3. Executes tool calls locally and feeds results back
4. Returns the final briefing text

The Responses API replaces the deprecated Assistants API (sunset Aug 2026).
It handles multi-turn tool use in a simpler request/response model.

Usage:
    export OPENAI_API_KEY=sk-...
    python3 agent_server.py

    # Or with a custom port:
    python3 agent_server.py --port 8080

Dependencies:
    pip install openai
"""

import argparse
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from openai import OpenAI
except ImportError:
    print("openai package required: pip install openai")
    sys.exit(1)

# Add parent directory for shared tools/prompts
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools import TOOL_SCHEMAS, execute_tool
from prompts import SYSTEM_PROMPT, build_user_prompt


def run_agent(latitude=None, longitude=None, preferences=None):
    """Run the morning briefing agent loop using OpenAI Responses API."""
    client = OpenAI()

    user_prompt = build_user_prompt(latitude, longitude, preferences)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # Agent loop — keep calling until no more tool calls
    max_iterations = 5
    for i in range(max_iterations):
        response = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        message = choice.message

        # Append assistant's response to conversation
        messages.append(message.model_dump())

        # If no tool calls, we're done
        if not message.tool_calls:
            return message.content

        # Execute each tool call
        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            result = execute_tool(func_name, func_args)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

    # If we hit max iterations, return whatever we have
    return messages[-1].get("content", "I wasn't able to complete your briefing.")


class BriefingHandler(BaseHTTPRequestHandler):
    """HTTP handler for briefing requests from iOS Shortcuts."""

    def do_POST(self):
        if self.path != "/briefing":
            self.send_error(404)
            return

        # Parse request body
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}

        latitude = body.get("latitude")
        longitude = body.get("longitude")
        preferences = body.get("preferences")

        try:
            briefing = run_agent(latitude, longitude, preferences)
            response = json.dumps({"briefing": briefing})

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response.encode())
        except Exception as e:
            error = json.dumps({"error": str(e)})
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(error.encode())

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    parser = argparse.ArgumentParser(description="Morning Briefing Agent (OpenAI)")
    parser.add_argument("--port", type=int, default=8090, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY environment variable")
        sys.exit(1)

    server = HTTPServer((args.host, args.port), BriefingHandler)
    print(f"Morning Briefing Agent (OpenAI) running on http://{args.host}:{args.port}/briefing")
    print("Send POST with {latitude, longitude, preferences}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
