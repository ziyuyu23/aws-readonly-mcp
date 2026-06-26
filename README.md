# aws-readonly-mcp

A **read-only** [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server that lets
an LLM *inspect* an AWS account — list EC2 instances, S3 buckets, IAM users, and cost — but
**never mutate it**.

## Why I built it

When I help teams understand their cloud, I want an LLM that can answer "what's running and what's
it costing me?" without any ability to change the account. So the read-only guarantee is
structural, not a matter of trusting the model.

Every AWS call routes through a single function that checks the operation name against an
allow-list of read-only prefixes (`describe*`, `list*`, `get*`). There is **no code path** that can
`Run`, `Create`, `Delete`, `Terminate`, or `Modify` anything. If the model asks for a mutation, the
server refuses. Pair it with a read-only IAM policy (e.g. AWS-managed `ReadOnlyAccess`) for
defense in depth — the server enforces it in code, IAM enforces it at the boundary.

## What it does

| Tool | Description |
|------|-------------|
| `list_ec2_instances` | EC2 instances in a region: ID, state, type, AZ |
| `list_s3_buckets` | All S3 bucket names in the account |
| `get_cost_last_30_days` | Total cost over the last 30 days, grouped by service |
| `describe_iam_user` | Details for a single IAM user |

## Quick start

```bash
# 1. Install (using uv — https://docs.astral.sh/uv/)
uv sync

# 2. Configure AWS credentials. STRONGLY recommended: use a profile whose IAM
#    role has only ReadOnlyAccess, so even a bug cannot mutate anything.
export AWS_PROFILE=my-readonly-profile
aws sts get-caller-identity   # confirm you're who you expect

# 3. Run the server
uv run aws-readonly-mcp
```

### Connect it to Claude Desktop

```json
{
  "mcpServers": {
    "aws-readonly": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/aws-readonly-mcp", "run", "aws-readonly-mcp"],
      "env": { "AWS_PROFILE": "my-readonly-profile" }
    }
  }
}
```

Then ask Claude things like *"Which services drove my AWS bill last month?"* — it calls
`get_cost_last_30_days`, reasons over the breakdown, and explains — but it physically cannot change
your account.

## Design decisions

- **Allow-list by operation prefix.** Read-only AWS operations are `Describe*`/`List*`/`Get*`. I
  allow those prefixes and reject everything else, so the boundary fails closed.
- **One chokepoint.** All boto3 calls go through `_aws_call`; the security boundary is one
  auditable function.
- **Defense in depth.** The README pushes you toward a `ReadOnlyAccess` IAM role so there are *two*
  independent guarantees (code + IAM), not one.
- **Trimmed responses.** Botocore `ResponseMetadata` is stripped so the model sees only the useful
  payload, saving tokens.

## What I'd do next

- Add pagination for accounts with many resources.
- Add a small eval asserting every mutating operation is refused.
- Support assuming a cross-account read-only role per request.

## License

MIT
