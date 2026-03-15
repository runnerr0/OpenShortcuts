# AWS Bedrock Agent — Morning Briefing

Fully managed agent on AWS. Bedrock handles the agent loop, tool selection,
and multi-turn reasoning. You just call `InvokeAgent` and get back the briefing.

## Architecture

```
iOS Shortcut
    │ HTTPS POST
    ▼
API Gateway (REST API)
    │
    ▼
Lambda (thin proxy → InvokeAgent)
    │
    ▼
Bedrock Agent (Claude 3.5 Sonnet on Bedrock)
    ├── Action Group: weather_tools
    │   └── Lambda: calls Open-Meteo API
    ├── Action Group: news_tools
    │   └── Lambda: calls news API
    ├── Action Group: calendar_tools
    │   └── Lambda: calls CalDAV / Google Calendar
    ├── Action Group: commute_tools
    │   └── Lambda: calls maps API
    └── Action Group: time_tools
        └── Lambda: returns current time context
```

## Deploy

```bash
cd aws-bedrock
pip install -r requirements.txt
cdk deploy
```

## Cost Estimate (Personal Use)

- Bedrock Claude: ~$0.003/invocation (input) + ~$0.015/invocation (output)
- Lambda: free tier covers ~1M requests/month
- API Gateway: free tier covers ~1M requests/month
- **Total**: ~$1-5/month for daily use
