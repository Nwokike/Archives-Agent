# Igbo Archives Autonomous Ingestion System

[![AI-Powered](https://img.shields.io/badge/AI-Autonomous%20Agents-blueviolet)](https://google.github.io/google-adk/)
[![Powered by DeepMind Gemma 4](https://img.shields.io/badge/Powered%20by-DeepMind%20Gemma%204-orange)](https://deepmind.google/models/gemma/gemma-4/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An enterprise-grade, fully autonomous AI pipeline designed for **Daily Cultural Archiving**. This system preserves Igbo heritage by intelligently fetching colonial-era metadata across multiple dynamic Hugging Face datasets, performing deep visual analysis, augmenting facts with live web research, and publishing validated entries to the [Igbo Archives](https://igboarchives.com.ng) platform via an MCP client.

## 🎛️ Telegram Control Panel
The bot features a dynamic inline menu to seamlessly switch between historical datasets while maintaining isolated row-tracking memory for each one.
- `/menu` or `/start`: Opens the interactive Dataset Selection Menu.
- `/new` (or UI Button): Clears memory and securely processes the next unarchived row for the active dataset.

## 🏗️ Architecture: The Agent Hive
The system follows a **Supervised Hierarchical Pipeline** leveraging Google ADK's `SequentialAgent` and `LoopAgent` routing:

- **Orchestrator**: The root supervisor. Dynamically routes dataset targets via System Directives and halts the pipeline if the image fundamentally mismatches the metadata.
- **Vision Analyst (Hardened Tool)**: A quarantined multimodal visual inspector. Features auto-image-resizing and exponential backoff to bypass inference server payload limits.
- **Context Researcher (RAG)**: A DuckDuckGo-powered retrieval agent that scours the internet for missing geographical and historical context before writing begins.
- **Taxonomy Mapper**: Aligns historical metadata with the live database categories and authors.
- **Synthesis Loop**: A strict Writer/Critic iterative refinement loop. Enforces formatting rules (no AI-speak, no em-dashes) and uses a deterministic `CriticEscalationChecker` to handle approvals.
- **Publisher**: The "fire-and-forget" final executioner. Pushes the approved JSON payload to the remote MCP server and explicitly commits the session state.

## 🛠️ Tech Stack
-   **Framework**: Google ADK (2026)
-   **LLM Engine**: Google Gemma 4 (gemma-4-26b-a4b-it for Vision, gemma-4-26b-a4b-it & gemma-4-31b-it for Synthesis/Critic) via `litellm`.
-   **Execution**: Python 3.13 with [uv](https://github.com/astral-sh/uv).
-   **Persistence**: Neon DB (Postgres) via ADK `DatabaseSessionService`.
-   **Serverless Infrastructure**: Render Web Service + Telegram Webhook.
-   **Integrations**: Hugging Face Hub, DuckDuckGo Search, Telegram Bot API, Custom MCP Client.

## 🚀 Installation & Usage

### 1. Setup
```bash
# Clone & Sync
git clone [https://github.com/Nwokike/Archives-Agent.git](https://github.com/Nwokike/Archives-Agent.git)
cd archives-agent
uv sync
```

### 2. Configure Datasets
To add new datasets in the future, simply update the dictionary in `agents/orchestrator/config.py`. The database and Telegram UI will adapt automatically.

### 3. Run the Production Suite
The app auto-detects its environment. It runs a Polling Bot locally, or a Webhook worker in production.
```bash
# Start the Telegram Bot + Dynamic Status Streaming
uv run python app.py
```

### 4. Debug with ADK Web UI
Visualize the agent trace, session states, and artifact generation locally:
```bash
# Start the ADK Dev Server
uv run adk web
```
*(Note: When running in ADK Web, the Orchestrator will automatically fall back to the default dataset defined in config.py).*

## 🧠 State Management
This pipeline utilizes ADK's Shared Session State to pass variables (`raw_metadata`, `vision_report`, `research_context`, `critic_status`) seamlessly between agents without prompt stuffing, ensuring maximum token efficiency and clean separation of concerns.
```
