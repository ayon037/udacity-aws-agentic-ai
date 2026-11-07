# Tool Output Evidence (CloudWatch logs and direct tool calls)

Region us-east-1, agent runtime `csagent`. This file backs up the six test logs with tool-level evidence.

**How to read this document.** Three kinds of evidence are used, and each section says which:

- **Runtime log** = lines the deployed agent wrote to CloudWatch (`/aws/bedrock-agentcore/runtimes/csagent-...`) during the original test runs. These show *which tools the agent called* and in what order. The runtime does not log raw tool results.
- **Lambda log** = lines the backend Lambdas wrote to CloudWatch during the same runs (arguments the agent sent).
- **Direct call** = the same tool called again afterwards, outside the agent, to show the raw output it returns. Direct calls were made after the tests, so IDs and timestamps differ from the test run where noted.

---

## Test 1: Order tracking (API-based Gateway target)

**Runtime log (15:37:26 UTC):** `Tool #1: order-tracker___get_order`

**Lambda log, `/aws/lambda/order-tracker` (15:37:26 UTC):**
```
Event: {"resource": "/orders/{order_id}", "path": "/orders/ORD-001", "httpMethod": "GET", ...}
Request: GET /orders/{order_id} {'order_id': 'ORD-001'}
```

**Direct call to the Gateway tool, raw result (isError false):**
```
isError: False
{
  "order_id": "ORD-001",
  "customer_id": "CUST-123",
  "status": "SHIPPED",
  "items": [
    {
      "name": "Wireless Headphones Pro",
      "qty": 1,
      "price": 89.99
    }
  ],
  "total": 89.99,
  "tracking_number": "TRK987654321",
  "carrier": "UPS",
  "estimated_delivery": "2026-11-09"
}
```

## Test 2: Refund (Lambda-based Gateway target)

**Runtime log (15:37:35 to 15:37:37 UTC):**
```
Tool #1: order-tracker___get_order
Tool #2: refund-processor___initiate_refund
```

**Lambda log, `/aws/lambda/refund-processor` (15:37:37 UTC):**
```
Tool called: initiate_refund | Event: {"reason": "Customer return", "amount": 139.99, "order_id": "ORD-002"}
```

**Direct call to the Gateway tool, raw result (new refund ID, because each call creates a refund):**
```
isError: False
{
  "statusCode": 200,
  "body": "{\"refund_id\": \"REF-8DC5TC1Y\", \"order_id\": \"ORD-002\", \"status\": \"APPROVED\", \"amount\": 139.99, \"message\": \"Refund approved. Credit appears in 3-5 business days.\", \"created_at\": \"2026-11-07T16:09:36.543327+00:00\"}"
}
```

## Test 3: Knowledge Base (RAG)

**Runtime log (15:37:43 UTC):** `Tool #1: search_knowledge_base`

**Direct Retrieve API call, passage returned for "What are the benefits of the Platinum loyalty tier?":**
```
### Tier Benefits
- Gold: Free expedited shipping, 10% discount
- Platinum: Free same-day shipping, 15% discount, priority customer support
```

## Test 4: Cross-session memory

Session A (`s-A`) stated the name and preference. Session B (`s-B`, new session, same customer `CUST-123`) answered: "Yes Jane, I remember your name and that you prefer concise responses." (runtime log, 15:40:12 UTC).

**Memory records stored for `CUST-123`, retrieved from AgentCore Memory, namespace `cs_agent/CUST-123/facts`:**
- Jane requested a return and refund for a Kindle Paperwhite (Order ORD-002) on 2026-11-07. The refund of $139.99 was approved with Refund ID REF-27N4971J.
- The user has 4,250 loyalty points (as of 2026-11-07).
- Jane placed order ORD-001 for Wireless Headphones Pro (1 unit at $89.99), shipped via UPS with tracking number TRK987654321, with an estimated delivery of November 9, 2026.
- The user is a Gold member in a loyalty program with 4,250 loyalty points (as of 2026-11-07).
- The user's name is Jane and she prefers concise responses.

**Namespace `cs_agent/CUST-123/preferences`:**
- `{"context":"Receiving information or answers","preference":"Prefers concise responses","categories":["communication style","response length"]}`

## Test 5: Loyalty discount (Code Interpreter)

**Runtime log (15:37:49 UTC):** `Tool #1: calculate_loyalty_discount`

**Direct call, raw sandbox result for loyalty_points=4250, tier=Gold, order_total=150.0, product_category=standard (exitCode 0):**
```
{
  "order_total": 150.0,
  "tier": "Gold",
  "points_redeemed": 4000,
  "points_discount": 40.0,
  "tier_discount_pct": 10,
  "tier_discount": 11.0,
  "final_total": 99.0,
  "total_savings": 51.0,
  "points_earned": 99,
  "remaining_points": 349
}
```
All four required fields are present: `points_redeemed`, `tier_discount_pct`, `final_total`, `remaining_points`.

## Test 6: Browser

**Runtime log (15:38:01 to 15:38:50 UTC):** five `browser` tool calls (`Tool #1` to `Tool #5: browser`), then the agent returned the live page title: "Learn the Latest Tech Skills; Advance Your Career | Udacity".

## Gateway tool registration

Tools listed by the Gateway MCP endpoint (`tools/list`):
```
order-tracker___get_customer
order-tracker___get_customer_orders
order-tracker___get_order
refund-processor___check_refund_status
refund-processor___get_return_label
refund-processor___initiate_refund
```
