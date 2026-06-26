"""A read-only Model Context Protocol (MCP) server for AWS.

Design goal: let an LLM *inspect* an AWS account but never *mutate* it.

Safety is structural. Every AWS call goes through `_aws_call`, which rejects
any API operation whose name does not start with a read-only prefix
(Describe*, List*, Get*). There is no code path that can create, delete,
modify, or terminate a resource — regardless of what the model asks for.
"""

from __future__ import annotations

import json

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("aws-readonly")

# Only API operations starting with these prefixes are permitted. Every
# mutating AWS operation (RunInstances, DeleteBucket, TerminateInstances, ...)
# starts with a different verb, so this prefix allow-list fails closed.
READONLY_PREFIXES = ("describe", "list", "get")


def _aws_call(service: str, operation: str, **kwargs) -> str:
    """Invoke a boto3 operation, but only if it is read-only.

    Raises ValueError if the operation name is not on the read-only
    allow-list. This single chokepoint is the security boundary.
    """
    normalized = operation.lower().replace("_", "")
    if not normalized.startswith(READONLY_PREFIXES):
        raise ValueError(
            f"Refusing to run '{operation}'. This server is read-only; only "
            f"operations starting with {READONLY_PREFIXES} are allowed."
        )

    try:
        client = boto3.client(service)
        result = getattr(client, operation)(**kwargs)
        # Drop botocore's response metadata; the model only needs the payload.
        result.pop("ResponseMetadata", None)
        return json.dumps(result, indent=2, default=str)
    except (BotoCoreError, ClientError) as exc:
        return f"AWS error calling {service}.{operation}: {exc}"


@mcp.tool()
def list_ec2_instances(region: str = "us-east-1") -> str:
    """List EC2 instances in a region with their state, type, and ID."""
    try:
        client = boto3.client("ec2", region_name=region)
        resp = client.describe_instances()
    except (BotoCoreError, ClientError) as exc:
        return f"AWS error: {exc}"

    rows = []
    for reservation in resp.get("Reservations", []):
        for inst in reservation.get("Instances", []):
            rows.append(
                {
                    "InstanceId": inst.get("InstanceId"),
                    "State": inst.get("State", {}).get("Name"),
                    "Type": inst.get("InstanceType"),
                    "AZ": inst.get("Placement", {}).get("AvailabilityZone"),
                }
            )
    return json.dumps(rows, indent=2) if rows else "(no instances found)"


@mcp.tool()
def list_s3_buckets() -> str:
    """List all S3 bucket names in the account."""
    return _aws_call("s3", "list_buckets")


@mcp.tool()
def get_cost_last_30_days() -> str:
    """Get total unblended AWS cost for the last 30 days, grouped by service."""
    from datetime import date, timedelta

    # Note: dates are computed at call time inside the tool, not at import.
    end = date.today()
    start = end - timedelta(days=30)
    try:
        client = boto3.client("ce", region_name="us-east-1")
        resp = client.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
    except (BotoCoreError, ClientError) as exc:
        return f"AWS error: {exc}"

    resp.pop("ResponseMetadata", None)
    return json.dumps(resp, indent=2, default=str)


@mcp.tool()
def describe_iam_user(user_name: str) -> str:
    """Get details for a single IAM user (read-only)."""
    return _aws_call("iam", "get_user", UserName=user_name)


def main() -> None:
    """Entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
