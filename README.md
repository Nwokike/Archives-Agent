# Igbo Archives Autonomous Ingestion System

[![AI-Powered](https://img.shields.io/badge/AI-Autonomous%20Agents-blueviolet)](https://google.github.io/google-adk/)
[![Powered by Google Gemini](https://img.shields.io/badge/Powered%20by-Google%20Gemini-orange)](https://ai.google/gemini/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An enterprise-grade, fully autonomous AI pipeline designed for **Daily Cultural Archiving**. This system preserves Igbo heritage by intelligently fetching colonial-era metadata from Hugging Face, performing deep visual analysis, augmenting facts with live web research, and publishing validated entries to the [Igbo Archives](https://igboarchives.com.ng) platform via an MCP client.

## 🏗️ Architecture: The Agent Hive
The system follows a **Supervised Hierarchical Pipeline** leveraging Google ADK's `SequentialAgent` and `LoopAgent` routing:

- **Orchestrator**: The root supervisor. Fetches HF records and halts the pipeline if the image fundamentally mismatches the metadata.
- **Vision Analyst (Hardened Tool)**: A quarantined multimodal visual inspector. Features auto-image-resizing and exponential backoff to bypass inference server payload limits.
- **Context Researcher (RAG)**: A DuckDuckGo-powered retrieval agent that scours the internet for missing geographical and historical context before writing begins.
- **Taxonomy Mapper**: Aligns historical metadata with the live database categories and authors.
- **Synthesis Loop**: A strict Writer/Critic iterative refinement loop. Enforces formatting rules (no AI-speak, no em-dashes) and uses a deterministic `CriticEscalationChecker` to handle approvals.
- **Publisher**: The "fire-and-forget" final executioner. Pushes the approved JSON payload to the remote MCP server and explicitly commits the session state.

## 🛠️ Tech Stack
-   **Framework**: Google ADK (2026)
-   **LLM Engine**: Google Gemini 3.1 Flash-Lite (Primary) & Google Gemma 4 (Fallback) via `litellm`.
-   **Execution**: Python 3.13 with [uv](https://github.com/astral-sh/uv).
-   **Persistence**: Neon DB (Postgres) via ADK `DatabaseSessionService`.
-   **Serverless Infrastructure**: Google Cloud Run + Cloud Tasks (Bypasses CPU scale-to-zero timeouts during long agent chains).
-   **Integrations**: Hugging Face Hub, DuckDuckGo Search, Telegram Bot API, Custom MCP Client.

## 🚀 Installation & Usage

### 1. Setup
```bash
# Clone & Sync
git clone [https://github.com/Nwokike/Archives-Agent.git](https://github.com/Nwokike/Archives-Agent.git)
cd archives-agent
uv sync

```

### 2. Run the Production Suite
The app auto-detects its environment. It runs a Polling Bot locally, or a Webhook + Cloud Tasks worker in production.
```bash
# Start the Telegram Bot + Dynamic Status Streaming
uv run python app.py
```

### 3. Debug with ADK Web UI
Visualize the agent trace, session states, and artifact generation locally:
```bash
# Start the ADK Dev Server
uv run adk web
```

## 🧠 State Management
This pipeline utilizes ADK's Shared Session State to pass variables (`raw_metadata`, `vision_report`, `research_context`, `critic_status`) seamlessly between agents without prompt stuffing, ensuring maximum token efficiency and clean separation of concerns.
