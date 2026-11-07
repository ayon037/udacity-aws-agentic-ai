# Submission Notes — Read This First

## Why this submission doesn't match the rubric's Bedrock Flow language

The rubric text (and the reviewer's example screenshots) describe a **Bedrock Flow**
with a classifier prompt node and Condition nodes routing to separate paths. That
approach is built on **Amazon Bedrock Agents Classic**, which the project's own
instructions state is being deprecated (Agents Classic closes July 30, 2026) and
was not available to provision in the Udacity lab account at the time of this
submission.

Per the project instructions, this submission instead uses the **Amazon Bedrock
AgentCore managed harness** with **prompt-based routing**: a single system prompt
(`system_prompt.txt`) classifies each customer message (BUG_REPORT /
PLATFORM_QUESTION / OTHER_REQUEST) and handles all three paths itself — there is no
separate classifier resource, Condition node, or Output node, because the harness
has no flow-graph concept. All routing logic lives in the prompt, as the project
instructions require ("all routing logic in a single system prompt, no external
classifiers/condition nodes").

Mapping rubric items to what's actually in this submission:

| Rubric item | Where to find it here |
|---|---|
| Classifier that produces consistent, unambiguous output | `system_prompt.txt`, "Step 1 classification" section (BUG_REPORT / PLATFORM_QUESTION / OTHER_REQUEST with tie-break order) |
| Messages routed to distinct paths, each with separate handling | `system_prompt.txt` Step 2 (three separate sections, one per category) |
| Bug report path: collects info before calling tool, tool persists to DynamoDB via Gateway | `system_prompt.txt` BUG_REPORT section (collection checklist) + `create_harness.py` (harness tool config wiring the Gateway) + `chat_bug_report_transcript.txt` (live transcript) + `dynamodb_bug_report_item.png` (screenshot) |
| Platform question path: answers from FAQ, redirects when uncovered | `system_prompt.txt` lines 38-45 (PLATFORM_QUESTION section, `{{FAQ}}` placeholder) + `online_shop_faq.md` (the actual FAQ content substituted in at harness-creation time by `create_harness.py`, in place of a Flow "Prompt node template") + `chat_faq_covered_transcript.txt` (covered question, live) + `chat_faq_uncovered_transcript.txt` (uncovered question, live) |
| Other request path: redirects to phone support | `system_prompt.txt` lines 47-49 (OTHER_REQUEST section) + `chat_other_request_transcript.txt` (live) |
| Testing/evaluation: test suite, JSONL generation, Bedrock Evaluations job, correctness ~1.0 | `harness-tests.json` (test suite — equivalent to `flow-tests.json`, renamed because this project has no Flow) → `generate-eval-dataset.py` → `output_eval_dataset.jsonl` → `bedrock_eval_job_results.png` (screenshot) → `evaluation-observations.md` (written observations, correctness = 1.0 avg across 10 tests) |

## Evidence file list

- `chat_bug_report_transcript.txt` — live `chat.py` run showing the assistant asking
  follow-up questions before calling the tool, the
  `[tool call] bugreports___create_bug_report` line, and the ticket ID returned to
  the customer.
- `dynamodb_bug_report_item.png` — DynamoDB console screenshot of the
  `bug-report-tool-stack-bug-reports` table showing the item created by that same
  conversation (ticket ID matches the transcript).
- `bedrock_eval_job_results.png` — Bedrock Evaluations console screenshot of the
  completed `support-chatbot-eval-run-1` job (`Builtin.Correctness`, evaluator
  model `amazon.nova-pro-v1:0`).
- `evaluation-observations.md` — written observations on the eval results and the
  issues found/fixed during development.
- `chat_faq_covered_transcript.txt` — live `chat.py` run: a question the FAQ
  covers ("What is your return policy?"), answered directly from
  `online_shop_faq.md`.
- `chat_faq_uncovered_transcript.txt` — live `chat.py` run: a plausible but
  FAQ-uncovered question ("Do you offer gift wrapping?"), redirected to human
  support.
- `chat_other_request_transcript.txt` — live `chat.py` run: a non-FAQ, non-bug
  request (asking for a manager over a billing dispute), redirected to human
  support.

There is no separate "FAQ Prompt node" to screenshot, because there is no Flow —
the FAQ is embedded directly into the single system prompt. `system_prompt.txt`
lines 38-45 are the equivalent of that node's template (the `{{FAQ}}`
placeholder), and `online_shop_faq.md` is the content substituted into it by
`create_harness.py` when the harness is built.

If anything here should be reviewed differently, happy to clarify further in the
knowledge platform — flagging per the reviewer's note.
