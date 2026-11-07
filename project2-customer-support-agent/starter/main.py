"""
Customer Support AI Agent
=========================
An e-commerce support agent on Amazon Bedrock AgentCore Runtime (Strands SDK).
Tools: Gateway (MCP) order and refund tools, Knowledge Base RAG, Code Interpreter
loyalty calculator and the AgentCore Browser. Cross-session memory via MemoryHook.

Run locally (after filling in config values):
  uv run main.py '{"prompt": "Hello", "customer_id": "CUST-123", "session_id": "s1"}'

Deploy to AgentCore:
  agentcore deploy

Invoke deployed agent:
  agentcore invoke '{"prompt": "Hello", "customer_id": "CUST-123", "session_id": "s1"}'
"""

# ── Imports ───────────────────────────────────────────────────────────────────
# These imports are provided. Do not remove them.
from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory import MemoryClient
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamable_http_client
import argparse, json
import os, asyncio, boto3
from strands.hooks import (
    HookProvider, AfterInvocationEvent, HookRegistry, MessageAddedEvent,
)
import logging
import uuid
from typing import Dict
from bedrock_agentcore.tools.code_interpreter_client import code_session
from strands_tools.browser import AgentCoreBrowser


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("CSAI_Agent")

# ── App Initialisation ──────────────────────────────────────────────────────────

app = BedrockAgentCoreApp()


# Suppress interactive tool-consent prompts (required in headless deployments).
os.environ["BYPASS_TOOL_CONSENT"] = "true"


# ── Configuration ───────────────────────────────────────────────────────────────

GATEWAY_URL = "https://customersupportgateway-s24zviuwtj.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
KB_ID       = "K3L8BJDRMJ"
REGION      = "us-east-1"
MEMORY_ID   = "CustomerSupportMemory-pB3x47EUod"


# ── Model and Clients ───────────────────────────────────────────────────────────

model_id = "global.amazon.nova-2-lite-v1:0"

model = BedrockModel(model_id=model_id)
memory_client = MemoryClient(region_name=REGION)
_bedrock_runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)


# ── Namespace Helper ────────────────────────────────────────────────────────────

def get_namespaces(mem_client: MemoryClient, memory_id: str) -> Dict:
    """Return a dict mapping strategy type → namespace template string."""
    namespaces: Dict[str, str] = {}
    for strategy in mem_client.get_memory_strategies(memory_id):
        templates = strategy.get("namespaceTemplates") or strategy.get("namespaces") or []
        strategy_type = strategy.get("memoryStrategyType") or strategy.get("type")
        if templates and strategy_type:
            namespaces[strategy_type] = templates[0]
    return namespaces


# ── Memory Hook ─────────────────────────────────────────────────────────────────

