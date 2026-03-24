# 🇳🇬 Igbo Archives Autonomous Ingestion System (HQ)

[![AI-Powered](https://img.shields.io/badge/AI-Autonomous%20Agents-blueviolet)](https://google.github.io/google-adk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An enterprise-grade, fully autonomous AI pipeline designed for **Daily Cultural Archiving**. This system preserves Igbo heritage by intelligently fetching colonial-era metadata from Hugging Face, performing deep visual analysis, and publishing validated entries to the [Igbo Archives](https://igboarchives.com.ng) platform.

## 🌟 Project Vision
Cultural heritage is often trapped in inaccessible digital silos. This project uses **Google ADK v1.26** and **Gemini 3.1/2.5** to create a resident AI archivist that:
1.  **Rescues History**: Automates the ingestion of thousands of historical images with human-grade accuracy.
2.  **Verifies Context**: Employs an 8-layer anti-hallucination protocol to ensure historical integrity.
3.  **Preserves Identity**: Grounded in live taxonomies of Igbo authors and categories at **igboarchives.com.ng**.

## 🏗️ Architecture: The Agent Hive
The system follows a **Supervised Hierarchical Pipeline** (Agent-as-a-Tool Hive):

- **Orchestrator (Gemini 3.1 Flash Lite)**: The conversational brain. Interprets natural language intents (e.g., "Archive the next available row") and manages the sequence.
- **Agent A (Fetcher)**: Deterministically fetches metadata and downloads images from the HF `maa-cambridge-south-eastern-nigeria` dataset.
- **Agent B (Vision Analyst)**: Performs quarantined visual-only analysis to ensure unbiased reporting (Gemini 2.5 Flash).
- **Agent C/D (Synthesis & Quality)**: Iterative Write/Critic loop to synthesize draft entries and validate them against platform taxonomies.
- **Agent E (Publisher)**: Final execution engine that commits the validated archive to the platform via MCP.

## 🛠️ Tech Stack
-   **Framework**: [Google ADK v1.26](https://google.github.io/google-adk/)
-   **Models**: Gemini 3.1 Flash Lite (Orchestration), Gemini 3 Flash (Synthesis), Gemini 2.5 Flash (Vision).
-   **Persistence**: [Neon DB](https://neon.tech) (Postgres) via `DatabaseSessionService`.
-   **Integrations**: Hugging Face Hub, Telegram Bot API, MCP (Model Context Protocol).

## 🚀 Installation & Local Development

### 1. Prerequisites
- [uv](https://github.com/astral-sh/uv)
- Python 3.13

### 2. Setup (UV)
```bash
# Clone & Sync
git clone https://github.com/Nwokike/Archives-Agent.git
cd archives-agent
uv sync

# Environment Variables
cp .env.example .env
# Edit .env with your Google AI Studio, Telegram, and Neon DB credentials.

# Start System
uv run python app.py
```

### 3. Usage
**Telegram Chat**: Start the bot and simply say **"Archive row 500"** or **"Today's archive"**.
**Local Web UI**: Use `uv run adk web app.py` for debugging and real-time trace inspection.

## 🛡️ Anti-Hallucination Protocol
- **Deterministic Row Access**: Uses static indexing for 100% repeatability.
- **Author Matcher**: Forces fuzzy-to-exact mapping against live web records.
- **Honest Null Protocol**: Strictly forbids LLM fabrication if data is missing.

---
© 2026. Released under the **MIT License**.
