"""
ChatOps-Input-Parser  (corrected)

Fixes vs original:
  - handles isBase64Encoded bodies (API Gateway sets this for non-text content types)
  - handles application/x-www-form-urlencoded (Slack slash commands are NOT JSON)
  - handles Google Chat's nested message.text
  - handles body == None (POST with no body)
  - handles explicit JSON nulls (dict.get(k, "") returns None when k exists with null)
  - validates env / resource_type / instance_type against allowlists
  - enforces a strict charset on project so it cannot escape the git path
  - generates a unique request_id instead of a deterministic collision-prone one
"""

import base64
import json
import re
import urllib.parse
import uuid

ALLOWED_ENVS = {"dev", "qa", "stage"}
ALLOWED_RESOURCE_TYPES = {"ec2", "s3"}

# Cost guardrail as much as a correctness one. Extend deliberately.
ALLOWED_INSTANCE_TYPES = {
    "t2.micro", "t2.small", "t2.medium",
    "t3.micro", "t3.small", "t3.medium", "t3.large",
    "t3a.micro", "t3a.small", "t3a.medium",
    "m5.large", "m5.xlarge",
}
DEFAULT_INSTANCE_TYPE = "t3.micro"

ALLOWED_OS = {"ubuntu", "windows", "amazonlinux23"}
DEFAULT_OS = "ubuntu"

# Must be a safe path component AND a valid tag / bucket-name fragment.
PROJECT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,28}[a-z0-9]$")
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{3,64}$")
OWNER_RE = re.compile(r"^[A-Za-z0-9 ._@-]{1,64}$")


class ValidationError(Exception):
    """User-facing input problem. Not retryable."""


def lambda_handler(event, context):
    body = _extract_body(event)
    fields = _read_fields(body)
    return _validate(fields)


# ---------------------------------------------------------------- body decoding

def _extract_body(event):
    """Return a dict from any of the payload shapes we actually receive."""
    if not isinstance(event, dict):
        raise ValidationError("Event is not an object.")

    # Direct Step Functions / test invocation: no HTTP envelope at all.
    if "body" not in event:
        return event

    raw = event.get("body")
    if raw is None:
        raise ValidationError("Request body is empty.")

    if isinstance(raw, dict):
        return raw

    if not isinstance(raw, str):
        raise ValidationError(f"Unsupported body type: {type(raw).__name__}")

    # API Gateway base64-encodes bodies whose content type it doesn't treat as text.
    if event.get("isBase64Encoded"):
        try:
            raw = base64.b64decode(raw).decode("utf-8")
        except Exception as exc:
            raise ValidationError(f"Could not base64-decode body: {exc}")

    raw = raw.strip()
    if not raw:
        raise ValidationError("Request body is empty.")

    content_type = _header(event, "content-type").lower()

    if "application/x-www-form-urlencoded" in content_type or (
        "=" in raw and not raw.startswith(("{", "["))
    ):
        # Slack slash commands land here.
        parsed = urllib.parse.parse_qs(raw, keep_blank_values=True)
        return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}

    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Body is not valid JSON or form data: {exc}")

    if not isinstance(decoded, dict):
        raise ValidationError("Body must decode to an object.")
    return decoded


def _header(event, name):
    """Case-insensitive header lookup across REST v1 and HTTP v2 event shapes."""
    for key in ("headers", "multiValueHeaders"):
        headers = event.get(key) or {}
        if not isinstance(headers, dict):
            continue
        for k, v in headers.items():
            if k.lower() == name.lower():
                return v[0] if isinstance(v, list) and v else (v or "")
    return ""


# ---------------------------------------------------------------- field reading

def _read_fields(body):
    """Pull canonical fields out of whichever integration sent this."""
    text = _find_message_text(body)

    if text:
        return {
            "project": _extract_value(text, "project"),
            "env": _extract_value(text, "env") or "dev",
            "resource_type": _infer_resource_type(text),
            "requester_name": (
                _extract_value(text, "owner")
                or _sender_name(body)
                or "unknown"
            ),
            "approver_name": "Auto-Approved",
            "request_id": _extract_value(text, "ticket") or _new_request_id(),
            "instance_type": _extract_value(text, "type") or DEFAULT_INSTANCE_TYPE,
            "os_name": _extract_os(text),
        }

    # Structured Help Desk payload. Note `or` throughout, never dict.get(k, default),
    # so an explicit JSON null falls through to the fallback instead of becoming None.
    return {
        "project": body.get("project") or body.get("project_code"),
        "env": body.get("env") or body.get("environment") or "dev",
        "resource_type": body.get("resource_type") or "",
        "requester_name": body.get("requester_name") or body.get("owner") or "unknown",
        "approver_name": body.get("approver_name") or "Authorized Platform Admin",
        "request_id": body.get("request_id") or body.get("ticket_id"),
        "instance_type": body.get("instance_type") or body.get("type") or DEFAULT_INSTANCE_TYPE,
        "os_name": body.get("os_name") or DEFAULT_OS,
    }


