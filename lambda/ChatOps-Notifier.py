"""
ChatOps-Notifier

The one function the corrected state machine references that you don't have yet.
Deploy this, or repoint every Catch at 'Provisioning Failed' until you do.

Records the failure so it is not invisible, then tells the requester. The
original workflow had no Catch anywhere, so a failure left no DynamoDB row and
sent no message - the user re-submitted, which compounded the duplicate-resource
problem.

Env vars:
  RESOURCE_TABLE            aws-ops-resources
  SLACK_WEBHOOK_SECRET_ID   optional; Secrets Manager id holding {"url": "..."}
"""

import json
import os
import urllib.error
import urllib.request

import boto3
from botocore.config import Config

_cfg = Config(retries={"max_attempts": 5, "mode": "standard"})
_ddb = boto3.client("dynamodb", config=_cfg)
_secrets = boto3.client("secretsmanager", config=_cfg)

HTTP_TIMEOUT = 5
_webhook_cache = None


def lambda_handler(event, context):
    outcome = event.get("outcome", "FAILED")
    error = event.get("error") or {}
    execution = event.get("execution", "unknown")
    original = event.get("input") or {}

    cause = _readable_cause(error)
    parsed = _parsed_input(original)
    request_id = parsed.get("request_id")

    if request_id:
        _record_failure(request_id, parsed, outcome, cause)

    text = (
        f":x: Provisioning {outcome.lower()}\n"
        f"*Request:* {request_id or 'unknown'}\n"
        f"*Project:* {parsed.get('project', '?')} / {parsed.get('env', '?')}\n"
        f"*Type:* {parsed.get('resource_type', '?')}\n"
        f"*Reason:* {cause}\n"
        f"*Execution:* {execution}"
    )

    _notify(original, text)

    # Return rather than raise. The state machine transitions to a Fail state
    # next; raising here would just mask the original cause.
    return {"notified": True, "request_id": request_id, "cause": cause}


def _readable_cause(error):
    """Step Functions puts the Lambda error JSON in Cause as a nested string."""
    if not isinstance(error, dict):
        return str(error)[:400]

    cause = error.get("Cause") or ""
    err = error.get("Error") or "UnknownError"

    try:
        detail = json.loads(cause)
        msg = detail.get("errorMessage") or detail.get("Message") or cause
    except (json.JSONDecodeError, TypeError):
        msg = cause

    return f"{err}: {str(msg)[:400]}" if msg else err


def _parsed_input(original):
    """Best-effort extraction; the failure may have happened before parsing."""
    node = original.get("parsedInput")
    if isinstance(node, dict):
        inner = node.get("parsed")
        if isinstance(inner, dict):
            return inner
        return node

    raw = original.get("body")
    if isinstance(raw, str):
        try:
            body = json.loads(raw)
            if isinstance(body, dict):
                return body
        except json.JSONDecodeError:
            pass
    elif isinstance(raw, dict):
        return raw
    return {}


def _record_failure(request_id, parsed, outcome, cause):
    """
    A bare put would clobber a PENDING row's other attributes, so update in
    place and let the row be created if the failure happened before logging.
    """
    table = os.environ.get("RESOURCE_TABLE")
    if not table:
        # os.environ["X"] raises KeyError whose str() is just "'X'", which logs
        # as a cryptic "could not record failure: 'RESOURCE_TABLE'".
        print("WARN RESOURCE_TABLE env var is not set; failure not recorded to DynamoDB")
        return
    try:
        _ddb.update_item(
            TableName=table,
            Key={
                "request_id": {"S": request_id},
                "resource_id": {"S": parsed.get("resource_id") or f"unresolved#{request_id}"},
            },
            UpdateExpression=(
                "SET #s = :s, failure_reason = :r, updated_at = :t"
            ),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": {"S": outcome},
                ":r": {"S": cause[:900]},
                ":t": {"S": _now()},
            },
        )
    except Exception as exc:  # never let bookkeeping swallow the notification
        print(f"WARN could not record failure for {request_id}: {exc}")


def _notify(original, text):
    url = _response_url(original) or _webhook()
    if not url:
        print("No response_url or webhook configured; failure not delivered.")
        print(text)
        return

    payload = json.dumps({"text": text, "response_type": "ephemeral"}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as res:
            print(f"Notified via {url.split('/')[2]}: {res.getcode()}")
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        print(f"WARN notification failed: {exc}")


def _response_url(original):
    """
    Slack slash commands carry a response_url valid for 30 minutes. Preferred
    over a webhook because it replies in the originating channel and thread.
    """
    raw = original.get("body")
    if isinstance(raw, str):
        if "response_url=" in raw:
            import urllib.parse
            return urllib.parse.parse_qs(raw).get("response_url", [None])[0]
        try:
            body = json.loads(raw)
            if isinstance(body, dict):
                return body.get("response_url")
        except json.JSONDecodeError:
            return None
    elif isinstance(raw, dict):
        return raw.get("response_url")
    return None


def _webhook():
    global _webhook_cache
    if _webhook_cache is not None:
        return _webhook_cache

    secret_id = os.environ.get("SLACK_WEBHOOK_SECRET_ID")
    if not secret_id:
        _webhook_cache = ""
        return _webhook_cache
    try:
        raw = _secrets.get_secret_value(SecretId=secret_id)["SecretString"]
        try:
            _webhook_cache = json.loads(raw).get("url", "")
        except json.JSONDecodeError:
            _webhook_cache = raw.strip()
    except Exception as exc:
        print(f"WARN could not read webhook secret: {exc}")
        _webhook_cache = ""
    return _webhook_cache


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
