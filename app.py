import sys
import os
import asyncio
import tempfile
import uuid
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
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
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

DATASET_ID = "nwokikeonyeka/maa-cambridge-south-eastern-nigeria"

# --- State Management ---
# Maps a user's Telegram chat_id to their active dynamic session ID
active_sessions = {}

# --- Main Pipeline Execution (RAW MODE) ---
async def run_pipeline(update: Update, bot: Bot):
    chat_id = update.effective_chat.id
    msg_text = update.message.text.strip() if update.message.text else ""
    
    # Handle the /new command directly in the pipeline to support Webhook mode easily
    if msg_text.startswith("/new"):
        active_sessions[chat_id] = f"archive_run_{uuid.uuid4().hex[:8]}"
        await bot.send_message(
            chat_id=chat_id, 
            text="🔄 Memory cleared. Ready for a new archive record."
        )
        return

    # Ensure the user has an active session ID
    if chat_id not in active_sessions:
        active_sessions[chat_id] = f"archive_run_{uuid.uuid4().hex[:8]}"
    
    current_session_id = active_sessions[chat_id]
    
    msg_content = types.Content(role="user", parts=[types.Part.from_text(text=msg_text)])
    
    # Explicitly AWAIT the session check and creation
    try:
        current_session = await session_service.get_session(
            app_name="igbo-archives-agent-hq", 
            user_id=DATASET_ID, 
            session_id=current_session_id
        )
        if not current_session:
            await session_service.create_session(
                app_name="igbo-archives-agent-hq", 
                user_id=DATASET_ID, 
                session_id=current_session_id
            )
    except Exception:
        # Fallback if the database throws a hard error instead of returning None
        await session_service.create_session(
            app_name="igbo-archives-agent-hq", 
            user_id=DATASET_ID, 
            session_id=current_session_id
        )

    try:
        # Execute the pipeline using the dynamic session ID
        async for event in runner.run_async(user_id=DATASET_ID, session_id=current_session_id, new_message=msg_content):
            author = event.author
            
            # We only care about agents (not user input or background system pings)
            if author and author not in ["user", "system"]:
                
                # Extract text
                event_text = ""
                if event.content and event.content.parts:
                    event_text = "".join([p.text for p in event.content.parts if hasattr(p, 'text') and p.text]).strip()

                # If the agent actually spoke, send it directly to Telegram
                if event_text:
                    # 🚨 FIX: Markdown formatting completely removed to prevent Telegram crashes
                    await bot.send_message(
                        chat_id=chat_id, 
                        text=f"{author.upper()}:\n{event_text}"
                    )

        # AWAIT the get_session call for cleanup
        try:
            current_session = await session_service.get_session(
                app_name="igbo-archives-agent-hq", 
                user_id=DATASET_ID, 
                session_id=current_session_id
            )
            if current_session:
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
    
    # Render webhooks will catch /new here because we check update.message.text
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
            
            # Register command handler and text handler for polling
            tg_app.add_handler(CommandHandler("new", handle_polling))
            tg_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_polling))
            
            tg_app.run_polling()
        else:
            print("CRITICAL: TELEGRAM_BOT_TOKEN not found.")