class MemoryHook(HookProvider):
    """Long-term memory hook for the customer support agent."""

    def __init__(
        self,
        actor_id: str,
        session_id: str,
        memory_client: MemoryClient,
        memory_id: str,
    ):
        self.actor_id = actor_id
        self.session_id = session_id
        self.memory_id = memory_id
        self.memory_client = memory_client
        self.namespaces = get_namespaces(memory_client, memory_id)

    def retrieve_customer_context(self, event: MessageAddedEvent):
        """Retrieve relevant memories and prepend them to the user message."""
        messages = event.agent.messages
        if not messages:
            return
        last = messages[-1]
        if last.get("role") != "user":
            return
        content = last.get("content", [])
        if not content or "text" not in content[0] or "toolResult" in content[0]:
            return
        user_query = content[0]["text"]

        try:
            context_lines = []
            for strategy_type, template in self.namespaces.items():
                namespace = template.format(actorId=self.actor_id)
                memories = self.memory_client.retrieve_memories(
                    memory_id=self.memory_id,
                    namespace=namespace,
                    query=user_query,
                    top_k=5,
                )
                for memory in memories:
                    text = memory.get("content", {}).get("text", "").strip()
                    if text:
                        context_lines.append(f"[{strategy_type}] {text}")
            if context_lines:
                joined = "\n".join(context_lines)
                content[0]["text"] = f"Customer Context:\n{joined}\n\n{user_query}"
        except Exception as e:
            logger.warning("Memory retrieval failed: %s", e)

    def save_support_interaction(self, event: AfterInvocationEvent):
        """Save the completed turn to memory after the agent responds."""
        try:
            messages = event.agent.messages
            customer_query = None
            agent_response = None
            for msg in reversed(messages):
                content = msg.get("content", [])
                if not content or "text" not in content[0]:
                    continue
                if msg["role"] == "assistant" and agent_response is None:
                    agent_response = content[0]["text"]
                elif msg["role"] == "user" and customer_query is None:
                    customer_query = content[0]["text"]
                    if customer_query.startswith("Customer Context:") and "\n\n" in customer_query:
                        customer_query = customer_query.split("\n\n", 1)[1]
                if customer_query and agent_response:
                    break
            if customer_query and agent_response:
                self.memory_client.create_event(
                    memory_id=self.memory_id,
                    actor_id=self.actor_id,
                    session_id=self.session_id,
                    messages=[(customer_query, "USER"), (agent_response, "ASSISTANT")],
                )
        except Exception as e:
            logger.warning("Memory save failed: %s", e)

    def register_hooks(self, registry: HookRegistry) -> None:  # type: ignore
        """Register both memory callbacks."""
        registry.add_callback(MessageAddedEvent, self.retrieve_customer_context)
        registry.add_callback(AfterInvocationEvent, self.save_support_interaction)


# ── Knowledge Base Tool ─────────────────────────────────────────────────────────

@tool
def search_knowledge_base(query: str) -> str:
    """
    Search the Amazon product catalog and support knowledge base.
    Use this for product specifications, return policies, warranty
    information, loyalty program details, and order status definitions.

    Args:
        query: The question or topic to search for

    Returns:
        Relevant information retrieved from the knowledge base
    """
    if not KB_ID:
        return "Knowledge base not configured."
    resp = _bedrock_runtime.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={"text": query},
    )
    results = resp.get("retrievalResults", [])
    if not results:
        return "No relevant information found in the knowledge base."
    return "\n---\n".join(r["content"]["text"] for r in results)


# ── Loyalty Discount Tool (Code Interpreter) ────────────────────────────────────

@tool
def calculate_loyalty_discount(
    loyalty_points: int,
    tier: str,
    order_total: float,
    product_category: str = "standard",
) -> str:
    """
    Calculate the loyalty discount for a customer order using the
    AgentCore Code Interpreter. Runs exact arithmetic in a secure sandbox.

    Args:
        loyalty_points:   Customer's current points balance
        tier:             Customer tier — Silver, Gold, or Platinum
        order_total:      Order total in USD
        product_category: standard, device, or fresh

    Returns:
        Full discount breakdown and final price
    """
    code = f"""
import json, math

loyalty_points = {int(loyalty_points)}
tier = {tier!r}
order_total = {float(order_total)}
product_category = {product_category!r}

earn_rates = {{"standard": 1, "device": 2, "fresh": 5}}
tier_rates = {{"Silver": 0.00, "Gold": 0.10, "Platinum": 0.15}}

# 100 points = $1. Redeem in blocks of 500 points, capped at 50% of the order.
max_points_by_order = math.floor((order_total * 0.5 * 100) / 500) * 500
points_redeemed = min(math.floor(loyalty_points / 500) * 500, max_points_by_order)
points_redeemed = max(points_redeemed, 0)
points_discount = points_redeemed / 100

subtotal_after_points = order_total - points_discount
tier_discount = round(subtotal_after_points * tier_rates.get(tier, 0.0), 2)
final_total = round(subtotal_after_points - tier_discount, 2)
total_savings = round(points_discount + tier_discount, 2)
points_earned = math.floor(final_total * earn_rates.get(product_category, 1))
remaining_points = loyalty_points - points_redeemed + points_earned

print(json.dumps({{
    "order_total": order_total,
    "tier": tier,
    "points_redeemed": points_redeemed,
    "points_discount": round(points_discount, 2),
    "tier_discount_pct": int(tier_rates.get(tier, 0.0) * 100),
    "tier_discount": tier_discount,
    "final_total": final_total,
    "total_savings": total_savings,
    "points_earned": points_earned,
    "remaining_points": remaining_points,
}}))
"""

    try:
        with code_session(REGION) as code_client:
            response = code_client.invoke(
                "executeCode",
                {"code": code, "language": "python", "clearContext": True},
            )
            for event in response["stream"]:
                return json.dumps(event["result"])
        return json.dumps({"error": "Code Interpreter returned no result."})

    except Exception as e:
        logger.warning("Code Interpreter unavailable, using fallback: %s", e)
        rates = {"Silver": 0.00, "Gold": 0.10, "Platinum": 0.15}
        rate = rates.get(tier, 0.0)
        discount = round(order_total * rate, 2)
        return json.dumps({
            "fallback": True,
            "note": "Code Interpreter unavailable; tier discount only, no points redemption.",
            "tier": tier,
            "points_redeemed": 0,
            "tier_discount_pct": int(rate * 100),
            "tier_discount": discount,
            "final_total": round(order_total - discount, 2),
            "remaining_points": loyalty_points,
        })


