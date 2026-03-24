import os
from dotenv import load_dotenv
from google_adk import DatabaseSessionService, AgentApp
from agents.schema import PipelineState
from agents.orchestrator.agent import Orchestrator
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, CommandHandler, ContextTypes

load_dotenv()

# --- Initialization ---
neon_url = os.getenv("NEON_DATABASE_URL")
session_service = DatabaseSessionService(url=neon_url) if neon_url else None

agent_app = AgentApp(
    root_agent=Orchestrator(),
    session_service=session_service,
    memory_type=PipelineState
)

app = agent_app

# --- Telegram Logic ---
async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message.text
    async for event in agent_app.run(user_msg):
        # We can add the streamer here if needed, keeping it simple for now
        pass
    await update.message.reply_text("🏁 Task Complete.")

if __name__ == "__main__":
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if bot_token:
        tg_app = ApplicationBuilder().token(bot_token).build()
        tg_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_chat))
        tg_app.run_polling()
