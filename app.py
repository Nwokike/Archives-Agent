import os
import asyncio
import time
from dotenv import load_dotenv
from google_adk import SupervisorAgent, WorkflowAgent, DatabaseSessionService, AgentApp, Node
from agents.schema import PipelineState
from agents.fetcher import FetcherAgent
from agents.vision import VisionAgent
from agents.writer_critic import SynthesisLoop
from agents.publisher import PublisherAgent
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Load local .env
load_dotenv()

# --- The Pipeline Tool (Agent 3.2) ---
class ArchivePipeline(WorkflowAgent):
    """The nested sequence triggered by the Orchestrator."""
    nodes = [
        Node(FetcherAgent(), id="fetcher"),
        Node(VisionAgent(), id="vision"),
        Node(SynthesisLoop(), id="synthesis"),
        Node(PublisherAgent(), id="publisher")
    ]

# --- The Orchestrator (Root Agent 3.1) ---
class Orchestrator(SupervisorAgent):
    """Root Coordinator: Realizes conversational intent as pipeline triggers."""
    model = "gemini-3.1-flash-lite"
    tools = [ArchivePipeline().as_tool("execute_archive_pipeline")]

    system_prompt = """
    You are the Igbo Archives Orchestrator. 
    You manage a cultural archiving pipeline.
    
    CONVERSATIONAL FLOW:
    1. If the user says 'Archive the next one', 'Archive today', or similar, find the next index (current + 1) and call `execute_archive_pipeline(current_index=IDX)`.
    2. If they provide a specific index (e.g. 'Process 500'), call the tool with that index.
    3. You have access to the `PipelineState` which tracks the `current_index`.
    
    IMPORTANT: Provide brief, efficient updates in English.
    """

# --- Telegram Status Streamer ---
class TelegramStatusStreamer:
    def __init__(self, update: Update):
        self.update = update
        self.message = None
        self.last_update_time = 0.0
        self.status_map = {
            "fetcher": "[..] Fetching Data",
            "vision": "[..] Analyzing Image",
            "synthesis": "[..] Writing/Critiquing",
            "publisher": "[..] Publishing archive"
        }
        self.completed = set()

    async def start(self, initial_text="⚙️ Initializing Pipeline..."):
        self.message = await self.update.message.reply_text(initial_text)

    async def on_event(self, event):
        node_id = getattr(event, "node_id", None)
        if not node_id or node_id not in self.status_map: return
        if event.type == "node_finish": self.completed.add(node_id)
        if time.time() - self.last_update_time < 3 and event.type != "node_finish": return
        await self.refresh_ui()

    async def refresh_ui(self):
        text = "⚙️ Pipeline Progress:\n\n"
        icons = {
            "fetcher": "✅" if "fetcher" in self.completed else "⚙️",
            "vision": "👁️" if "vision" in self.completed else ".." if "fetcher" in self.completed else "",
            "synthesis": "⚖️" if "synthesis" in self.completed else ".." if "vision" in self.completed else "",
            "publisher": "🚀" if "publisher" in self.completed else ".." if "synthesis" in self.completed else ""
        }
        for node_id, label in self.status_map.items():
            icon = icons.get(node_id, "   ")
            text += f"{icon} {label}\n"
        if self.message:
            try: await self.message.edit_text(text)
            except: pass
            self.last_update_time = time.time()

# --- Telegram Bot Interface ---
async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pass all chat messages to the Orchestrator for conversational intent."""
    user_msg = update.message.text
    streamer = TelegramStatusStreamer(update)
    await streamer.start(f"🧐 Processing request: '{user_msg}'...")
    
    async for event in agent_app.run(user_msg):
        await streamer.on_event(event)

    await update.message.reply_text("🏁 Task Complete.")

# --- Initialization ---
neon_url = os.getenv("NEON_DATABASE_URL")
session_service = DatabaseSessionService(url=neon_url) if neon_url else None

agent_app = AgentApp(
    root_agent=Orchestrator(),
    session_service=session_service,
    memory_type=PipelineState
)

# Alias for ADK Web
app = agent_app

if __name__ == "__main__":
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if bot_token:
        print("🤖 Starting Telegram Bot...")
        tg_app = ApplicationBuilder().token(bot_token).build()
        tg_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_chat))
        tg_app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Igbo Archives HQ Online. Say 'Archive row 500' or 'Archive the next row'.")))
        print("🚀 System Online.")
        tg_app.run_polling()
    else:
        print("🚀 System Online (No Bot Token). Use 'adk web app.py' to test.")
