#!/usr/bin/env python3
import json
import sys
import time
from pathlib import Path

import boto3

REGION = "us-east-1"
HARNESS_NAME = "support_chatbot_harness"
MODEL_ID = "us.amazon.nova-pro-v1:0"
CONFIG_PATH = Path("agentcore_config.json")
SYSTEM_PROMPT_PATH = Path("system_prompt.txt")
FAQ_PATH = Path("online_shop_faq.md")


def load_config():
    if not CONFIG_PATH.exists():
        print(f"{CONFIG_PATH} not found - run setup_gateway.py first.", file=sys.stderr)
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text())


def save_config(config):
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")


def build_system_prompt():
    template = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    faq = FAQ_PATH.read_text(encoding="utf-8")
    if "{{FAQ}}" not in template:
        print("Warning: {{FAQ}} placeholder not found in system_prompt.txt - FAQ will not be embedded.", file=sys.stderr)
    return template.replace("{{FAQ}}", faq)


def find_harness(client, name):
    token = None
    while True:
        kwargs = {"nextToken": token} if token else {}
        resp = client.list_harnesses(**kwargs)
        for h in resp.get("items", resp.get("harnesses", [])):
            if h.get("harnessName") == name:
                return h
        token = resp.get("nextToken")
        if not token:
            return None


def wait_for_ready(client, harness_id, timeout=240):
    start = time.time()
    while True:
        resp = client.get_harness(harnessId=harness_id)
        status = resp["harness"]["status"]
        print(f"  harness status: {status}")
        if status == "READY":
            return resp["harness"]
        if status in ("CREATE_FAILED", "UPDATE_FAILED"):
            raise RuntimeError(f"Harness failed: {resp['harness'].get('failureReason')}")
        if time.time() - start > timeout:
            raise TimeoutError(f"Timed out waiting for harness (last status: {status})")
        time.sleep(5)


def main():
    config = load_config()
    for key in ("harnessRoleArn", "gatewayArn", "gatewayTargetName"):
        if key not in config:
            print(f"Missing '{key}' in agentcore_config.json - run setup_gateway.py first.", file=sys.stderr)
            sys.exit(1)

    system_prompt_text = build_system_prompt()

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)

    tools = [
        {
            "type": "agentcore_gateway",
            "name": config["gatewayTargetName"],
            "config": {
                "agentCoreGateway": {
                    "gatewayArn": config["gatewayArn"],
                    "outboundAuth": {"awsIam": {}},
                }
            },
        }
    ]

    harness_kwargs = dict(
        executionRoleArn=config["harnessRoleArn"],
        model={"bedrockModelConfig": {"modelId": MODEL_ID}},
        systemPrompt=[{"text": system_prompt_text}],
        tools=tools,
    )

    existing = find_harness(control, HARNESS_NAME)
    if existing:
        print(f"Harness '{HARNESS_NAME}' exists ({existing['harnessId']}), updating...")
        resp = control.update_harness(harnessId=existing["harnessId"], **harness_kwargs)
        harness_id = resp["harness"]["harnessId"]
    else:
        print(f"Creating harness '{HARNESS_NAME}' (first run takes ~2-3 minutes)...")
        resp = control.create_harness(harnessName=HARNESS_NAME, **harness_kwargs)
        harness_id = resp["harness"]["harnessId"]

    harness = wait_for_ready(control, harness_id)

    config["harnessId"] = harness_id
    config["harnessArn"] = harness["arn"]
    config["harnessModelId"] = MODEL_ID
    save_config(config)

    print("\nHarness ready.")
    print(f"  harnessArn: {harness['arn']}")
    print("Run chat.py to try it out.")


if __name__ == "__main__":
    main()
