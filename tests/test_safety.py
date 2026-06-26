"""Safety tests: the server must refuse every mutating AWS operation.

These assert the security boundary — no write operation can reach boto3 —
rather than testing happy-path output (which would need live AWS creds).
"""

import pytest

from aws_readonly_mcp.server import _aws_call, READONLY_PREFIXES

# Operations that change account state. None should ever be runnable.
MUTATING_OPERATIONS = [
    "run_instances",
    "terminate_instances",
    "delete_bucket",
    "create_bucket",
    "put_object",
    "modify_instance_attribute",
    "delete_user",
    "create_user",
    "attach_role_policy",
    "stop_instances",
]


@pytest.mark.parametrize("operation", MUTATING_OPERATIONS)
def test_mutating_operations_are_refused(operation):
    """Every mutating operation must raise before boto3 is ever invoked."""
    with pytest.raises(ValueError, match="read-only"):
        _aws_call("ec2", operation)


def test_readonly_prefixes_are_lowercase():
    """The allow-list must be lowercase so normalized comparison works."""
    assert all(p == p.lower() for p in READONLY_PREFIXES)


@pytest.mark.parametrize(
    "operation", ["describe_instances", "list_buckets", "get_user"]
)
def test_readonly_operations_pass_the_gate(operation):
    """Read-only operations get past the verb check (they fail later only on
    missing AWS creds, not on the safety gate — so we assert the error, if
    any, is NOT the read-only refusal)."""
    result = _aws_call("ec2", operation)
    assert "This server is read-only" not in result