# ── Agent Entrypoint ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a helpful e-commerce customer support assistant.
The current customer ID is {customer_id}.

Tools:
- Order tools (via Gateway): look up orders and customers, and process refunds
  and return labels. Always call a tool for order or refund questions; never
  guess order details.
- search_knowledge_base: product specs, return/warranty policy, loyalty program
  details, order status definitions.
- calculate_loyalty_discount: exact loyalty discount maths. Never calculate
  discounts yourself.
- browser: open live web pages when asked for real-time web information.

If the message starts with "Customer Context:", use it to personalise your reply
(name, preferences). Be accurate, concise and polite. If a tool fails, say so
plainly instead of inventing an answer."""


@app.entrypoint
async def invoke(payload, context=None):
    """
    Main handler called by AgentCore for every incoming request.

    Expected payload keys:
      prompt      (str, required) — the customer's message
      customer_id (str, optional) — unique customer identifier
      session_id  (str, optional) — session identifier; generated if absent
    """
    try:
        user_input = payload.get("prompt", "")
        actor_id = payload.get("customer_id", "anonymous")
        session_id = payload.get("session_id") or str(uuid.uuid4())

        memory_hook = MemoryHook(
            actor_id=actor_id,
            session_id=session_id,
            memory_client=memory_client,
            memory_id=MEMORY_ID,
        )
        agent_core_browser = AgentCoreBrowser(region=REGION)
        tools = [
            search_knowledge_base,
            calculate_loyalty_discount,
            agent_core_browser.browser,
        ]

        mcp_client = MCPClient(lambda: streamable_http_client(GATEWAY_URL))
        # The MCP session must stay open while the agent runs, so build and
        # invoke the Agent inside the `with` block.
        with mcp_client:
            tools.extend(mcp_client.list_tools_sync())
            agent = Agent(
                model=model,
                tools=tools,
                hooks=[memory_hook],
                system_prompt=SYSTEM_PROMPT.format(customer_id=actor_id),
            )
            response = agent(user_input)
        return response.message["content"][0]["text"]

    except Exception as e:
        logger.exception("Agent invocation failed")
        return f"Sorry, I ran into a problem handling your request: {e}"


# ── CLI entry point (do not modify) ──────────────────────────────────────────
def main():
    """Run one invocation from the command line for local testing."""
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=str)
    args = parser.parse_args()
    response = asyncio.run(invoke(json.loads(args.payload)))
    print(response)


if __name__ == "__main__":
    app.run()
    # Uncomment the line below and comment app.run() for local CLI testing:
    # main()
