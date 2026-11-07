#!/usr/bin/env python3
import json
import re
import sys
import uuid
from pathlib import Path

import boto3

REGION = "us-east-1"
CONFIG_PATH = Path("agentcore_config.json")

_THINKING_RE = re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE)


def strip_thinking(text: str) -> str:
    return _THINKING_RE.sub("", text).strip()


def load_config():
    if not CONFIG_PATH.exists():
        print(f"{CONFIG_PATH} not found - run setup_gateway.py and create_harness.py first.", file=sys.stderr)
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text())


def stream_turn(client, harness_arn, session_id, user_text):
    response = client.invoke_harness(
        harnessArn=harness_arn,
        runtimeSessionId=session_id,
        actorId=session_id,
        messages=[{"role": "user", "content": [{"text": user_text}]}],
    )

    text_parts = []
    for event in response["stream"]:
        if "contentBlockStart" in event:
            start = event["contentBlockStart"].get("start", {})
            if "toolUse" in start:
                tool_name = start["toolUse"].get("name", "?")
                print(f"[tool call] {tool_name}")
        elif "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            if "text" in delta:
                text_parts.append(delta["text"])
        elif "runtimeClientError" in event:
            print(f"[error] {event['runtimeClientError'].get('message')}")

    reply = strip_thinking("".join(text_parts))
    if reply:
        print(f"Bot: {reply}")


def main():
    config = load_config()
    harness_arn = config.get("harnessArn")
    if not harness_arn:
        print("No harnessArn in agentcore_config.json - run create_harness.py first.", file=sys.stderr)
        sys.exit(1)

    client = boto3.client("bedrock-agentcore", region_name=REGION)
    session_id = str(uuid.uuid4())
    print(f"New session: {session_id}")
    print("Type your message (or 'exit' to quit).\n")

    while True:
        try:
            user_text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_text:
            continue
        if user_text.lower() in ("exit", "quit"):
            break

        try:
            stream_turn(client, harness_arn, session_id, user_text)
        except Exception as e:
            print(f"[HARNESS_ERROR] {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
