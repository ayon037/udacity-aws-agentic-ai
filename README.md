# Udacity AWS Agentic AI Nanodegree: Projects

Two hands-on projects building agents on **Amazon Bedrock AgentCore** and the **Strands Agents SDK**.

| # | Project | What it shows | Folder |
|---|---|---|---|
| 1 | Support chatbot with prompt-based routing | Single-prompt intent classification, a bug-report tool behind an AgentCore Gateway (Lambda + DynamoDB), FAQ grounding, and an automated Bedrock Evaluations run (10/10 correctness) | [`project1-prompting-llm-reasoning`](project1-prompting-llm-reasoning/) |
| 2 | E-commerce customer support agent | AgentCore Runtime deployment, MCP tools via Gateway, RAG with a Bedrock Knowledge Base, cross-session Memory, Code Interpreter, Browser tool | [`project2-customer-support-agent`](project2-customer-support-agent/) |

## Skills demonstrated
- Deploying agents to AgentCore Runtime (`BedrockAgentCoreApp`, `@app.entrypoint`)
- Exposing REST APIs and Lambda functions as MCP tools through AgentCore Gateway
- Retrieval-Augmented Generation with a managed Knowledge Base
- Long-term, cross-session memory with semantic and user-preference strategies
- Sandboxed computation with the AgentCore Code Interpreter, with a safe fallback
- Prompt engineering, evaluation datasets, and iterating from eval findings

## Notes
- AWS account IDs are redacted (`XXXXXXXXXXXX`). No credentials are stored in this repo.
- Each project folder has its own README with architecture, setup, results and lessons learned.
- This is shared as a portfolio of my own work. If you are a Udacity student, use it to compare approaches after attempting the project yourself.
