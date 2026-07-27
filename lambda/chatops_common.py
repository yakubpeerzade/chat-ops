"""
chatops_common — shared helpers for the ChatOps provisioning lambdas.

Deploy as a Lambda layer, or copy into each function package.

Fixes vs original inline code:
  - GitHub token comes from Secrets Manager, not a plaintext env var
  - every HTTP call has a timeout (urlopen has NO default timeout)
  - 409/422 conflicts are retried with the sha RE-READ each attempt
  - HTTPError bodies are surfaced so failures are diagnosable
  - GitHubConflict is raised as a distinct type so Step Functions can Retry on it
  - atomic sequence numbers via DynamoDB ADD (replaces the static COUNTER env var)
  - HCL values are emitted via json.dumps to prevent injection
"""

import base64
import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request

import boto3
from botocore.config import Config

HTTP_TIMEOUT = 10
GITHUB_API = "https://api.github.com"

_boto_cfg = Config(retries={"max_attempts": 5, "mode": "standard"})
_ddb = boto3.client("dynamodb", config=_boto_cfg)
_secrets = boto3.client("secretsmanager", config=_boto_cfg)

_token_cache = None


class GitHubConflict(Exception):
    """Retryable: branch head moved or the ref is locked."""


class GitHubError(Exception):
    """Non-retryable GitHub failure."""


# ------------------------------------------------------------------ credentials

def github_token():
    """Fetched once per cold start and cached in module scope."""
    global _token_cache
    if _token_cache:
        return _token_cache

    secret_id = os.environ.get("GITHUB_TOKEN_SECRET_ID")
    if secret_id:
        raw = _secrets.get_secret_value(SecretId=secret_id)["SecretString"]
        try:
            _token_cache = json.loads(raw)["token"]
        except (json.JSONDecodeError, KeyError, TypeError):
            _token_cache = raw.strip()
    else:
        # Transitional only. Remove once the secret is in place.
        _token_cache = os.environ["GITHUB_TOKEN"]
    return _token_cache


def _headers():
    return {
        "Authorization": f"Bearer {github_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "jade-chatops/1.0",
    }


# ------------------------------------------------------------------ sequencing

def next_sequence(project, env):
    """
    Atomic monotonic counter per project+env.

    ADD on a missing attribute initialises to 0 then adds, so the first call
    returns 1. Single round trip, no read-modify-write race.
    """
    resp = _ddb.update_item(
        TableName=os.environ["COUNTER_TABLE"],
        Key={"counter_key": {"S": f"{project}#{env}"}},
        UpdateExpression="ADD seq :one",
        ExpressionAttributeValues={":one": {"N": "1"}},
        ReturnValues="UPDATED_NEW",
    )
    return int(resp["Attributes"]["seq"]["N"])


# ------------------------------------------------------------------ HCL writing

def hcl_assignments(pairs, width=16):
    """
    Render tfvars lines with injection-safe values.

    json.dumps produces a JSON string literal, which is also a valid HCL string
    literal, and correctly escapes quotes, backslashes and newlines. The original
    f-string approach let a value containing a quote inject arbitrary HCL into a
    file the pipeline then executes with its own IAM role.
    """
    lines = []
    for key, value in pairs:
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, (int, float)):
            rendered = str(value)
        else:
            rendered = json.dumps(str(value))
        lines.append(f"{key.ljust(width)} = {rendered}")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ GitHub calls

def _request(url, method, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as res:
            raw = res.read().decode()
            return res.getcode(), (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode()[:500]
        except Exception:
            pass
        if exc.code in (409, 422):
            raise GitHubConflict(f"{exc.code} on {method} {url}: {detail}")
        if exc.code == 404:
            return 404, {}
        raise GitHubError(f"{exc.code} on {method} {url}: {detail}")
    except urllib.error.URLError as exc:
        # Network-level: worth retrying, so surface as conflict-class.
        raise GitHubConflict(f"network error on {method} {url}: {exc.reason}")


def get_sha(repo, path, branch):
    """Return the blob sha, or None if the file does not exist."""
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}?ref={urllib.parse.quote(branch)}"
    code, body = _request(url, "GET")
    if code == 404:
        return None
    return body.get("sha")


def commit_file(repo, path, content, message, branch, attempts=5):
    """
    Create or update a file, retrying conflicts.

    The sha is re-read on every attempt. Reusing a stale sha after a 409 just
    produces another 409 — that is why the original code could not be fixed by
    wrapping it in a naive retry.
    """
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    for attempt in range(attempts):
        sha = get_sha(repo, path, branch)
        payload = {
            "message": message,
            "content": _b64(content),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        try:
            _, body = _request(url, "PUT", payload)
            return body.get("commit", {}).get("sha")
        except GitHubConflict:
            if attempt == attempts - 1:
                raise
            _backoff(attempt)


def delete_file(repo, path, message, branch, attempts=5):
    """Delete a file. Returns False if it was already absent."""
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    for attempt in range(attempts):
        sha = get_sha(repo, path, branch)
        if sha is None:
            return False
        try:
            _request(url, "DELETE", {"message": message, "sha": sha, "branch": branch})
            return True
        except GitHubConflict:
            if attempt == attempts - 1:
                raise
            _backoff(attempt)


def move_file(repo, src, dst, message, branch):
    """
    Copy then delete — used for the destroy flow, where the manifest must survive
    so `terraform destroy -var-file` still has its inputs.
    """
    url = f"{GITHUB_API}/repos/{repo}/contents/{urllib.parse.quote(src)}?ref={urllib.parse.quote(branch)}"
    code, body = _request(url, "GET")
    if code == 404:
        return False
    content = base64.b64decode(body["content"]).decode()
    commit_file(repo, dst, content, message, branch)
    delete_file(repo, src, message, branch)
    return True


def _b64(text):
    return base64.b64encode(text.encode()).decode()


def _backoff(attempt):
    time.sleep((2 ** attempt) * 0.5 + random.random())
