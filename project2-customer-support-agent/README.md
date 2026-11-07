# Project 2: E-commerce Customer Support Agent

A conversational support agent deployed to **Amazon Bedrock AgentCore Runtime** with the **Strands Agents SDK**. It tracks orders, processes refunds, answers product and policy questions, remembers customers across sessions, calculates loyalty discounts exactly, and can browse the web.

## Architecture
```
 customer ──► AgentCore Runtime (main.py, Strands Agent, Nova 2 Lite)
                 ├─ MCPClient ─► AgentCore Gateway (MCP)
                 │                 ├─ order-tracker  ─► API Gateway ─► Lambda   (get_order, get_customer, get_customer_orders)
                 │                 └─ refund-processor ─► Lambda               (initiate_refund, check_refund_status, get_return_label)
                 ├─ search_knowledge_base ─► Bedrock Managed Knowledge Base (S3 catalog, RAG)
                 ├─ MemoryHook ─► AgentCore Memory (semantic facts + user preferences)
                 ├─ calculate_loyalty_discount ─► AgentCore Code Interpreter (sandbox)
                 └─ AgentCoreBrowser ─► AgentCore Browser tool
```

## Key design points
- **Gateway tools via MCP.** One API-based target and one Lambda-based target. The MCP session stays open for the whole agent run.
- **RAG tool** with a configuration guard, `\n---\n`-joined chunks, and a docstring that tells the model when to call it.
- **MemoryHook** (a `HookProvider`): retrieves memories from every strategy namespace, tags them by strategy, and prepends them as `Customer Context:`. After each reply it saves the user/assistant pair. Memory errors are logged and never block an answer.
- **Loyalty maths in the sandbox, not the LLM.** 100 points = $1, redeem in blocks of 500, capped at 50% of the order, then the tier discount (Gold 10%, Platinum 15%). Falls back to a tier-only discount if the Code Interpreter is unavailable.

## Test results
Logs in [`test_logs/`](test_logs/):

| Test | Result |
|---|---|
| Order tracking (ORD-001) | SHIPPED, UPS, `TRK987654321`, estimated delivery |
| Refund (ORD-002) | APPROVED, refund ID returned, 3-5 business days |
| RAG (Platinum benefits) | Same-day shipping, 15% discount, priority support |
| Memory (two sessions, same customer) | Second session recalls the name and the preference for concise replies |
| Loyalty (Gold, 4250 pts, $150) | 4000 points redeemed ($40), 10% tier discount, final $99, 349 points left |
| Browser | Page title read from the live udacity.com page |

## Issues I hit
- `strands-agents-tools` 0.9.0 removed the `browser` module that the starter imports. Pinned `strands-agents-tools>=0.2.21,<0.9` in `pyproject.toml`.
- The Gateway rejected the REST API target until every method had a `200` response defined, because the Gateway builds its tool list from the API's OpenAPI export.
- Gateway target names cannot contain underscores, so targets are `order-tracker` and `refund-processor`.
- Managed Knowledge Base retrieval returns nothing until the sync job finishes.

## Production considerations
- The Gateway uses the `NONE` authorizer for this lab only. Production needs OAuth or IAM-signed requests.
- OpenSearch Serverless behind the Knowledge Base is the main idle cost. Add budgets and alarms.
- Turn on tracing for Gateway and Memory resources so CloudWatch GenAI Observability shows full traces.

## Run it
Needs Python 3.13, `uv`, AWS credentials, and the resources above. Set `GATEWAY_URL`, `KB_ID`, `REGION`, `MEMORY_ID` in `starter/main.py`, then from `starter/`:
```
uv sync --python 3.13
uv run agentcore configure --entrypoint main.py --name csagent --deployment-type direct_code_deploy --runtime PYTHON_3_13 --disable-memory
uv run agentcore deploy
uv run setup_permissions.py
agentcore invoke '{"prompt": "Can you track order ORD-001?", "customer_id": "CUST-123", "session_id": "t1"}'
```
The original Udacity brief is kept in the starter repository this project was based on.
