# Agents Architecture

OpenShortcuts agents are long-running AI processes that do real multi-step work
on your behalf — not just single inference calls. The iOS Shortcut is a thin
client: it captures input, POSTs to the agent, and displays the result.

```
┌──────────────┐         ┌──────────────────────────────┐
│  iOS Shortcut │   POST  │  Agent (runs server-side)     │
│              │ ───────► │                              │
│  • capture   │         │  1. Parse request             │
│    input     │         │  2. Call tools (weather API,  │
│  • POST to   │         │     calendar, news, etc.)     │
│    agent     │         │  3. Reason over results       │
│  • display   │  JSON   │  4. Maybe call more tools     │
│    result    │ ◄─────── │  5. Return final answer       │
│              │         │                              │
└──────────────┘         └──────────────────────────────┘
```

## Hosting Strategies

We support four hosting strategies. Pick the one that fits your needs:

| Strategy | Infra | Cost | Latency | Privacy | Setup Effort |
|----------|-------|------|---------|---------|-------------|
| **AWS Bedrock Agents** | Fully managed | Pay-per-invoke | ~5-15s | AWS-hosted | CDK deploy |
| **OpenAI Responses API** | Managed | Pay-per-token | ~3-10s | OpenAI-hosted | API key only |
| **Local (LangGraph + Ollama)** | Your machine | Free | ~5-20s | Full privacy | Python install |
| **ECS Container** | AWS Fargate | ~$5-15/mo | ~3-8s | AWS-hosted | CDK deploy |

### Strategy 1: AWS Bedrock Agents (All-AWS)

A fully managed agent on AWS. You define action groups (as Lambda functions or
return-control), attach a foundation model (Claude, Llama, etc.), and call
`InvokeAgent`. Bedrock handles the agent loop — tool selection, execution,
multi-turn reasoning — and returns the final answer.

```
iOS Shortcut
    │
    ▼
API Gateway (HTTPS endpoint)
    │
    ▼
Bedrock Agent (Claude on Bedrock)
    ├── Action Group: get_weather (Lambda → weather API)
    ├── Action Group: get_calendar (Lambda → Apple Calendar / Google Cal API)
    ├── Action Group: get_news (Lambda → news API)
    ├── Action Group: get_commute (Lambda → maps API)
    └── Knowledge Base (optional: personal notes, docs)
```

**Pros**: Zero infrastructure to manage, auto-scales, built-in session memory.
**Cons**: AWS lock-in, cold starts on Lambda, model selection limited to Bedrock catalog.

See: `agents/morning-briefing/aws-bedrock/`

### Strategy 2: OpenAI Responses API

The simplest option. A single HTTP call with tools defined. OpenAI's Responses
API handles the agent loop server-side — it calls your tools (via function
calling), reasons over results, and returns the final answer. The Shortcut
just POSTs and waits.

```
iOS Shortcut
    │
    ▼
OpenAI Responses API (/v1/responses)
    ├── Built-in: web_search (real-time web search)
    ├── Built-in: code_interpreter (run code)
    ├── Custom function: get_weather
    ├── Custom function: get_calendar
    └── Custom function: get_commute
```

Note: The Assistants API is deprecated (sunset Aug 2026). Use Responses API
for new projects. For custom function calling, you'll need a thin proxy
server to execute the functions and return results.

**Pros**: Simplest setup, best models, built-in web search.
**Cons**: No full server-side tool execution for custom functions (need proxy).

See: `agents/morning-briefing/openai-responses/`

### Strategy 3: Local (LangGraph + Ollama)

Run the agent entirely on your own hardware. LangGraph orchestrates the agent
loop, Ollama runs the LLM locally. A FastAPI server exposes the agent as an
HTTP endpoint your Shortcut can call.

```
iOS Shortcut
    │ (same network)
    ▼
FastAPI server (your machine)
    │
    ▼
LangGraph Agent
    ├── Ollama (llama3.2, qwen2.5, etc.)
    ├── Tool: get_weather (requests → weather API)
    ├── Tool: get_calendar (local calendar files / CalDAV)
    ├── Tool: get_news (requests → RSS / news API)
    └── Tool: get_commute (requests → maps API)
```

**Pros**: Full privacy, no API costs, works offline (except external tool calls).
**Cons**: Requires decent hardware (8GB+ RAM), slower inference, same-network only.

See: `agents/morning-briefing/local-langgraph/`

### Strategy 4: ECS Container (Personal Cloud Agent)

A Docker container running your agent on AWS Fargate. Always warm (or scale to
zero with provisioned concurrency). The setup wizard deploys the infra via CDK
and registers the endpoint in your shortcuts.

```
iOS Shortcut
    │
    ▼
ALB (HTTPS endpoint)
    │
    ▼
ECS Fargate Task (Docker container)
    │
    ▼
Python Agent (LangGraph or plain tool loop)
    ├── Any LLM provider (Claude API, OpenAI, Groq, etc.)
    ├── Tool: get_weather
    ├── Tool: get_calendar
    ├── Tool: get_news
    └── Tool: get_commute
```

**Pros**: Full control, any model, always available, low cost for personal use.
**Cons**: AWS account required, ~$5-15/mo for always-on, more setup.

See: `agents/morning-briefing/ecs-container/`

## Morning Briefing Agent

The first agent we're building. Tap a shortcut, get a personalized morning
briefing read aloud:

**Input**: Time of day, location (from phone)
**Tools the agent uses**:
- Weather API → current conditions + forecast
- Calendar API → today's meetings and events
- News API → headlines matching your interests
- Commute/Maps API → time to first meeting
- (Optional) Email summary → unread count + key senders

**Output**: A spoken briefing like:
> "Good morning. It's 52 degrees and cloudy, warming to 68 this afternoon.
> You have 3 meetings today — the first is your 9:30 standup in 45 minutes,
> 22 minutes away in current traffic. Top news: the Fed held rates steady.
> You have 12 unread emails, 2 from your manager."

The shortcut receives this as text and uses iOS TTS to read it aloud.
