# 🇳🇬 Igbo Archives Autonomous Ingestion System (HQ)

[![AI-Powered](https://img.shields.io/badge/AI-Autonomous%20Agents-blueviolet)](https://google.github.io/google-adk/)
[![Project-Status](https://img.shields.io/badge/Status-Alpha-orange)]()
[![License](https://img.shields.io/badge/License-Proprietary-red)](https://kiri.ng/about)

An enterprise-grade, fully autonomous AI pipeline designed for **Daily Cultural Archiving**. This system preserves Igbo heritage by intelligently fetching colonial-era metadata from Hugging Face, performing visual analysis, and publishing validated entries to the [Igbo Archives](https://igbo-archives.org) platform.

## 🌟 Project Vision
Cultural heritage is often trapped in inaccessible digital silos. This project uses **Google ADK v1.26** and **Gemini 3.1/2.5** to create a resident AI archivist that:
1.  **Rescues History**: Automates the ingestion of thousands of historical images.
2.  **Verifies Context**: Uses an 8-layer anti-hallucination protocol to ensure accuracy.
3.  **Preserves Identity**: Grounded in live taxonomies of Igbo authors and categories.

## 🏗️ Architecture: The Agent Hive
The system follows a **Supervised Hierarchical Pipeline** (Agent-as-a-Tool Hive):

- **Orchestrator (Gemini 3.1 Flash Lite)**: The conversational brain. Receives intents (e.g., "Archive row 500") and manages the overall workflow.
- **Agent A: The Fetcher**: Deterministically fetches metadata and downloads images from the HF `maa-cambridge-south-eastern-nigeria` dataset.
- **Agent B: The Vision Analyst (Quarantined)**: Performs visual-only analysis to ensure unbiased reporting (Gemini 2.5 Flash).
- **Agent C/D: The Writer & Critic (Refinement Loop)**: Synthesizes draft entries and validates them against MCP ground truth (Max 3 iterations).
- **Agent E: The Publisher**: Commits the final, validated record to the database via the Igbo Archives MCP server.

## 🛠️ Tech Stack
-   **Core Framework**: [Google ADK v1.26](https://google.github.io/google-adk/)
-   **Models**: Gemini 3.1 Flash Lite (Orchestration), Gemini 3 Flash (Synthesis), Gemini 2.5 Flash (Vision).
-   **Persistence**: [Neon DB](https://neon.tech) (PostgreSQL) via `DatabaseSessionService`.
-   **Integrations**: Hugging Face Hub API, Telegram Bot API.

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- `uv` (Recommended) or `pip`
- Neon DB Project
- Telegram Bot Token ([BotFather](https://t.me/botfather))

### 2. Setup
```bash
# 1. Clone & Setup
git clone https://github.com/Nwokike/Archives-Agent.git
cd archives-agent
uv venv
source .venv/bin/activate # or .venv/Scripts/activate on Windows

# 2. Environment Variables
cp .env.example .env
# Edit .env with your Google AI Studio, Telegram, and Neon DB credentials.

# 3. Install dependencies
uv pip install -r requirements.txt
```

### 3. Usage
**Local Testing (ADK Web)**:
```bash
uv run adk web app.py
```
**Telegram Interface**:
```bash
uv run python app.py
```
*Send `/archive 500` or just "Archive the next available row" to the bot.*

## 🛡️ Anti-Hallucination Protocol
- **Deterministic Row Access**: Uses `data.jsonl` line indexing for 100% reliability.
- **Author Matcher**: Forces fuzzy-to-exact mapping against live website author records.
- **Honest Null Protocol**: Strictly forbids LLM fabrication if data is missing.

---
© 2026 [Kiri Research Labs](https://kiri.ng). Proprietary. Efficiency-focused AI for cultural preservation.
