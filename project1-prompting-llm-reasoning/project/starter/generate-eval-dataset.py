#!/usr/bin/env python3
import argparse
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

import boto3

REGION = "us-east-1"
MODEL_ID = "us.amazon.nova-pro-v1:0"
CONFIG_PATH = Path("agentcore_config.json")

_THINKING_RE = re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE)


def strip_thinking(text: str) -> str:
    return _THINKING_RE.sub("", text).strip()


def load_config():
    if not CONFIG_PATH.exists():
        print(f"{CONFIG_PATH} not found - run setup_gateway.py and create_harness.py first.", file=sys.stderr)
        sys.exit(1)
    config = json.loads(CONFIG_PATH.read_text())
    if "harnessArn" not in config:
        print("Missing harnessArn in agentcore_config.json - run create_harness.py first.", file=sys.stderr)
        sys.exit(1)
    return config


def invoke_once(client, harness_arn: str, gateway_arn: str, gateway_target_name: str, prompt: str) -> str:
    session_id = str(uuid.uuid4())

    response = client.invoke_harness(
        harnessArn=harness_arn,
        runtimeSessionId=session_id,
        actorId=session_id,
        model={"bedrockModelConfig": {"modelId": MODEL_ID}},
        tools=[
            {
                "type": "agentcore_gateway",
                "name": gateway_target_name,
                "config": {
                    "agentCoreGateway": {
                        "gatewayArn": gateway_arn,
                        "outboundAuth": {"awsIam": {}},
                    }
                },
            }
        ],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
    )

    text_parts = []
    tool_calls = []
    for event in response["stream"]:
        if "contentBlockStart" in event:
            start = event["contentBlockStart"].get("start", {})
            if "toolUse" in start:
                tool_calls.append(start["toolUse"].get("name", "?"))
        elif "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            if "text" in delta:
                text_parts.append(delta["text"])
        elif "runtimeClientError" in event:
            raise RuntimeError(event["runtimeClientError"].get("message"))

    final_text = strip_thinking("".join(text_parts))
    if tool_calls:
        final_text = f"[tool call(s): {', '.join(tool_calls)}]\n{final_text}"
    return final_text


def main():
    p = argparse.ArgumentParser(description="Run harness tests and emit Bedrock Evaluations JSONL (LLM-as-judge BYOI).")
    p.add_argument("--tests-json", required=True, help="Path to the test suite JSON.")
    p.add_argument("--model-identifier", default="my-support-chatbot", help="Value to put in modelResponses[0].modelIdentifier.")
    p.add_argument("--out-jsonl", default="output_eval_dataset.jsonl", help="Where to write the eval dataset JSONL.")
    args = p.parse_args()

    config = load_config()
    harness_arn = config["harnessArn"]
    gateway_arn = config["gatewayArn"]
    gateway_target_name = config["gatewayTargetName"]

    suite = json.loads(Path(args.tests_json).read_text(encoding="utf-8"))
    tests = suite["tests"]

    client = boto3.client("bedrock-agentcore", region_name=REGION)

    out_path = Path(args.out_jsonl)
    n_ok = 0

    with out_path.open("w", encoding="utf-8") as f:
        for t in tests:
            test_id = t["id"]
            prompt = t.get("prompt", "")
            reference = t.get("expected", "")

            try:
                response_text = invoke_once(client, harness_arn, gateway_arn, gateway_target_name, prompt)
                n_ok += 1
            except Exception as e:
                print(e, file=sys.stderr)
                response_text = f"[HARNESS_ERROR] {type(e).__name__}: {e}"

            record: Dict[str, Any] = {
                "prompt": prompt,
                "referenceResponse": reference,
                "modelResponses": [
                    {
                        "response": response_text,
                        "modelIdentifier": args.model_identifier,
                    }
                ],
            }

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"{test_id}: wrote eval line", file=sys.stderr)

    print(f"\nWrote {len(tests)} JSONL lines to {out_path} ({n_ok} harness calls succeeded).", file=sys.stderr)


if __name__ == "__main__":
    main()
