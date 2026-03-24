# 🇳🇬 Igbo Archives Autonomous Ingestion System (HQ)

[![AI-Powered](https://img.shields.io/badge/AI-Autonomous%20Agents-blueviolet)](https://google.github.io/google-adk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An enterprise-grade, fully autonomous AI pipeline designed for **Daily Cultural Archiving**. This system preserves Igbo heritage by intelligently fetching colonial-era metadata from Hugging Face, performing deep visual analysis, and publishing validated entries to the [Igbo Archives](https://igboarchives.com.ng) platform.

## 🏗️ Architecture: The Agent Hive
The system follows a **Supervised Hierarchical Pipeline**. To ensure compatibility with the **ADK Web UI**, each agent is organized into its own subdirectory:

- **Orchestrator**: The root brain. Manages conversational intent and triggers the pipeline.
- **Fetcher**: Meta-data first deterministic row retrieval.
- **Vision Analyst**: Quarantined visual context analyzer.
- **Synthesis Loop**: Iterative Writer/Critic refinement.
- **Publisher**: Final commit engine via MCP.

## 🛠️ Tech Stack
-   **Framework**: [Google ADK v1.26](https://google.github.io/google-adk/)
-   **Execution**: Python 3.13 with [uv](https://github.com/astral-sh/uv).
-   **Persistence**: Neon DB (Postgres).
-   **Integrations**: Hugging Face Hub, Telegram Bot API, MCP.

## 🚀 Installation & Usage

### 1. Setup
```bash
# Clone & Sync
git clone https://github.com/Nwokike/Archives-Agent.git
cd archives-agent
uv sync

# Configure Environment
cp .env.example .env
# Edit .env with your credentials.
```

### 2. Run the Bot
```bash
uv run python app.py
```
*Chat with the bot: **"Archive row 500"** or **"Today's archive"**.*

### 3. Debug with ADK Web
```bash
uv run adk web agents/
```
*Browse individual agents and inspect history in the local dashboard.*
