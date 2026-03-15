"""AWS CDK stack for the Morning Briefing Bedrock Agent.

Deploys:
- Bedrock Agent with Claude as the foundation model
- Lambda functions for each tool (action group)
- API Gateway REST endpoint for the iOS Shortcut to call
- IAM roles with least-privilege access

Usage:
    cdk init app --language python
    # Copy this file into the stack
    cdk deploy
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_bedrock as bedrock,
)
from constructs import Construct


class MorningBriefingAgentStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # --- IAM Role for the Bedrock Agent ---
        agent_role = iam.Role(
            self, "AgentRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="Role for Morning Briefing Bedrock Agent",
        )
        agent_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=["arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-sonnet-*"],
        ))

        # --- Lambda: Tool executor ---
        # Single Lambda that handles all tools via event routing
        tool_lambda = lambda_.Function(
            self, "ToolExecutor",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("lambda/tools"),
            timeout=Duration.seconds(30),
            memory_size=256,
            description="Executes Morning Briefing agent tools (weather, news, etc.)",
        )

        # --- Lambda: API Gateway proxy → InvokeAgent ---
        invoke_lambda = lambda_.Function(
            self, "InvokeProxy",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("lambda/invoke"),
            timeout=Duration.seconds(60),
            memory_size=256,
            description="Proxies iOS Shortcut requests to Bedrock InvokeAgent",
        )
        invoke_lambda.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeAgent"],
            resources=["*"],  # Scoped to account by default
        ))

        # --- API Gateway ---
        api = apigw.RestApi(
            self, "BriefingAPI",
            rest_api_name="morning-briefing",
            description="Morning Briefing Agent API for iOS Shortcuts",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=["POST"],
            ),
        )

        briefing_resource = api.root.add_resource("briefing")
        briefing_resource.add_method(
            "POST",
            apigw.LambdaIntegration(invoke_lambda),
        )

        # --- Outputs ---
        CfnOutput(self, "ApiUrl",
            value=api.url + "briefing",
            description="Endpoint URL for iOS Shortcut",
        )

        # --- NOTE: Bedrock Agent creation ---
        # As of early 2026, CDK L2 constructs for Bedrock Agents are still
        # maturing. The agent itself is best created via:
        #
        # 1. AWS Console (Bedrock → Agents → Create)
        # 2. boto3 (see create_agent.py)
        # 3. CloudFormation AWS::Bedrock::Agent (L1 construct)
        #
        # Key configuration:
        #   - Foundation Model: anthropic.claude-3-5-sonnet-20241022-v2:0
        #   - Instruction: (paste from prompts.py SYSTEM_PROMPT)
        #   - Action Groups: attach tool_lambda with function schemas
        #   - Idle timeout: 600 seconds
        #
        # After creating the agent, update invoke_lambda with:
        #   AGENT_ID and AGENT_ALIAS_ID environment variables
