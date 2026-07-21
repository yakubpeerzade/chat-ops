import json
import re

def lambda_handler(event, context):
    try:
        # Step Functions passing from API Gateway passes the event payload directly
        raw_body = event.get("body", event)
        if isinstance(raw_body, str):
            body = json.loads(raw_body)
        else:
            body = raw_body

        # Check if incoming data uses the old text format or structured fields
        user_message = body.get('text', '')
        
        if user_message:
            # Fallback Pattern: Parse text using original regex engine
            project = extract_value(user_message, "project")
            env = extract_value(user_message, "env") or "dev"
            resource_type = "ec2" if "ec2" in user_message.lower() else ("s3" if "s3" in user_message.lower() else "")
            requester_name = extract_value(user_message, "owner") or "unknown"
            approver_name = "Auto-Approved"
            request_id = f"CHAT-{project}-{env}"
            instance_type = extract_value(user_message, "type") or "t2.micro"
            os_name = extract_os(user_message)
        else:
            # Primary Pattern: Read structured Help Desk fields directly
            project = body.get("project") or body.get("project_code")
            env = body.get("env") or body.get("environment") or "dev"
            resource_type = body.get("resource_type", "").lower()
            requester_name = body.get("requester_name") or body.get("owner") or "unknown"
            approver_name = body.get("approver_name") or "Authorized Platform Admin"
            request_id = body.get("request_id") or body.get("ticket_id")
            instance_type = body.get("instance_type") or body.get("type") or "t2.micro"
            os_name = body.get("os_name") or "ubuntu"

        if not project or not env or not resource_type:
            raise ValueError("Missing mandatory core arguments: project, env, or resource_type.")

        if not request_id:
            raise ValueError("Help Desk integration requires a valid unique 'request_id'.")

        # Return payload directly mapped to step function pipeline expectations
        return {
            "project": project,
            "env": env,
            "resource_type": resource_type,
            "requester_name": requester_name,
            "approver_name": approver_name,
            "request_id": request_id,
            "instance_type": instance_type,
            "os_name": os_name
        }

    except Exception as e:
        raise Exception(f"Input Parsing Phase Failed: {str(e)}")

# -------- Helper Utilities --------
def extract_value(text, key):
    match = re.search(rf"{key}\s*[:=]\s*([a-zA-Z0-9._-]+)", text, re.IGNORECASE)
    return match.group(1) if match else None

def extract_os(text):
    text = text.lower()
    if "ubuntu" in text: return "ubuntu"
    if "windows" in text: return "windows"
    if "amazonlinux23" in text or "al2023" in text: return "amazonlinux23"
    return "ubuntu"