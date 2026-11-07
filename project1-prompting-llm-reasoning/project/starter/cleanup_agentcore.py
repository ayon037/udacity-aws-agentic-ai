#!/usr/bin/env python3
import json
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
CONFIG_PATH = Path("agentcore_config.json")


def load_config():
    if not CONFIG_PATH.exists():
        print(f"{CONFIG_PATH} not found - nothing to clean up.")
        sys.exit(0)
    return json.loads(CONFIG_PATH.read_text())


def wait_until_gone(get_fn, label, timeout=180):
    start = time.time()
    while True:
        try:
            status = get_fn()
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("ResourceNotFoundException", "ValidationException"):
                print(f"  {label} deleted.")
                return
            raise
        print(f"  {label} status: {status}")
        if time.time() - start > timeout:
            print(f"  Timed out waiting for {label} deletion, continuing.")
            return
        time.sleep(5)


def main():
    config = load_config()
    control = boto3.client("bedrock-agentcore-control", region_name=REGION)

    harness_id = config.get("harnessId")
    if harness_id:
        print(f"Deleting harness {harness_id}...")
        try:
            control.delete_harness(harnessId=harness_id)
            wait_until_gone(lambda: control.get_harness(harnessId=harness_id)["harness"]["status"], "harness")
        except ClientError as e:
            print(f"  Skipping harness delete: {e}")
    else:
        print("No harnessId in config, skipping.")

    gateway_id = config.get("gatewayId")
    target_id = config.get("gatewayTargetId")
    if gateway_id and target_id:
        print(f"Deleting gateway target {target_id}...")
        try:
            control.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=target_id)
            wait_until_gone(
                lambda: control.get_gateway_target(gatewayIdentifier=gateway_id, targetId=target_id)["status"],
                "gateway target",
            )
        except ClientError as e:
            print(f"  Skipping gateway target delete: {e}")
    else:
        print("No gatewayId/gatewayTargetId in config, skipping.")

    if gateway_id:
        print(f"Deleting gateway {gateway_id}...")
        try:
            control.delete_gateway(gatewayIdentifier=gateway_id)
            wait_until_gone(lambda: control.get_gateway(gatewayIdentifier=gateway_id)["status"], "gateway")
        except ClientError as e:
            print(f"  Skipping gateway delete: {e}")
    else:
        print("No gatewayId in config, skipping.")

    print("\nDone. The DynamoDB table, Lambda, and IAM roles from cloudformation-tool.yaml")
    print("are deleted separately via 'aws cloudformation delete-stack'.")


if __name__ == "__main__":
    main()
