#!/usr/bin/env python3
"""Create and configure the Bedrock Agent via boto3.

This script creates the Morning Briefing agent, defines action groups
with function schemas, and prepares the agent for use.

Prerequisites:
    - AWS credentials configured (aws configure)
    - IAM role for the agent (created by CDK stack)
    - Tool Lambda function deployed (created by CDK stack)

Usage:
    python3 create_agent.py --role-arn <agent-role-arn> --lambda-arn <tool-lambda-arn>
"""

import argparse
import json
import sys
import time

try:
    import boto3
except ImportError:
    print("boto3 is required: pip install boto3")
    sys.exit(1)

# Import shared tool schemas and prompts
sys.path.insert(0, "..")
from prompts import SYSTEM_PROMPT
from tools import TOOL_SCHEMAS


def openai_schema_to_bedrock(tool_schema):
    """Convert OpenAI function schema to Bedrock function schema format."""
    func = tool_schema["function"]
    params = func.get("parameters", {})
    properties = params.get("properties", {})
    required = params.get("required", [])

    bedrock_params = {}
    for name, prop in properties.items():
        bedrock_params[name] = {
            "description": prop.get("description", ""),
            "type": prop.get("type", "string"),
            "required": name in required,
        }

    return {
        "name": func["name"],
        "description": func.get("description", ""),
        "parameters": bedrock_params,
    }


def create_agent(role_arn, lambda_arn, region="us-east-1"):
    """Create the Bedrock Agent with action groups."""
    client = boto3.client("bedrock-agent", region_name=region)

    # Create the agent
    print("Creating Bedrock Agent...")
    agent_resp = client.create_agent(
        agentName="morning-briefing",
        description="Personal morning briefing agent that gathers weather, news, calendar, and commute data to deliver a spoken briefing.",
        agentResourceRoleArn=role_arn,
        foundationModel="anthropic.claude-3-5-sonnet-20241022-v2:0",
        instruction=SYSTEM_PROMPT,
        idleSessionTTLInSeconds=600,
    )

    agent_id = agent_resp["agent"]["agentId"]
    print(f"Agent created: {agent_id}")

    # Wait for agent to be ready
    print("Waiting for agent to be ready...")
    while True:
        status = client.get_agent(agentId=agent_id)["agent"]["agentStatus"]
        if status == "NOT_PREPARED":
            break
        if status == "FAILED":
            print(f"Agent creation failed!")
            sys.exit(1)
        time.sleep(2)

    # Create action group with all tools as functions
    print("Creating action group...")
    functions = [openai_schema_to_bedrock(t) for t in TOOL_SCHEMAS]

    client.create_agent_action_group(
        agentId=agent_id,
        agentVersion="DRAFT",
        actionGroupName="briefing_tools",
        description="Tools for gathering morning briefing data",
        actionGroupExecutor={"lambda_": lambda_arn},
        functionSchema={"functions": functions},
    )

    # Prepare the agent (makes it invokable)
    print("Preparing agent...")
    client.prepare_agent(agentId=agent_id)

    # Wait for preparation
    while True:
        status = client.get_agent(agentId=agent_id)["agent"]["agentStatus"]
        if status == "PREPARED":
            break
        if status == "FAILED":
            print("Agent preparation failed!")
            sys.exit(1)
        time.sleep(2)

    # Create an alias for stable invocation
    print("Creating agent alias...")
    alias_resp = client.create_agent_alias(
        agentId=agent_id,
        agentAliasName="live",
        description="Production alias for morning briefing",
    )
    alias_id = alias_resp["agentAlias"]["agentAliasId"]

    print()
    print("=" * 50)
    print(f"  Agent ID:    {agent_id}")
    print(f"  Alias ID:    {alias_id}")
    print(f"  Region:      {region}")
    print()
    print("  Set these as environment variables on your")
    print("  invoke Lambda function:")
    print(f"    AGENT_ID={agent_id}")
    print(f"    AGENT_ALIAS_ID={alias_id}")
    print("=" * 50)

    return agent_id, alias_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create Morning Briefing Bedrock Agent")
    parser.add_argument("--role-arn", required=True, help="IAM role ARN for the agent")
    parser.add_argument("--lambda-arn", required=True, help="Tool executor Lambda ARN")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    args = parser.parse_args()

    create_agent(args.role_arn, args.lambda_arn, args.region)
