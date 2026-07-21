import json
import os
import urllib.request
import urllib.error

def lambda_handler(event, context):
    try:
        body = event.get("body", event)
        if isinstance(body, str):
            body = json.loads(body)

        resource_id = body.get("resource_id")
        delete_ticket = body.get("delete_ticket_id")
        
        # Pull resource type out of the metadata payload context
        resource_type = body.get("resource_type", "ec2").lower() 
        
        parts = resource_id.split("-")
        env = parts[1] if len(parts) > 1 else "dev"

        repo = os.environ['REPO_NAME']
        token = os.environ['GITHUB_TOKEN']
        branch = os.environ.get('BRANCH', 'main')

        # Dynamically targets the correct subfolder based on the resource type
        file_path = f"environments/{env}/{resource_type}/config/{resource_id}.tfvars"
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json"
        }

        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req) as res:
                sha = json.loads(res.read().decode()).get("sha")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"status": "SKIPPED", "message": f"Manifest {file_path} already absent."}
            else:
                raise

        payload = {
            "message": f"ChatOps [De-provisioning]: Purging {resource_id} via ticket {delete_ticket}",
            "sha": sha,
            "branch": branch
        }

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="DELETE")
        with urllib.request.urlopen(req) as res:
            if res.getcode() not in [200, 202]: raise RuntimeError("GitHub Deletion Rejected")

        return {"status": "SUCCESS", "purged_file": file_path}

    except Exception as e:
        raise Exception(f"De-provisioning Clean Action Failed: {str(e)}")