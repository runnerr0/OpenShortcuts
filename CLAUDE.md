# OpenShortcuts — Project Instructions

## Project Overview

OpenShortcuts is an open-source collection of AI-powered iOS Shortcuts backed by
cloud-hosted agents. The flagship agent is the **Morning Briefing** — a personal
assistant that gathers weather, news, calendar, and commute info, then delivers
a spoken briefing via Siri.

## Architecture

```
iOS Shortcut → POST /briefing or /topic → Python HTTP server → LLM (Groq/OpenAI/Anthropic)
                                              ↕
                                        Tool calls (weather, news, web_search, calendar, commute)
```

**Key directories:**
- `agents/morning-briefing/` — Shared tools, prompts, tests
- `agents/morning-briefing/ecs-container/` — Production HTTP server (ECS/Fargate)
- `agents/morning-briefing/openai-responses/` — OpenAI Responses API variant
- `agents/morning-briefing/aws-bedrock/` — AWS Bedrock variant
- `agents/morning-briefing/local-langgraph/` — LangGraph local variant
- `setup-wizard/` — Interactive setup for API keys and preferences
- `shortcuts/` — iOS Shortcut files (.shortcut)

## Development Practices

- **LLM Provider:** Groq (Llama 3.3 70B) for dev/testing — free, fast (2-3s round-trip)
- **Tests:** `python3 test_tools.py` in `agents/morning-briefing/` — all tests must pass
- **No API keys in code** — always via environment variables
- **Tools are shared** — `tools.py` and `prompts.py` are provider-agnostic
- **Spoken output** — all briefing text must sound natural read aloud by TTS

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | /briefing | Morning briefing (lat/lon, preferences) |
| POST | /topic | On-demand topic brief ("brief me on X") |
| GET | /feed | RSS feed of past briefings (HTTP Basic Auth) |
| GET | /health | Health check for load balancer |

## PAI Integration

This project uses PAI (Personal AI Infrastructure) v4.0.3 capabilities.
The full system is installed at `~/.claude/PAI/`.

### The Algorithm

For complex, multi-step work, load and follow `~/.claude/PAI/Algorithm/v3.7.0.md`.
This is the 7-phase problem-solving loop:
**OBSERVE → THINK → PLAN → BUILD → EXECUTE → VERIFY → LEARN**

### Context Routing

When you need PAI system context, read `~/.claude/PAI/CONTEXT_ROUTING.md` for file paths.

### Thinking Tools

Invoke via the Skill tool when the situation calls for it:

| Skill | When to Use |
|-------|-------------|
| **Council** | Multiple valid approaches worth debating |
| **RedTeam** | Stress-test a proposal, find fatal flaws |
| **FirstPrinciples** | Challenge unexamined assumptions |
| **BeCreative** | Divergent thinking, brainstorming |
| **Science** | Hypothesis testing, structured experiments |
| **Research** | Deep investigation with parallel agents |

### Agents

14 specialized agents available at `~/.claude/agents/`:
Architect, Engineer, Designer, QATester, UIReviewer, Pentester,
ClaudeResearcher, PerplexityResearcher, GeminiResearcher, and more.

## Running Locally

```bash
# Start the server
GROQ_API_KEY=gsk_... LLM_PROVIDER=groq python3 agents/morning-briefing/ecs-container/agent_server.py

# Test morning briefing
curl -X POST http://localhost:8090/briefing -H "Content-Type: application/json" \
  -d '{"latitude": 37.7749, "longitude": -122.4194, "preferences": "technology"}'

# Test topic briefing
curl -X POST http://localhost:8090/topic -H "Content-Type: application/json" \
  -d '{"topic": "quantum computing"}'

# Run tests
cd agents/morning-briefing && python3 test_tools.py
```
