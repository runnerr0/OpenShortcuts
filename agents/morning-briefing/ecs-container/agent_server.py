#!/usr/bin/env python3
"""Morning Briefing agent for ECS/Fargate deployment.

A containerized agent server that:
- Runs as a long-lived HTTP service on ECS Fargate
- Accepts POST /briefing from iOS Shortcuts via ALB
- Supports any LLM provider (set via LLM_PROVIDER env var)
- Includes /health endpoint for ALB health checks

Environment variables:
    LLM_PROVIDER: "openai", "anthropic", or "groq" (default: openai)
    OPENAI_API_KEY: API key for OpenAI
    ANTHROPIC_API_KEY: API key for Anthropic
    GROQ_API_KEY: API key for Groq
    LLM_MODEL: Model to use (default varies by provider)
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add parent for shared tools/prompts (in container, these are copied to /app)
sys.path.insert(0, os.path.dirname(__file__))
from tools import TOOL_SCHEMAS, execute_tool
from prompts import SYSTEM_PROMPT, build_user_prompt


def run_agent_openai(latitude=None, longitude=None, preferences=None):
    """Run agent loop using OpenAI-compatible API (works with OpenAI, Groq)."""
    from openai import OpenAI

    provider = os.environ.get("LLM_PROVIDER", "openai")

    if provider == "groq":
        client = OpenAI(
            api_key=os.environ.get("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
        )
        model = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
    else:
        client = OpenAI()
        model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

    user_prompt = build_user_prompt(latitude, longitude, preferences)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    for _ in range(5):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        message = choice.message
        messages.append(message.model_dump())

        if not message.tool_calls:
            return message.content

        for tool_call in message.tool_calls:
            result = execute_tool(
                tool_call.function.name,
                json.loads(tool_call.function.arguments),
            )
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

    return "Briefing generation timed out."


def run_agent_anthropic(latitude=None, longitude=None, preferences=None):
    """Run agent loop using Anthropic's native tool use API."""
    import anthropic

    client = anthropic.Anthropic()
    model = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")
    user_prompt = build_user_prompt(latitude, longitude, preferences)

    # Convert OpenAI tool schemas to Anthropic format
    anthropic_tools = []
    for t in TOOL_SCHEMAS:
        func = t["function"]
        anthropic_tools.append({
            "name": func["name"],
            "description": func["description"],
            "input_schema": func["parameters"],
        })

    messages = [{"role": "user", "content": user_prompt}]

    for _ in range(5):
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=anthropic_tools,
            messages=messages,
        )

        # Check if we need to execute tools
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if not tool_use_blocks:
            # Extract text response
            text_blocks = [b.text for b in response.content if b.type == "text"]
            return " ".join(text_blocks)

        # Append assistant response
        messages.append({"role": "assistant", "content": response.content})

        # Execute tools and append results
        tool_results = []
        for block in tool_use_blocks:
            result = execute_tool(block.name, block.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })

        messages.append({"role": "user", "content": tool_results})

    return "Briefing generation timed out."


def run_agent(latitude=None, longitude=None, preferences=None):
    """Route to the right provider."""
    provider = os.environ.get("LLM_PROVIDER", "openai")
    if provider == "anthropic":
        return run_agent_anthropic(latitude, longitude, preferences)
    return run_agent_openai(latitude, longitude, preferences)


class BriefingHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        if self.path != "/briefing":
            self.send_error(404)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}

        try:
            briefing = run_agent(
                latitude=body.get("latitude"),
                longitude=body.get("longitude"),
                preferences=body.get("preferences"),
            )
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

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"healthy"}')
            return
        self.send_error(404)

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    port = int(os.environ.get("PORT", 8090))
    server = HTTPServer(("0.0.0.0", port), BriefingHandler)
    provider = os.environ.get("LLM_PROVIDER", "openai")
    model = os.environ.get("LLM_MODEL", "auto")
    print(f"Morning Briefing Agent (ECS/{provider}/{model}) on port {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
