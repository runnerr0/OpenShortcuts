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
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add paths for shared tools/prompts — works both in container (same dir)
# and when running directly from the repo (parent dir)
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools import TOOL_SCHEMAS, execute_tool
from prompts import SYSTEM_PROMPT, TOPIC_SYSTEM_PROMPT, build_user_prompt


def _clean_message(message):
    """Convert an OpenAI message to a dict, stripping unsupported fields.

    Some providers (Groq) reject extra fields like 'annotations' that the
    OpenAI SDK adds via model_dump(). Strip them for compatibility.
    """
    d = message.model_dump()
    d.pop("annotations", None)
    return {k: v for k, v in d.items() if v is not None}


def run_agent_openai(latitude=None, longitude=None, preferences=None):
    """Run agent loop using OpenAI-compatible API (works with OpenAI, Groq)."""
    client, model, _ = _get_client_and_model()
    user_prompt = build_user_prompt(latitude, longitude, preferences)
    return _run_loop(client, model, SYSTEM_PROMPT, user_prompt)


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


def _get_client_and_model():
    """Get the LLM client and model based on provider config."""
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

    return client, model, provider


def _run_loop(client, model, system_prompt, user_prompt):
    """Generic agent loop: system prompt + user prompt → tool calls → response."""
    messages = [
        {"role": "system", "content": system_prompt},
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
        messages.append(_clean_message(message))

        if not message.tool_calls:
            return message.content

        for tool_call in message.tool_calls:
            args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
            result = execute_tool(tool_call.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

    return "Briefing generation timed out."


def run_agent(latitude=None, longitude=None, preferences=None):
    """Route to the right provider for morning briefings."""
    provider = os.environ.get("LLM_PROVIDER", "openai")
    if provider == "anthropic":
        return run_agent_anthropic(latitude, longitude, preferences)
    client, model, _ = _get_client_and_model()
    user_prompt = build_user_prompt(latitude, longitude, preferences)
    return _run_loop(client, model, SYSTEM_PROMPT, user_prompt)


def run_topic_agent(topic):
    """Research a topic and deliver an on-demand briefing."""
    provider = os.environ.get("LLM_PROVIDER", "openai")
    if provider == "anthropic":
        # TODO: add Anthropic topic support
        pass
    client, model, _ = _get_client_and_model()
    user_prompt = f"Brief me on {topic}"
    return _run_loop(client, model, TOPIC_SYSTEM_PROMPT, user_prompt)


import base64
from datetime import timezone

# In-memory store of recent briefings for the RSS feed
_briefing_history = []
_MAX_HISTORY = 20


def _add_to_history(title, content):
    """Store a briefing for the RSS feed."""
    now = datetime.now(timezone.utc)
    _briefing_history.insert(0, {
        "title": title,
        "content": content,
        "pub_date": now.strftime("%a, %d %b %Y %H:%M:%S +0000"),
        "guid": f"briefing-{now.strftime('%Y%m%d%H%M%S')}",
    })
    if len(_briefing_history) > _MAX_HISTORY:
        _briefing_history.pop()


def _build_rss():
    """Build an RSS 2.0 XML feed from briefing history."""
    items = ""
    for b in _briefing_history:
        items += f"""    <item>
      <title>{_xml_escape(b['title'])}</title>
      <description>{_xml_escape(b['content'])}</description>
      <pubDate>{b['pub_date']}</pubDate>
      <guid isPermaLink="false">{b['guid']}</guid>
    </item>
"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>OpenShortcuts Briefings</title>
    <description>Your personal AI briefings</description>
    <language>en-us</language>
    <lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
{items}  </channel>
</rss>"""


def _xml_escape(text):
    """Escape text for XML."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


class BriefingHandler(BaseHTTPRequestHandler):

    def _check_auth(self):
        """Check HTTP Basic Auth. Returns True if authorized."""
        feed_password = os.environ.get("FEED_PASSWORD")
        if not feed_password:
            return True  # No password set = open access

        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Basic "):
            self._send_auth_required()
            return False

        try:
            decoded = base64.b64decode(auth_header[6:]).decode()
            _, password = decoded.split(":", 1)
            if password == feed_password:
                return True
        except Exception:
            pass

        self._send_auth_required()
        return False

    def _send_auth_required(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="OpenShortcuts"')
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Unauthorized")

    def _send_json(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}

        if self.path == "/briefing":
            try:
                briefing = run_agent(
                    latitude=body.get("latitude"),
                    longitude=body.get("longitude"),
                    preferences=body.get("preferences"),
                )
                _add_to_history("Morning Briefing", briefing)
                self._send_json(200, {"briefing": briefing})
            except Exception as e:
                self._send_json(500, {"error": str(e)})

        elif self.path == "/topic":
            topic = body.get("topic", "").strip()
            if not topic:
                self._send_json(400, {"error": "Missing 'topic' field"})
                return
            try:
                briefing = run_topic_agent(topic)
                _add_to_history(f"Brief: {topic}", briefing)
                self._send_json(200, {"briefing": briefing})
            except Exception as e:
                self._send_json(500, {"error": str(e)})

        else:
            self.send_error(404)

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "healthy"})
            return

        if self.path == "/feed":
            if not self._check_auth():
                return
            rss = _build_rss().encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
            self.send_header("Content-Length", str(len(rss)))
            self.end_headers()
            self.wfile.write(rss)
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