def _find_message_text(body):
    """Slack puts it in `text`. Google Chat nests it under message.text."""
    for candidate in (
        body.get("text"),
        (body.get("message") or {}).get("text") if isinstance(body.get("message"), dict) else None,
        (body.get("message") or {}).get("argumentText") if isinstance(body.get("message"), dict) else None,
        body.get("argumentText"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _sender_name(body):
    message = body.get("message")
    if isinstance(message, dict):
        sender = message.get("sender")
        if isinstance(sender, dict) and sender.get("displayName"):
            return sender["displayName"]
    return body.get("user_name")  # Slack


def _new_request_id():
    return f"CHAT-{uuid.uuid4().hex[:12].upper()}"


# ---------------------------------------------------------------- validation

def _validate(f):
    project = (f["project"] or "").strip().lower()
    if not project:
        raise ValidationError("Missing required field: project.")
    if not PROJECT_RE.match(project):
        raise ValidationError(
            f"Invalid project '{project}'. Use 3-30 lowercase letters, digits or "
            "hyphens, starting and ending alphanumeric."
        )

    env = (f["env"] or "").strip().lower()
    if env not in ALLOWED_ENVS:
        raise ValidationError(
            f"Invalid env '{env}'. Allowed: {', '.join(sorted(ALLOWED_ENVS))}."
        )

    resource_type = (f["resource_type"] or "").strip().lower()
    if resource_type not in ALLOWED_RESOURCE_TYPES:
        raise ValidationError(
            f"Invalid resource_type '{resource_type}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_RESOURCE_TYPES))}."
        )

    request_id = (f["request_id"] or "").strip()
    if not REQUEST_ID_RE.match(request_id):
        raise ValidationError("A valid request_id (3-64 chars) is required.")

    instance_type = (f["instance_type"] or DEFAULT_INSTANCE_TYPE).strip().lower()
    os_name = (f["os_name"] or DEFAULT_OS).strip().lower()

    if resource_type == "ec2":
        if instance_type not in ALLOWED_INSTANCE_TYPES:
            raise ValidationError(
                f"Instance type '{instance_type}' is not approved. Allowed: "
                f"{', '.join(sorted(ALLOWED_INSTANCE_TYPES))}."
            )
        if os_name not in ALLOWED_OS:
            raise ValidationError(
                f"OS '{os_name}' is not supported. Allowed: {', '.join(sorted(ALLOWED_OS))}."
            )

    requester = (f["requester_name"] or "unknown").strip()
    if not OWNER_RE.match(requester):
        raise ValidationError("requester_name contains unsupported characters.")

    approver = (f["approver_name"] or "unknown").strip()
    if not OWNER_RE.match(approver):
        raise ValidationError("approver_name contains unsupported characters.")

    return {
        "project": project,
        "env": env,
        "resource_type": resource_type,
        "requester_name": requester,
        "approver_name": approver,
        "request_id": request_id,
        "instance_type": instance_type,
        "os_name": os_name,
    }


# ---------------------------------------------------------------- text helpers

def _extract_value(text, key):
    match = re.search(
        rf"\b{re.escape(key)}\s*[:=]\s*([a-zA-Z0-9._-]+)", text, re.IGNORECASE
    )
    return match.group(1) if match else None


def _infer_resource_type(text):
    """
    Explicit `resource: s3` wins. Otherwise fall back to keyword sniffing, but
    anchor on the verb so "s3 bucket for ec2 logs" doesn't resolve to ec2.
    """
    explicit = _extract_value(text, "resource") or _extract_value(text, "resource_type")
    if explicit and explicit.lower() in ALLOWED_RESOURCE_TYPES:
        return explicit.lower()

    lowered = text.lower()
    verb = re.search(r"\b(create|provision|launch|spin\s*up)\b\W+(\w+)", lowered)
    if verb and verb.group(2) in ALLOWED_RESOURCE_TYPES:
        return verb.group(2)

    found = [t for t in ALLOWED_RESOURCE_TYPES if re.search(rf"\b{t}\b", lowered)]
    return found[0] if len(found) == 1 else ""


def _extract_os(text):
    lowered = text.lower()
    if "ubuntu" in lowered:
        return "ubuntu"
    if "windows" in lowered:
        return "windows"
    if "amazonlinux23" in lowered or "al2023" in lowered or "amazon linux" in lowered:
        return "amazonlinux23"
    return DEFAULT_OS
