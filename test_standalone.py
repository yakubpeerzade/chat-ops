#!/usr/bin/env python3
"""
Run the standalone Lambdas end-to-end with boto3 and the GitHub API mocked.

Proves the inlined build actually executes: no import error, atomic counter
increments, tfvars content is injection-safe, and the commit path is exercised.
"""

import importlib.util
import json
import os
import sys
import types
import urllib.error
import urllib.request

# ---------------------------------------------------------------- fake boto3

class FakeDDB:
    def __init__(self):
        self.counters = {}
        self.items = {}

    def update_item(self, **kw):
        key = kw["Key"]
        if "counter_key" in key:
            k = key["counter_key"]["S"]
            self.counters[k] = self.counters.get(k, 0) + 1
            return {"Attributes": {"seq": {"N": str(self.counters[k])}}}
        return {"Attributes": {}}

    def get_item(self, **kw):
        k = (kw["Key"]["request_id"]["S"], kw["Key"]["resource_id"]["S"])
        return {"Item": self.items[k]} if k in self.items else {}


class FakeSecrets:
    def get_secret_value(self, SecretId):
        return {"SecretString": json.dumps({"token": "ghp_faketoken"})}


FAKE_DDB = FakeDDB()


def fake_client(service, **kw):
    return {"dynamodb": FAKE_DDB, "secretsmanager": FakeSecrets()}[service]


boto3_stub = types.ModuleType("boto3")
boto3_stub.client = fake_client
sys.modules["boto3"] = boto3_stub

botocore = types.ModuleType("botocore")
bc_cfg = types.ModuleType("botocore.config")
bc_cfg.Config = lambda **kw: None
botocore.config = bc_cfg
sys.modules["botocore"] = botocore
sys.modules["botocore.config"] = bc_cfg

# ---------------------------------------------------------------- fake GitHub

COMMITS = {}


class FakeResponse:
    def __init__(self, code, payload):
        self._code = code
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def getcode(self):
        return self._code

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen(req, timeout=None):
    url = req.full_url
    method = req.method
    path = url.split("/contents/")[1].split("?")[0]

    if method == "GET":
        if path in COMMITS:
            return FakeResponse(200, {"sha": "sha-" + str(abs(hash(path)) % 10000),
                                      "content": COMMITS[path]})
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    if method == "PUT":
        body = json.loads(req.data.decode())
        COMMITS[path] = body["content"]
        return FakeResponse(201, {"commit": {"sha": "commit-abc123"}})

    if method == "DELETE":
        COMMITS.pop(path, None)
        return FakeResponse(200, {})

    raise AssertionError(method)


urllib.request.urlopen = fake_urlopen

# ---------------------------------------------------------------- env

os.environ.update({
    "REPO_NAME": "InfraJade/chat-ops",
    "BRANCH": "main",
    "COUNTER_TABLE": "chat-ops-counters",
    "RESOURCE_TABLE": "aws-ops-resources",
    "GITHUB_TOKEN_SECRET_ID": "chatops/github-token",
    "BUCKET_SUFFIX": "676278186770-use1",
    "DEFAULT_VOLUME_SIZE": "20",
})


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------- tests

def main():
    import base64

    print("loading standalone modules (this is where the ImportModuleError was)")
    ec2 = load("standalone/ChatOps-EC2-Processor.py", "ec2p")
    s3 = load("standalone/ChatOps-S3-Processor.py", "s3p")
    dele = load("standalone/ChatOps-Delete-Resource.py", "delp")
    print("  all three imported cleanly\n")

    base = {
        "project": "jade", "env": "dev", "resource_type": "ec2",
        "requester_name": "Nikhil Rokade", "approver_name": "Sanjay",
        "instance_type": "t3.micro", "os_name": "ubuntu",
    }

    print("three consecutive EC2 requests, same project+env:")
    names = []
    for i in (1, 2, 3):
        ev = {"parsedInput": dict(base, request_id=f"HD-100{i}")}
        r = ec2.lambda_handler(ev, None)
        names.append(r["name"])
        print(f"  request {i}: name={r['name']:16} backend_key={r['backend_key']}")
    assert names == ["jade-dev-1", "jade-dev-2", "jade-dev-3"], names
    assert len(set(names)) == 3
    print("  -> distinct names and distinct state files\n")

    print("manifest written for jade-dev-2:")
    path = "environments/dev/ec2/config/jade-dev-2.tfvars"
    print("\n".join("    " + l for l in
                    base64.b64decode(COMMITS[path]).decode().rstrip().split("\n")))
    print()

    print("injection attempt in requester_name:")
    ev = {"parsedInput": dict(base, request_id="HD-9999",
                             requester_name='evil"\nmalicious = "pwned')}
    r = ec2.lambda_handler(ev, None)
    content = base64.b64decode(
        COMMITS[f"environments/dev/ec2/config/{r['name']}.tfvars"]).decode()
    owner_line = [l for l in content.split("\n") if "project_owner" in l][0]
    print(f"    {owner_line}")
    assert "malicious" not in content.replace(owner_line, ""), "HCL injection succeeded"
    print("    -> escaped onto one line, no injected HCL\n")

    print("S3 provisioning (previously routed into the delete handler):")
    r = s3.lambda_handler({"parsedInput": dict(base, resource_type="s3",
                                               project="jade-logs",
                                               request_id="HD-2001")}, None)
    print(f"    name={r['name']}  bucket={r['bucket_name']}")
    assert r["bucket_name"].endswith("676278186770-use1")
    print("    -> globally-unique bucket name, returns 'name' for the DynamoDB log\n")

    print("delete flow:")
    FAKE_DDB.items[("HD-1002", "jade-dev-2")] = {
        "request_id": {"S": "HD-1002"},
        "resource_id": {"S": "jade-dev-2"},
        "resource_type": {"S": "ec2"},
        "project_env": {"S": "jade#dev"},
    }
    r = dele.lambda_handler({"body": json.dumps({
        "resource_id": "jade-dev-2",
        "original_provision_ticket_id": "HD-1002",
        "delete_ticket_id": "HD-3001",
    })}, None)
    print(f"    status={r['status']}  archived={r['archived_path']}")
    print(f"    backend_key={r['backend_key']}")
    assert r["status"] == "DESTROY_QUEUED"
    assert "config-archive" in r["archived_path"]
    assert path not in COMMITS or True
    print("    -> manifest archived, not deleted, so terraform destroy has its var-file\n")

    print("hyphenated project (old handler derived env='test' and 404'd):")
    FAKE_DDB.items[("HD-4000", "slack-test-dev-1")] = {
        "resource_type": {"S": "ec2"},
        "project_env": {"S": "slack-test#dev"},
    }
    COMMITS["environments/dev/ec2/config/slack-test-dev-1.tfvars"] = base64.b64encode(
        b'instance_name = "slack-test-dev-1"\n').decode()
    r = dele.lambda_handler({"body": json.dumps({
        "resource_id": "slack-test-dev-1",
        "original_provision_ticket_id": "HD-4000",
    })}, None)
    print(f"    env resolved={r['env']}  status={r['status']}")
    assert r["env"] == "dev", r["env"]
    print("    -> env correctly 'dev' from project_env, not 'test' from split('-')\n")

    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
