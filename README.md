# 🇳🇬 Igbo Archives Autonomous Ingestion System (HQ)

[![AI-Powered](https://img.shields.io/badge/AI-Autonomous%20Agents-blueviolet)](https://google.github.io/google-adk/)
[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red.svg)](https://kiri.ng/about)

An enterprise-grade, fully autonomous AI pipeline designed for **Daily Cultural Archiving**. This system preserves Igbo heritage by intelligently fetching colonial-era metadata from Hugging Face, performing deep visual analysis (Gemini/Groq), and publishing validated entries to the [Igbo Archives](https://igboarchives.com.ng) platform via MCP.

## 🏗️ Architecture: Native ADK 2026 Pipeline

The system utilizes the **Google ADK v1.26** framework, following a **Sequential & Loop Agent** pattern for deterministic, stateful execution.

- **Orchestrator** (`moonshotai/kimi-k2-instruct-0905` via LiteLLM): The conversational supervisor. Oversees the entire state and delegates to the `archive_pipeline`.
- **`execute_archive_pipeline`** (SequentialAgent):
    - **Fetcher**: Deterministic metadata retrieval using `{current_index}` template variables.
    - **Taxonomy Mapper**: Programmatic injection of live taxonomy for entity resolution.
    - **Vision Analyst**: Visual context reporter (Quarantined from metadata).
    - **Synthesis Loop** (LoopAgent): Iterative Writer/Critic refinement using Kiri's Anti-Hallucination protocol.
    - **Publisher**: Final commit engine with native `ToolContext` state increments.

## 💾 Native Persistence & Memory

This system achieves **Zero-Nonsense State Management** by leveraging ADK's native features:
- **Persistent State**: Leverages `DatabaseSessionService` with Neon PostgreSQL for long-running session awareness.
- **Instruction Templates**: State variables like `{current_index}` and `{dataset_id}` are natively injected into agent instructions, ensuring all agents are grounded in the same reality.
- **State Hydration**: Includes a `bootstrap_state` callback for seamless `adk web` compatibility.

## 🛠️ Tech Stack
-   **Framework**: [Google ADK v1.26](https://google.github.io/google-adk/)
-   **Execution**: Python 3.13 with [uv](https://github.com/astral-sh/uv).
-   **Models**: LiteLLM integration for **Groq (Moonshot Kimi)** and **Gemini 2.0/3.1**.
-   **Persistence**: Neon Serverless Postgres with `postgresql+psycopg://` driver.
-   **Integrations**: Hugging Face Hub, Telegram Bot, Custom MCP.

## 🚀 Usage

### 1. Setup
```bash
# Clone & Sync
git clone https://github.com/Nwokike/Archives-Agent.git
cd archives-agent
uv sync

# Ensure .env contains:
# GOOGLE_API_KEY, GROQ_API_KEY, NEON_DATABASE_URL, IGBO_ARCHIVES_TOKEN
```

### 2. Autonomous Run
```bash
# Start the production bot suite
python app.py
```

### 3. Debug with ADK Web
```bash
# Start the Web UI for agent inspection
adk web agents
```

---
Copyright © 2026 [Kiri Research Labs](https://kiri.ng/about). All rights reserved. Proprietary software.
