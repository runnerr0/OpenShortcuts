"""AWS CDK stack for ECS Fargate deployment of the Morning Briefing agent.

Deploys:
- VPC with public subnets
- ECS Cluster + Fargate Service
- ALB with HTTPS (optional, HTTP for dev)
- ECR repository for the container image
- Secrets Manager for API keys

Usage:
    cdk deploy --context llm_provider=openai
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ecr_assets as ecr_assets,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class MorningBriefingECSStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        llm_provider = self.node.try_get_context("llm_provider") or "openai"

        # --- VPC ---
        vpc = ec2.Vpc(self, "AgentVPC",
            max_azs=2,
            nat_gateways=0,  # Save cost — public subnets only
        )

        # --- ECS Cluster ---
        cluster = ecs.Cluster(self, "AgentCluster",
            vpc=vpc,
            cluster_name="morning-briefing",
        )

        # --- Secret for API key ---
        api_key_secret = secretsmanager.Secret(self, "ApiKeySecret",
            secret_name="morning-briefing/api-key",
            description=f"API key for {llm_provider}",
        )

        # --- Fargate Service with ALB ---
        service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "AgentService",
            cluster=cluster,
            cpu=256,           # 0.25 vCPU — plenty for an HTTP proxy
            memory_limit_mib=512,
            desired_count=1,   # Single instance for personal use
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset("."),  # Build from Dockerfile
                container_port=8090,
                environment={
                    "LLM_PROVIDER": llm_provider,
                    "PORT": "8090",
                },
                secrets={
                    "OPENAI_API_KEY": ecs.Secret.from_secrets_manager(api_key_secret)
                    if llm_provider == "openai" else
                    ecs.Secret.from_secrets_manager(api_key_secret),
                },
            ),
            public_load_balancer=True,
            listener_port=80,  # Use 443 with a certificate for production
        )

        # Health check
        service.target_group.configure_health_check(
            path="/health",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
        )

        # Scale to zero when not in use (cost optimization)
        scaling = service.service.auto_scale_task_count(
            min_capacity=0,
            max_capacity=2,
        )
        # Scale based on request count
        scaling.scale_on_request_count("RequestScaling",
            requests_per_target=10,
            target_group=service.target_group,
            scale_in_cooldown=Duration.minutes(15),
            scale_out_cooldown=Duration.seconds(30),
        )

        # --- Outputs ---
        CfnOutput(self, "AgentUrl",
            value=f"http://{service.load_balancer.load_balancer_dns_name}/briefing",
            description="Agent endpoint URL for iOS Shortcut",
        )
        CfnOutput(self, "SecretArn",
            value=api_key_secret.secret_arn,
            description="Store your API key here: aws secretsmanager put-secret-value ...",
        )
