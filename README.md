# 🇳🇬 Igbo Archives Autonomous Ingestion System (HQ)

[![AI-Powered](https://img.shields.io/badge/AI-Autonomous%20Agents-blueviolet)](https://google.github.io/google-adk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An enterprise-grade, fully autonomous AI pipeline designed for **Daily Cultural Archiving**. This system preserves Igbo heritage by intelligently fetching colonial-era metadata from Hugging Face, performing deep visual analysis, and publishing validated entries to the [Igbo Archives](https://igboarchives.com.ng) platform via MCP.

## 🏗️ Architecture: The Agent Hive
The system follows a **Supervised Hierarchical Pipeline** using the **Agent-as-a-Tool** pattern:

- **Orchestrator**: The supervisor. Coordinates the hive by delegating to sub-agents as tools.
- **Fetcher**: Meta-data first deterministic row retrieval from HF.
- **Vision Analyst**: Visual context reporter (Quarantined from metadata).
- **Synthesis Loop**: Iterative Writer/Critic refinement.
- **Publisher**: Final commit engine via MCP.

## 🛠️ Tech Stack
-   **Framework**: [Google ADK v1.26](https://google.github.io/google-adk/)
-   **Execution**: Python 3.13 with [uv](https://github.com/astral-sh/uv).
-   **Persistence**: Neon DB (Postgres) with `DatabaseSessionService`.
-   **Integrations**: Hugging Face Hub, Telegram Bot API, Custom MCP Client.

## 🚀 Installation & Usage

### 1. Setup
```bash
# Clone & Sync
git clone https://github.com/Nwokike/Archives-Agent.git
cd archives-agent
uv sync

# Configure Environment
# Ensure .env contains GOOGLE_API_KEY, TELEGRAM_BOT_TOKEN, NEON_DATABASE_URL, IGBO_ARCHIVES_TOKEN
```

### 2. Run the Production Suite
```bash
# Start the Telegram Bot + Dynamic Status Streaming
uv run python app.py
```

### 3. Debug with ADK Web
```bash
# Discover the Orchestrator App
uv run adk web agents
```
