#!/usr/bin/env python3
import json
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
STACK_NAME = "bug-report-tool-stack"
GATEWAY_NAME = "bug-report-gateway"
TARGET_NAME = "bugreports"
CONFIG_PATH = Path("agentcore_config.json")


def get_stack_outputs(cf):
    resp = cf.describe_stacks(StackName=STACK_NAME)
    outputs = resp["Stacks"][0]["Outputs"]
    return {o["OutputKey"]: o["OutputValue"] for o in outputs}


def load_config():
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}


def save_config(config):
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")
    print(f"Wrote {CONFIG_PATH}")


def find_gateway(client, name):
    paginator_kwargs = {}
    while True:
        resp = client.list_gateways(**paginator_kwargs)
        for gw in resp.get("items", []):
            if gw.get("name") == name:
                return gw
        token = resp.get("nextToken")
        if not token:
            return None
        paginator_kwargs["nextToken"] = token


def find_target(client, gateway_id, name):
    paginator_kwargs = {}
    while True:
        resp = client.list_gateway_targets(gatewayIdentifier=gateway_id, **paginator_kwargs)
        for t in resp.get("items", []):
            if t.get("name") == name:
                return t
        token = resp.get("nextToken")
        if not token:
            return None
        paginator_kwargs["nextToken"] = token


def wait_for_status(get_fn, ok_statuses, fail_statuses, label, timeout=180):
    start = time.time()
    while True:
        status = get_fn()
        print(f"  {label} status: {status}")
        if status in ok_statuses:
            return status
        if status in fail_statuses:
            raise RuntimeError(f"{label} reached failure status: {status}")
        if time.time() - start > timeout:
            raise TimeoutError(f"Timed out waiting for {label} (last status: {status})")
        time.sleep(5)


def create_gateway_with_retry(client, **kwargs):
    last_err = None
    for attempt in range(6):
        try:
            return client.create_gateway(**kwargs)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("AccessDeniedException", "ValidationException") and attempt < 5:
                last_err = e
                print(f"  Retrying after IAM propagation delay ({code})...")
                time.sleep(15)
                continue
            raise
    raise last_err


def main():
    cf = boto3.client("cloudformation", region_name=REGION)
    control = boto3.client("bedrock-agentcore-control", region_name=REGION)

    print(f"Reading outputs from stack '{STACK_NAME}'...")
    outputs = get_stack_outputs(cf)
    for key in ("LambdaFunctionArn", "GatewayRoleArn", "HarnessRoleArn", "BugReportsTableName"):
        if key not in outputs:
            print(f"Missing expected output '{key}' - is cloudformation-tool.yaml deployed?", file=sys.stderr)
            sys.exit(1)

    lambda_arn = outputs["LambdaFunctionArn"]
    gateway_role_arn = outputs["GatewayRoleArn"]
    harness_role_arn = outputs["HarnessRoleArn"]
    table_name = outputs["BugReportsTableName"]

    config = load_config()

    existing_gw = find_gateway(control, GATEWAY_NAME)
    if existing_gw:
        print(f"Gateway '{GATEWAY_NAME}' already exists ({existing_gw['gatewayId']}), reusing it.")
        gateway_id = existing_gw["gatewayId"]
        gateway_arn = existing_gw["gatewayArn"]
        gateway_url = existing_gw["gatewayUrl"]
    else:
        print(f"Creating gateway '{GATEWAY_NAME}'...")
        resp = create_gateway_with_retry(
            control,
            name=GATEWAY_NAME,
            roleArn=gateway_role_arn,
            protocolType="MCP",
            authorizerType="AWS_IAM",
            description="Gateway exposing the create_bug_report tool to the support chatbot harness.",
        )
        gateway_id = resp["gatewayId"]
        gateway_arn = resp["gatewayArn"]
        gateway_url = resp["gatewayUrl"]

        wait_for_status(
            lambda: control.get_gateway(gatewayIdentifier=gateway_id)["status"],
            ok_statuses={"READY"},
            fail_statuses={"FAILED"},
            label="gateway",
        )

    existing_target = find_target(control, gateway_id, TARGET_NAME)
    tool_schema = {
        "inlinePayload": [
            {
                "name": "create_bug_report",
                "description": "File a bug report ticket for the online shop. All three fields are required.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Description of the bug, in the customer's own words.",
                        },
                        "stepsToReproduce": {
                            "type": "string",
                            "description": "Steps to follow to reproduce the issue.",
                        },
                        "environment": {
                            "type": "string",
                            "description": "Customer's environment: browser, operating system, device.",
                        },
                    },
                    "required": ["description", "stepsToReproduce", "environment"],
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "ticketId": {"type": "string", "description": "The created ticket's ID."},
                        "status": {"type": "string", "description": "The ticket's status."},
                    },
                },
            }
        ]
    }

    if existing_target:
        print(f"Gateway target '{TARGET_NAME}' already exists ({existing_target['targetId']}), reusing it.")
        target_id = existing_target["targetId"]
    else:
        print(f"Creating gateway target '{TARGET_NAME}'...")
        resp = control.create_gateway_target(
            gatewayIdentifier=gateway_id,
            name=TARGET_NAME,
            targetConfiguration={
                "mcp": {
                    "lambda": {
                        "lambdaArn": lambda_arn,
                        "toolSchema": tool_schema,
                    }
                }
            },
            credentialProviderConfigurations=[
                {"credentialProviderType": "GATEWAY_IAM_ROLE"}
            ],
        )
        target_id = resp["targetId"]

        wait_for_status(
            lambda: control.get_gateway_target(gatewayIdentifier=gateway_id, targetId=target_id)["status"],
            ok_statuses={"READY"},
            fail_statuses={"FAILED"},
            label="gateway target",
        )

    config.update(
        {
            "region": REGION,
            "stackName": STACK_NAME,
            "lambdaArn": lambda_arn,
            "gatewayRoleArn": gateway_role_arn,
            "harnessRoleArn": harness_role_arn,
            "tableName": table_name,
            "gatewayId": gateway_id,
            "gatewayArn": gateway_arn,
            "gatewayUrl": gateway_url,
            "gatewayTargetId": target_id,
            "gatewayTargetName": TARGET_NAME,
        }
    )
    save_config(config)
    print("\nGateway ready.")
    print(f"  gatewayArn: {gateway_arn}")
    print(f"  gatewayUrl: {gateway_url}")
    print(f"  tool exposed to the model as: {TARGET_NAME}___create_bug_report")


if __name__ == "__main__":
    main()
