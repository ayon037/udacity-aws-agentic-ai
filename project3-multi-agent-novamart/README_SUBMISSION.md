# Project 3: NovaMart Multi-Agent Customer Support (submission map)

Where each deliverable and rubric item lives.

| Deliverable | Location |
|---|---|
| Completed `agent_orchestrator.py` (Tasks 2, 3, 4, 6) | `starter/src/agent_orchestrator.py` |
| Populated `.env` (KB IDs, Runtime ARN, Guardrail ID and version) | `starter/.env` (submitted in the zip; not committed here, see `starter/.env.example`) |
| Three Bedrock Knowledge Bases (synced, S3 Vectors, Titan Embed v2) | IDs in `.env`; checked by `test_agent.py task5` |
| Screenshot: all tests passed, 120/120 | `screenshots/01_all_tests_120_of_120.png` |
| Screenshot: X-Ray Service Map | `screenshots/03_xray_service_map.png` |
| Extra: guardrail adversarial and allowed-math checks | `screenshots/02_guardrail_validation.png` |

## Rubric map

| Rubric area | Where to look |
|---|---|
| Worker agents (tools, models, temperatures 0.1 / 0.1 / 0.3) | `build_inventory_agent`, `build_refund_agent`, `build_communication_agent` |
| Multi-agent RAG, three retrievers, `ThreadPoolExecutor(max_workers=3)` + `as_completed` | `build_policy_agent` / `search_all_policies` |
| Orchestrator, six routing rules, WorkflowState with optimistic locking | `build_orchestrator_agent` |
| Guardrail (content, PII, 3 DENY topics, profanity, numbered version) | `create_guardrail` |
| Runtime via AgentCore CLI (PUBLIC, HTTP, env vars) | `deploy_to_agentcore_runtime` |
| Memory: summaryMemoryStrategy, 7-day expiry | `configure_memory` |
| Observability: CloudWatch INFO and X-Ray 100% | `configure_observability` |

## Evidence in `test_logs/`

- `test_all_120_of_120.txt`: full `python tests/test_agent.py all` output, score 120/120.
- `live_scenarios_local_run.txt`: the three required scenarios via `python src/agent_orchestrator.py test`
  (return: Inventory, Refund, Communication; policy: Policy with 3 parallel retrievers, Communication;
  math: Communication only).
- `live_scenarios_deployed_runtime.txt`: the same scenarios through the deployed AgentCore Runtime.
- `guardrail_validation.txt`: math question and answer allowed; negotiation, competitor, legal-threat,
  credit-card and violence prompts blocked.

## Notes

- Knowledge Bases were created through the Bedrock API (self-managed, not Managed KB) against the stack's
  S3 Vectors bucket and the three matching indexes, then synced. `test_agent.py task5` confirms the
  embedding model, ACTIVE status and a completed sync for each.
- The Communication Agent returns its message inside `<result>` tags and the routing tool extracts it, so
  internal commentary never reaches the customer.
