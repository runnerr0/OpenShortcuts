#!/usr/bin/env python3
"""Morning Briefing agent using LangGraph + Ollama (fully local).

Runs entirely on your own hardware — no cloud APIs needed for the LLM.
External API calls (weather, news) still go out, but your prompts and
data never leave your machine.

Usage:
    # Make sure Ollama is running with a model pulled:
    ollama pull llama3.2

    # Install dependencies:
    pip install langgraph langchain-ollama

    # Start the agent server:
    python3 agent_server.py

    # Or with a different model:
    python3 agent_server.py --model qwen2.5

Dependencies:
    pip install langgraph langchain-ollama langchain-core
"""

import argparse
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from langchain_ollama import ChatOllama
    from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
    from langchain_core.tools import tool as langchain_tool
    from langgraph.graph import StateGraph, MessagesState, START, END
    from langgraph.prebuilt import ToolNode
except ImportError:
    print("Required packages: pip install langgraph langchain-ollama langchain-core")
    sys.exit(1)

# Add parent directory for shared tools/prompts
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools import (
    get_weather as _get_weather,
    get_news as _get_news,
    get_calendar_events as _get_calendar_events,
    get_commute_time as _get_commute_time,
    get_time_context as _get_time_context,
)
from prompts import SYSTEM_PROMPT, build_user_prompt


# --- Wrap shared tools as LangChain tools ---

@langchain_tool
def get_weather(latitude: float, longitude: float) -> str:
    """Get current weather conditions and forecast for a location."""
    return json.dumps(_get_weather(latitude, longitude))


@langchain_tool
def get_news(category: str = "general", count: int = 5) -> str:
    """Get top news headlines, optionally filtered by category."""
    return json.dumps(_get_news(category, count))


@langchain_tool
def get_calendar_events(date: str = None) -> str:
    """Get today's calendar events and meetings."""
    return json.dumps(_get_calendar_events(date))


@langchain_tool
def get_commute_time(origin_lat: float, origin_lon: float, destination: str) -> str:
    """Get estimated travel time between two locations."""
    return json.dumps(_get_commute_time(origin_lat, origin_lon, destination))


@langchain_tool
def get_time_context() -> str:
    """Get current date, time, and time-of-day context."""
    return json.dumps(_get_time_context())


ALL_TOOLS = [get_weather, get_news, get_calendar_events, get_commute_time, get_time_context]


def build_agent(model_name="llama3.2", ollama_host="http://localhost:11434"):
    """Build the LangGraph agent."""
    llm = ChatOllama(
        model=model_name,
        base_url=ollama_host,
    ).bind_tools(ALL_TOOLS)

    tool_node = ToolNode(ALL_TOOLS)

    def should_continue(state: MessagesState):
        """Decide whether to call tools or finish."""
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END

    def call_model(state: MessagesState):
        """Call the LLM with the current message history."""
        response = llm.invoke(state["messages"])
        return {"messages": [response]}

    # Build the graph
    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")

    return workflow.compile()


def run_agent(model_name, ollama_host, latitude=None, longitude=None, preferences=None):
    """Run the briefing agent and return the final response."""
    agent = build_agent(model_name, ollama_host)

    user_prompt = build_user_prompt(latitude, longitude, preferences)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    result = agent.invoke({"messages": messages})

    # Get the last AI message
    final_message = result["messages"][-1]
    return final_message.content


class BriefingHandler(BaseHTTPRequestHandler):
    """HTTP handler for briefing requests."""

    model_name = "llama3.2"
    ollama_host = "http://localhost:11434"

    def do_POST(self):
        if self.path != "/briefing":
            self.send_error(404)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}

        try:
            briefing = run_agent(
                self.model_name,
                self.ollama_host,
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

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    parser = argparse.ArgumentParser(description="Morning Briefing Agent (Local/Ollama)")
    parser.add_argument("--port", type=int, default=8090, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--model", default="llama3.2", help="Ollama model name")
    parser.add_argument("--ollama-host", default="http://localhost:11434", help="Ollama server URL")
    args = parser.parse_args()

    BriefingHandler.model_name = args.model
    BriefingHandler.ollama_host = args.ollama_host

    server = HTTPServer((args.host, args.port), BriefingHandler)
    print(f"Morning Briefing Agent (Ollama/{args.model}) running on http://{args.host}:{args.port}/briefing")
    print(f"Ollama host: {args.ollama_host}")
    print("Send POST with {latitude, longitude, preferences}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
