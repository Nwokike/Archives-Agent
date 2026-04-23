import sys
import os
import asyncio
import tempfile
import uuid
import re
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

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

# --- Global Index DB Setup (TRUE PERSISTENCE) ---
engine = create_engine(NEON_URL)

def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bot_index_tracker (
                chat_id BIGINT PRIMARY KEY,
                current_index INTEGER NOT NULL
            )
        """))

async def get_persistent_index(chat_id: int) -> int:
    def _get():
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_index FROM bot_index_tracker WHERE chat_id = :c"), {"c": chat_id}).fetchone()
            return result[0] if result else 0
    return await asyncio.to_thread(_get)

async def set_persistent_index(chat_id: int, new_index: int):
    def _set():
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO bot_index_tracker (chat_id, current_index)
                VALUES (:c, :i)
                ON CONFLICT (chat_id) DO UPDATE SET current_index = EXCLUDED.current_index
            """), {"c": chat_id, "i": new_index})
    await asyncio.to_thread(_set)

init_db()

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

DATASET_ID = os.getenv("TARGET_DATASET", "nwokikeonyeka/maa-cambridge-south-eastern-nigeria")

# --- State Management ---
active_sessions = {}

# --- Main Pipeline Execution (RAW MODE) ---
async def run_pipeline(update: Update, bot: Bot):
    chat_id = update.effective_chat.id
    msg_text = update.message.text.strip() if update.message.text else ""
    
    # 1. Check if user manually asked for a specific row (e.g. "Process row 5")
    manual_row_match = re.search(r'(?:row|index)\s+(\d+)', msg_text.lower())
    if manual_row_match:
        await set_persistent_index(chat_id, int(manual_row_match.group(1)))
        
    # Read the absolute truth from the Neon Database
    current_persistent_index = await get_persistent_index(chat_id)
    
    # Handle the /new command
    if msg_text.startswith("/new"):
        active_sessions[chat_id] = f"archive_run_{uuid.uuid4().hex[:8]}"
        await bot.send_message(
            chat_id=chat_id, 
            text=f"🔄 Memory cleared. The next run will securely process Row {current_persistent_index} from the database."
        )
        return

    # Ensure the user has an active session ID
    if chat_id not in active_sessions:
        active_sessions[chat_id] = f"archive_run_{uuid.uuid4().hex[:8]}"
    
    current_session_id = active_sessions[chat_id]
    
    # 2. Silently inject the Database Target Index into the user's prompt
    system_directive = f"\n\n[SYSTEM DIRECTIVE: The exact row index you MUST fetch for this session is {current_persistent_index}. Override any defaults.]"
    injected_msg_text = msg_text + system_directive
    
    msg_content = types.Content(role="user", parts=[types.Part.from_text(text=injected_msg_text)])
    
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
        await session_service.create_session(
            app_name="igbo-archives-agent-hq", 
            user_id=DATASET_ID, 
            session_id=current_session_id
        )

    try:
        # Execute the pipeline using the dynamic session ID
        async for event in runner.run_async(user_id=DATASET_ID, session_id=current_session_id, new_message=msg_content):
            author = event.author
            
            if author and author not in ["user", "system"]:
                event_text = ""
                if event.content and event.content.parts:
                    event_text = "".join([p.text for p in event.content.parts if hasattr(p, 'text') and p.text]).strip()

                if event_text:
                    await bot.send_message(
                        chat_id=chat_id, 
                        text=f"{author.upper()}:\n{event_text}"
                    )
                    
                    # 3. Auto-advance the index in the NEON DATABASE when Publisher completes
                    if author == "publisher" and "successfully published" in event_text.lower():
                        new_index = await get_persistent_index(chat_id) + 1
                        await set_persistent_index(chat_id, new_index)
                        await bot.send_message(
                            chat_id=chat_id,
                            text=f"✅ Row completed! Target Index permanently advanced to {new_index} in the Database.\nSend /new to clear memory before starting the next row."
                        )

        # Cleanup image file
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
        error_msg = f"Error: {str(e)}"
        if len(error_msg) > 4000:
            error_msg = error_msg[:4000] + "\n...[Error Truncated due to length]"
        await bot.send_message(chat_id, error_msg)


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
            
            tg_app.add_handler(CommandHandler("new", handle_polling))
            tg_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_polling))
            
            tg_app.run_polling()
        else:
            print("CRITICAL: TELEGRAM_BOT_TOKEN not found.")
