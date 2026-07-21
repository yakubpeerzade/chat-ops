import json
import base64
import os
import urllib.request
import urllib.error

def lambda_handler(event, context):
    try:
        inputs = event.get("parsedInput", event)
        project = inputs["project"]
        env = inputs["env"]
        owner = inputs["requester_name"]
        instance_type = inputs["instance_type"]
        os_name = inputs["os_name"]
        ticket_id = inputs["request_id"]

        counter = int(os.environ.get("COUNTER", "1"))
        name = f"{project}-{env}-{counter}"
        file_name = f"{name}.tfvars"

        ami_map = {
            "ubuntu": "ami-091138d0f0d41ff90",
            "windows": "ami-0b2f6494ff0b07a0e",
            "amazonlinux23": "ami-0eb38b817b93460ac"
        }
        ami = ami_map.get(os_name, "ami-091138d0f0d41ff90")

        # Refactored tfvars payload configuration: conditional parameters removed
        tfvars_content = f"""instance_name  = "{name}"
ami_id         = "{ami}"
instance_type  = "{instance_type}"
project_code   = "{project}"
project_owner  = "{owner}"
request_id     = "{ticket_id}"
"""

        # Commit directly to the isolated ec2 subfolder layout
        commit_to_github(env, "ec2", file_name, tfvars_content, name)
        return {"name": name}

    except Exception as e:
        raise Exception(f"EC2 Processing Module Error: {str(e)}")

def commit_to_github(env, res_dir, file_name, content, resource_name):
    repo = os.environ['REPO_NAME']
    token = os.environ['GITHUB_TOKEN']
    branch = os.environ.get('BRANCH', 'main')
    
    file_path = f"environments/{env}/{res_dir}/config/{file_name}"
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json"
    }

    sha = None
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req) as res:
            sha = json.loads(res.read().decode()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404: raise

    payload = {
        "message": f"ChatOps [EC2]: Provisions {resource_name}",
        "content": base64.b64encode(content.encode()).decode(),
        "branch": branch
    }
    if sha: payload["sha"] = sha

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="PUT")
    with urllib.request.urlopen(req) as res:
        if res.getcode() not in [200, 201]: raise RuntimeError("GitHub Push Refused")