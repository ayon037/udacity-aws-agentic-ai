# Project 3 Documentation: NovaMart Multi-Agent Customer Support

A plain-language guide to what this project is, what it is built from, what data it uses, and how every file fits together.

---

## 1. What is this project?

NovaMart is a pretend online shop. Its support team gets thousands of messages a day:

- "I want to return my order ORD-27176." (needs order data and a decision)
- "What is the return policy for premium customers?" (needs the shop's policy documents)
- "How much are 5 items at $29.99 with 10% off?" (needs only arithmetic)

This project builds the AI layer that handles those messages without a person. It uses **five cooperating AI agents**, not one. A manager agent (the **Orchestrator**) reads the message and decides who should work on it. Specialists do the actual work, and a final agent writes the reply.

| Agent | Plain-English job |
|---|---|
| **Orchestrator** | The manager. Never answers the customer itself. Decides which specialists to call, in which order. |
| **Inventory Agent** | The record keeper. Looks up the order and the customer's tier. Reports facts, never decides. |
| **Refund Agent** | The decision maker. Checks whether an order can be returned and starts the return. |
| **Policy Agent** | The librarian. Answers policy questions by searching three document collections at once. |
| **Communication Agent** | The writer. Turns everything the others found into a warm, clear reply. |

---

## 2. The technologies, and what each does

| Technology | Role | Where it is used |
|---|---|---|
| **Strands Agents SDK** | Python library for building agents: a model, instructions, and tools (plain Python functions) | `src/agent_orchestrator.py` |
| **Amazon Bedrock** with **Claude Haiku 4.5** | The fast, cheap model used by the manager | Orchestrator |
| **Claude Sonnet 4.5** | The stronger model used by every worker | The four workers and three retrievers |
| **Amazon DynamoDB** | Database: orders, customers, and the shared "workflow state" | `infrastructure/starter_stack.yaml` |
| **Bedrock Knowledge Bases** | Managed search over documents (RAG): splits, embeds and indexes them | Three KBs: returns, shipping, warranty |
| **Amazon S3 + S3 Vectors** | S3 stores the policy files. S3 Vectors stores the searchable embeddings. | Policy bucket, vector bucket with 3 indexes |
| **Titan Embed Text v2** | Turns text into numbers so similar meaning can be searched | Inside each Knowledge Base |
| **Bedrock Guardrails** | Safety filter on every model call | `create_guardrail()` |
| **AgentCore Runtime** | Hosts the finished agent as a web service in AWS | Deployed with the AgentCore CLI |
| **AgentCore Memory** | Stores session summaries for 7 days | `configure_memory()` |
| **CloudWatch Logs + X-Ray** | Logs and a map of which agent called which | `configure_observability()` |
| **CloudFormation** | Builds the base resources from one YAML file | `infrastructure/starter_stack.yaml` |
| **AgentCore CLI** (`@aws/agentcore`) | Packages the code and deploys the runtime | `src/agentcore_cli.py` |

---

## 3. The data, and why it is there

All data is fictional.

| Data | Where | What it is | Why it exists |
|---|---|---|---|
| **Customers** | DynamoDB `customers` table | 4 people (CUST-001 to CUST-004) with name, email, **tier** (Standard or Premium) | The tier decides the return window |
| **Orders** | DynamoDB `orders` table | 11 orders with product, price, status and date, keyed by customer id + order id | What the Inventory and Refund agents look up |
| **Policy documents** | S3, three folders | Return, shipping and warranty policies, plus a customer-tiers file copied into each folder | What the Knowledge Bases index and the Policy Agent searches |
| **Workflow state** | DynamoDB `workflow-state` table | One row per conversation, filled in as each agent finishes | The shared notebook the agents pass findings through |

The order dates are generated relative to the day the seed script runs, so the scenarios always behave the same way. For example, ORD-27176 is 12 days old, so it can be returned by a Premium customer, and ORD-28001 is 45 days old, so a Standard customer is too late.

The key policy facts the documents contain: Standard customers get a **30-day** return window and Premium customers **60 days**. Premium also gets a 3-year electronics warranty (Standard gets 1 year), and refunds are issued 5 to 7 business days after the item arrives.

---

## 4. How a request flows

### A return request

1. Customer: "I want to return my order ORD-27176."
2. Orchestrator calls `initialize_session`, which creates a blank row in the workflow-state table (version 0).
3. Orchestrator calls `route_to_inventory_agent`. The Inventory Agent looks up the order and the customer's tier, then the result is saved into the row (version 1).
4. Orchestrator calls `route_to_refund_agent`. The Refund Agent reads the Inventory findings from the row, works out that a Premium customer has 60 days and the order is 12 days old, calls `initiate_refund` and saves its decision (version 2).
5. Orchestrator calls `route_to_communication_agent`. The Communication Agent reads the whole row and writes the reply. That text goes back to the customer.

### A policy question

`initialize_session` -> `route_to_policy_agent` -> `route_to_communication_agent`. Inside the Policy Agent, one tool (`search_all_policies`) starts **three retriever agents at the same time**, one per Knowledge Base, and joins their answers.

### A math question

`initialize_session` -> `route_to_communication_agent`. No database or documents are needed, so the specialists are skipped.

### The routing rules the Orchestrator follows

| Rule | When | What it does |
|---|---|---|
| 1 | Every request | Call `initialize_session` first |
| 2 | Order status, return or refund | Inventory agent, then (for returns) Refund agent |
| 3 | Policy questions | Policy agent |
| 4 | Account questions ("am I Premium?") | Inventory agent, never the Policy agent (it knows policy text, not customers) |
| 5 | Math | Skip Inventory, Policy and Refund |
| 6 | Every request | Communication agent is always the last call |

### Why the shared "workflow state" has a version number

Each agent writes its result with the version it last saw. If someone else wrote in between, the write is refused and retried with the fresh version. This is **optimistic locking**, and it stops two agents from silently overwriting each other.

---

## 5. How the files fit together

All paths are under `starter/`.

| File | What it does |
|---|---|
| `src/agent_orchestrator.py` | **My implementation.** Builds all five agents, the guardrail, the deployment, the memory and the observability setup. Doubles as the web server when deployed. |
| `config.py` | Reads resource names from CloudFormation outputs and IDs from `.env`. Provided. |
| `src/bedrock_kb_retrieval.py` | Helper that searches one Knowledge Base. Provided. |
| `src/agent_observability.py` | Wraps every tool so each call becomes a node in X-Ray. Provided. |
| `src/agent_utils.py` | Colour-coded terminal trace. Provided. |
| `src/agentcore_cli.py` | Stages the code and runs the AgentCore CLI. Provided. |
| `src/demo.py` | Runs one example request. Provided. |
| `infrastructure/starter_stack.yaml` | CloudFormation: 3 DynamoDB tables, policy bucket, vector bucket with 3 indexes, runtime role, log group. |
| `infrastructure/seed_data.py` | Loads the customers, orders and policy documents. |
| `infrastructure/cleanup.py` | Deletes everything the project created. |
| `agentcore/agentcore.json` | The runtime definition the CLI deploys (entry point, network mode, environment variables). |
| `tests/test_agent.py` | The 120-point test suite. |
| `.env.example` | Template for the IDs you fill in (the real `.env` is not committed). |

Outside `starter/`: `screenshots/` (proof), `test_logs/` (raw output) and `README_SUBMISSION.md` (rubric map).

### Build order

```
1. CloudFormation stack         -> tables, buckets, vector indexes, role
2. seed_data.py                 -> customers, orders, policy files in S3
3. Create 3 Knowledge Bases     -> index the policy files into the vector indexes, then sync
4. Fill .env                    -> the three KB IDs
5. python src/agent_orchestrator.py deploy
        -> build agents, create guardrail, deploy runtime,
           create memory, switch on logging and tracing
6. Copy runtime ARN + guardrail id/version into .env
7. python tests/test_agent.py all      -> 120/120
8. python src/agent_orchestrator.py test -> traces appear in X-Ray
```

---

## 6. The safety guardrail

One Bedrock Guardrail (published as version 1) is attached to the model of each of the five main agents:

| Policy | Setting |
|---|---|
| Content filters | Sexual, violence, hate at **HIGH**; insults, misconduct at **MEDIUM** |
| Personal data | Credit card and SSN **blocked**; email and phone **anonymized** |
| Denied topics | Competitor products, price haggling, legal threats |
| Words | Managed profanity list |

The "price haggling" topic is written narrowly: asking to change an advertised price is blocked, but arithmetic with a price and discount the customer states is allowed. A looser definition blocked the required math question during testing. I checked it directly: the math question and its answer pass, and negotiation, competitor, legal-threat, credit-card and violence prompts are all blocked (`test_logs/guardrail_validation.txt`).

---

## 7. What went wrong along the way (and the fixes)

1. **A tool ran before its setup step.** The manager model sometimes called `initialize_session` and `route_to_*` in the same step, so the route found no session. It recovered by retrying, but the prompt now says to call one tool at a time.
2. **The writer leaked its notes.** The Communication Agent sometimes started with a remark like "the workflow context has no findings". It now puts the customer message inside `<result>` tags and the code keeps only that part.
3. **Wrong rounding.** Rounding the discount ($14.995 to $15.00) before subtracting gave $134.95. The correct approach is to round only at the end: $134.955 becomes **$134.96**.
4. **Agents remembered other customers.** A long-running runtime would carry one session's data into the next. Each worker's history is cleared before it runs.
5. **A second message in the same chat broke.** The session row already existed, so creating it failed. `initialize_session` now starts the row fresh.
6. **Old Node.js.** The AgentCore CLI needs Node 20 and the machine had 16, so I installed Node 20 for the deployment.

---

## 8. Results and where to see them

| Evidence | File |
|---|---|
| All tests, 120/120 | `screenshots/01_all_tests_120_of_120.png`, `test_logs/test_all_120_of_120.txt` |
| Guardrail allow/block checks | `screenshots/02_guardrail_validation.png`, `test_logs/guardrail_validation.txt` |
| X-Ray service map: orchestrator connected to all four workers and the three Knowledge Base nodes | `screenshots/03_xray_service_map.png` |
| The three scenarios run locally | `test_logs/live_scenarios_local_run.txt` |
| The same scenarios against the deployed runtime | `test_logs/live_scenarios_deployed_runtime.txt` |

---

## 9. Where to look first

- To understand the behaviour: the `build_orchestrator_agent()` system prompt in `src/agent_orchestrator.py`.
- To see the parallel search: `build_policy_agent()` and the `[PARALLEL RETRIEVAL]` section of `test_logs/live_scenarios_local_run.txt`.
- To see it working: the X-Ray screenshot and the test log.
