# Project 1: Support Chatbot with Prompt-Based Routing

A customer-support assistant for an online shop, built on the **Amazon Bedrock AgentCore managed harness**. One system prompt classifies every message and handles three paths. There is no separate classifier service or flow graph.

## How it works
1. **Classify** each message as `BUG_REPORT`, `PLATFORM_QUESTION` or `OTHER_REQUEST` (tie-break order defined in the prompt).
2. **Bug report:** ask for description, steps to reproduce and environment, one missing field at a time. Only then call `create_bug_report` through an AgentCore **Gateway** (Lambda), which stores the ticket in **DynamoDB**.
3. **Platform question:** answer from the FAQ embedded in the prompt (`online_shop_faq.md`), or hand off to human support when the FAQ does not cover it.
4. **Other request:** redirect to phone support.

## Evaluation
10 test cases (bug reports, covered and uncovered FAQ, hand-offs, ambiguous input, one-word input, prompt injection) run through a Bedrock Evaluations job with the built-in **Correctness** metric: **10/10, average 1.0**. Details in `project/starter/evaluation-observations.md`.

## Lessons learned
- Eval runs exposed bugs that manual chats missed: leaked `<thinking>` text, memory bleeding between sessions (fixed with a per-conversation `actorId`), and the model filing tickets with invented fields.
- Fixing premature tool calls took a hard rule at the top of the prompt plus a failure-consequence framing. A polite instruction alone was not enough.

## Layout (`project/starter/`)
| File | Purpose |
|---|---|
| `system_prompt.txt` | Classification and routing logic |
| `create_harness.py`, `setup_gateway.py` | Create the harness and Gateway tool |
| `cloudformation-tool.yaml`, `cloudformation-testing.yaml` | Lambda, DynamoDB, roles |
| `chat.py` | CLI chat client |
| `harness-tests.json`, `generate-eval-dataset.py` | Test suite and eval dataset generation |
| `evaluation-observations.md`, `SUBMISSION_NOTES.md` | Results and notes |
| `*_transcript.txt`, `*.png` | Evidence: live chats, DynamoDB item, eval results |

The original Udacity brief is in `project/README.md`.
