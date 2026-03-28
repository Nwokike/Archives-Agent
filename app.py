import sys
import os
import asyncio
import tempfile
from dotenv import load_dotenv

# 1. OS-Agnostic Cache Path
HF_CACHE_DIR = os.path.join(tempfile.gettempdir(), "hf_cache")
os.environ["HF_HUB_CACHE"] = HF_CACHE_DIR

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
from fastapi import FastAPI, Request
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from google.genai import types

load_dotenv()

# --- Master Configuration ---
NEON_URL = os.getenv("NEON_DATABASE_URL")
if not NEON_URL:
    raise ValueError("NEON_DATABASE_URL required for autonomous persistence.")

if NEON_URL.startswith("postgresql://"):
    NEON_URL = NEON_URL.replace("postgresql://", "postgresql+psycopg://", 1)

session_service = DatabaseSessionService(db_url=NEON_URL)

# --- Agent Imports ---
from agents.orchestrator.agent import orchestrator, archive_pipeline
from agents.orchestrator.research.agent import researcher
from agents.orchestrator.taxonomy.agent import taxonomy_mapper
from agents.orchestrator.synthesis.agent import synthesis_loop
from agents.orchestrator.publisher.agent import publisher

runner = Runner(
    app_name="igbo-archives-agent-hq",
    agent=orchestrator,
    session_service=session_service
)

STATIC_SESSION_ID = "global_archive_tracker"
DATASET_ID = "nwokikeonyeka/maa-cambridge-south-eastern-nigeria"

# --- Main Pipeline Execution (RAW MODE) ---
async def run_pipeline(update: Update, bot: Bot):
    chat_id = update.effective_chat.id
    msg_content = types.Content(role="user", parts=[types.Part.from_text(text=update.message.text)])
    
    # 🚨 FIX: Explicitly create the session in the DB if it doesn't exist
    try:
        session_service.get_session(
            app_name="igbo-archives-agent-hq", 
            user_id=DATASET_ID, 
            session_id=STATIC_SESSION_ID
        )
    except Exception:
        # If it throws an error (Session Not Found), we create it so the Runner doesn't crash
        session_service.create_session(
            app_name="igbo-archives-agent-hq", 
            user_id=DATASET_ID, 
            session_id=STATIC_SESSION_ID
        )

    try:
        # Execute the pipeline
        async for event in runner.run_async(user_id=DATASET_ID, session_id=STATIC_SESSION_ID, new_message=msg_content):
            author = event.author
            
            # We only care about agents (not user input or background system pings)
            if author and author not in ["user", "system"]:
                
                # Extract text
                event_text = ""
                if event.content and event.content.parts:
                    event_text = "".join([p.text for p in event.content.parts if hasattr(p, 'text') and p.text]).strip()

                # If the agent actually spoke, send it directly to Telegram
                if event_text:
                    await bot.send_message(
                        chat_id=chat_id, 
                        text=f"**{author.upper()}**:\n{event_text}", 
                        parse_mode="Markdown"
                    )

        # Cleanup image if it exists in state after the run
        try:
            current_session = session_service.get_session(
                app_name="igbo-archives-agent-hq", 
                user_id=DATASET_ID, 
                session_id=STATIC_SESSION_ID
            )
            image_to_cleanup = current_session.state.get("image_path")
            if image_to_cleanup and os.path.exists(image_to_cleanup):
                os.remove(image_to_cleanup)
        except Exception:
            pass

    except Exception as e:
        # Only send actual unhandled Python/API errors
        await bot.send_message(chat_id, f"Error: {str(e)}")


# --- Webhook Mode (Render Web Service) ---
app = FastAPI()
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
tg_bot = Bot(token=bot_token) if bot_token else None

@app.post("/webhook")
async def telegram_webhook(request: Request):
    payload = await request.json()
    update = Update.de_json(payload, tg_bot)
    
    if update.message and update.message.text:
        asyncio.create_task(run_pipeline(update, tg_bot))
            
    return {"status": "ok"}

@app.get("/")
def health():
    return {"status": "Raw Archiving Hive is ACTIVE on Render", "mode": "Webhook"}

# --- Polling Mode (Local Dev) ---
async def handle_polling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await run_pipeline(update, context.bot)

if __name__ == "__main__":
    if os.getenv("RENDER") or os.getenv("TELEGRAM_WEBHOOK_URL"):
        import uvicorn
        port = int(os.environ.get("PORT", 8080))
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        if bot_token:
            from telegram.request import HTTPXRequest
            print("Starting Telegram Bot (Polling Mode)...")
            request = HTTPXRequest(connect_timeout=30, read_timeout=30)
            tg_app = ApplicationBuilder().token(bot_token).request(request).build()
            tg_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_polling))
            tg_app.run_polling()
        else:
            print("CRITICAL: TELEGRAM_BOT_TOKEN not found.")