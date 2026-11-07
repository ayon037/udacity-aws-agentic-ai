# Submission: E-commerce Customer Support Agent (AgentCore + Strands)

## Contents
| Path | What it is |
|---|---|
| `starter/main.py` | Completed agent, all sections implemented |
| `starter/pyproject.toml` | Dependencies (`strands-agents-tools` pinned `<0.9`, see reflection) |
| `starter/lambda/` | `order_tracker.py`, `refund_processor.py`, `lambda_schema` (deployed unchanged) |
| `starter/product_catalog.txt` | Knowledge Base source document |
| `starter/setup_permissions.py` | Post-deploy permissions script (unchanged) |
| `test_logs/test1..test6*.txt` | Terminal output of each `agentcore invoke` test, including the command |
| `test_logs/screenshots/*.png` | The same tests as screenshots |
| `test_logs/tool_output_evidence.md` | CloudWatch tool-call lines plus raw tool outputs for each test |
| `reflection.md` | Written reflection (design decision, challenge, production consideration) |

## Rubric map
| Rubric criterion | Where to look |
|---|---|
| Deploy an agent to a cloud runtime | `main.py`: `app = BedrockAgentCoreApp()`, `@app.entrypoint async def invoke`, `app.run()`. Tests 1-6 show `agentcore invoke` responding without errors. |
| MCP tools via Gateway | `main.py`: `MCPClient(lambda: streamable_http_client(GATEWAY_URL))`, `list_tools_sync()` added to tools. Test 1 = API-based target (`order-tracker___get_order`), Test 2 = Lambda-based target (`refund-processor___initiate_refund`). Evidence file shows both calls and raw results. |
| RAG with a Knowledge Base | `main.py`: `search_knowledge_base` (`@tool`, `KB_ID` guard, Retrieve API, chunks joined with `\n---\n`, descriptive docstring). Test 3. |
| Cross-session memory | `main.py`: `get_namespaces`, `MemoryHook` (`retrieve_customer_context`, `save_support_interaction`, `register_hooks`). Test 4: sessions `s-A` and `s-B`, same customer `CUST-123`. Stored records are listed in the evidence file. |
| Sandboxed code interpreter | `main.py`: `calculate_loyalty_discount` (`@tool`, code string with redemption, tier and earn rules, `code_session(REGION).invoke("executeCode", ...)` with `clearContext=True`, tier-only fallback). Result fields: `points_redeemed`, `tier_discount_pct`, `final_total`, `remaining_points`. Test 5 and the sandbox output in the evidence file. |
| Browser tool | `main.py`: `AgentCoreBrowser(region=REGION)` added to tools. Test 6 returns the live udacity.com page title. |
| Reflection (200-400 words) | `reflection.md` |

AWS account IDs are redacted (`XXXXXXXXXXXX`) in logs and evidence.
