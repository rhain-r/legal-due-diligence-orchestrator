# Legal Due Diligence Orchestrator

An Agentic AI architecture designed for law firms and enterprise compliance teams. This is not a simple document summarizer; it is a multi-agent system where different AI "personas" collaborate to audit legal contracts against strict Standard Operating Procedures (SOPs).

Instead of paralegals spending hours scanning for missing clauses, a Lead Agent delegates document chunks to Worker Agents, who then report back to a Verifier Agent to ensure absolute accuracy and zero hallucinations.

---

## Agentic Workflow Execution

The workflow relies on a hierarchical agent structure. The Orchestrator receives the document and compliance checklist. It dispatches read-tasks to specialized agents (e.g., Liability Agent, Jurisdiction Agent). Their findings are then aggressively challenged by the Verifier Agent before a final report is generated.

![Multi-Agent Workflow](./assets/workflow-execution.jpg)
*(Note: Upload your execution image to the assets folder and replace this filename)*

---

## Project Overview

This project demonstrates how high-risk industries can safely utilize Agentic AI by implementing "Verification Loops." It is built using Python, Autogen (or LangGraph), and Claude AI.

The workflow begins when a PDF is dropped into a secure bucket. The Lead Agent normalizes the text and begins executing the firm's compliance SOP. If an agent claims a clause is missing, the Verifier Agent is triggered to re-read the document using a different search strategy to confirm the omission.

---

## Agent Capabilities

*   **Multi-Agent Orchestration:** Lead agent assigns tasks to sub-agents.
*   **Strict Verification Loops:** Cross-examines AI outputs to eliminate false positives/hallucinations.
*   **Context-Aware Reading:** Understands legal phrasing rather than relying on exact keyword matches.
*   **Structured Output Generation:** Forces the LLM to output findings in strict JSON format.
*   **Citation Tool Use:** Agents must use the `cite_source()` tool to provide exact page/paragraph numbers for findings.

---

## Audit State & Finding Log

The system maintains a strict audit trail of what the agents found and verified.

| Contract ID | Agent Assigned | Clause Checked | Finding | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| NDA-8812 | Liability_Bot | Cap on Damages | Missing | Verified by Verifier_Bot |
| LSE-1049 | General_Bot | Jurisdiction | Found (Sec 4.2) | Auto-Approved |

---

## Agentic Architecture Overview

```text
[ Document Ingestion ]
       │
       ▼
[ Lead Agent: Plan Strategy ]
       │
       ├──► [ Worker Agent 1: Check Liability ] ──► "Found uncapped risk."
       │
       ├──► [ Worker Agent 2: Check Termination ] ─► "Clause missing."
       │
       ▼
[ Verifier Agent: Challenge Findings ]
       │
       ├──► Scans document again for "Termination" synonyms.
       │
       ▼
[ Output Agent: Generate Strict JSON Report ]
```

---

## Tech Stack

| Component | Technology |
| :--- | :--- |
| Agent Framework | Microsoft AutoGen / CrewAI |
| LLM Reasoning Engine | Anthropic Claude 3/5 Sonnet |
| Document Parsing | PyPDF2 / LlamaParse |
| Validation | Pydantic (Strict JSON) |
| Version Control | GitHub |

---

## Repository Structure

```
docs/
    architecture.md
    compliance-rules.md
    setup-guide.md
agent/
    orchestrator.py
    workers.py
    verifier.py
assets/
    workflow-execution.jpg
```
