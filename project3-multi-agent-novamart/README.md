# Project 3: NovaMart Multi-Agent Customer Support

A multi-agent customer support system built with the **Strands Agents SDK** and **Amazon Bedrock AgentCore**. An orchestrator reads each customer request, sends it to the right specialist agent, and hands the findings to a communication agent that writes the reply.

**Result:** the automated suite scores **120/120**, the guardrail passes 8 of 8 allow/block checks, and the X-Ray service map shows the full call chain with 0 errors.

## Architecture

```
Customer request
      |
OrchestratorAgent (Claude Haiku 4.5, temperature 0.0)   routes + manages WorkflowState
      |
      +--> InventoryAgent      (Sonnet 4.5, 0.1)  DynamoDB lookups: orders, customer tier
      +--> RefundAgent         (Sonnet 4.5, 0.1)  30-day Standard / 60-day Premium decision
      +--> PolicyAgent         (Sonnet 4.5, 0.2)  multi-agent RAG coordinator
      |        +--> ReturnsPolicyRetrieverAgent   -> Knowledge Base (returns)   \
      |        +--> ShippingPolicyRetrieverAgent  -> Knowledge Base (shipping)    > parallel, ThreadPoolExecutor
      |        +--> WarrantyPolicyRetrieverAgent  -> Knowledge Base (warranty)   /
      +--> CommunicationAgent  (Sonnet 4.5, 0.3)  writes the final customer reply

Shared state: DynamoDB WorkflowState table (optimistic locking on a version field)
Safety: Bedrock Guardrail (version 1) on the five main agents
Hosting: AgentCore Runtime (PUBLIC, HTTP) deployed with the AgentCore CLI
Observability: CloudWatch Logs (INFO) + X-Ray (100% sampling)
```

## Results

| Check | Result |
|---|---|
| `python tests/test_agent.py all` | **120/120** ([screenshot](screenshots/01_all_tests_120_of_120.png), [log](test_logs/test_all_120_of_120.txt)) |
| Return request (CUST-001, ORD-27176) | Orchestrator -> Inventory -> Refund -> Communication; a return reference is created in DynamoDB |
| Policy question | Orchestrator -> Policy (3 retrievers in parallel) -> Communication |
| "5 items at $29.99 with 10% off" | Orchestrator -> Communication only; answer **$134.96** |
| Guardrail | Math allowed (input and output). Price haggling, competitor talk, legal threats, credit card numbers and violence blocked ([log](test_logs/guardrail_validation.txt)) |
| X-Ray service map | `NovaMart-Orchestrator` connected to all 4 workers and 3 `KnowledgeBase:*` nodes, 0 errors, 0 faults ([screenshot](screenshots/03_xray_service_map.png)) |

## What I implemented (`starter/src/agent_orchestrator.py`)

- **Task 2:** the five agents, their tools and prompts, the six routing rules, and WorkflowState updates with the expected version.
- **Task 3:** `create_guardrail()` (content, PII, three denied topics, profanity, numbered version) and `deploy_to_agentcore_runtime()`.
- **Task 4:** `configure_memory()` with a session-summary strategy and 7-day retention.
- **Task 6:** `configure_observability()`.
- Three Knowledge Bases (returns, shipping, warranty) on S3 Vectors with Titan Embed Text v2, created and synced.

## Problems found and fixed

1. **Route ran before the session existed.** The orchestrator model called `initialize_session` and a route tool in the same step. Fixed by telling it to call one tool at a time.
2. **Internal notes reached the customer.** The Communication Agent sometimes opened with remarks such as "the workflow context has no findings". It now writes the reply inside `<result>` tags and the routing tool keeps only that part.
3. **Rounding.** Rounding the discount first gave $134.95. Rounding only at the end gives the correct $134.96.
4. **Stale history.** Worker agents kept earlier conversations, which could leak data between sessions in a long-running runtime. Their history is cleared before each task.
5. **Follow-up messages in one chat session** failed because the session row already existed. `initialize_session` now resets it.

## Run it

```bash
cd starter
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env              # fill in Knowledge Base IDs, runtime ARN, guardrail
python infrastructure/seed_data.py
python tests/test_agent.py all
python src/agent_orchestrator.py test      # three scenarios, traced to X-Ray
python src/agent_orchestrator.py deploy    # needs Node 20+, the AgentCore CLI and uv
```

## Layout

```
project3-multi-agent-novamart/
  starter/            code, infrastructure, tests (src/agent_orchestrator.py is my work)
  screenshots/        tests 120/120, guardrail checks, X-Ray service map
  test_logs/          full test output and live scenario runs
  README_SUBMISSION.md  deliverables mapped to the rubric
  DOCUMENTATION.md    plain-language guide (PDF alongside)
```

AWS account IDs are redacted (`XXXXXXXXXXXX`), and `.env` is not committed. See [DOCUMENTATION.md](DOCUMENTATION.md) for the full walkthrough.
