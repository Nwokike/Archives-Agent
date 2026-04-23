import sys
import os
import asyncio
import tempfile
import uuid
import re
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# --- Telegram Imports ---
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
from fastapi import FastAPI, Request
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

# --- Configuration Import ---
from agents.orchestrator.config import DATASETS, DEFAULT_DS_KEY

load_dotenv()

# --- Master Configuration ---
NEON_URL = os.getenv("NEON_DATABASE_URL")
if not NEON_URL:
    raise ValueError("NEON_DATABASE_URL required for autonomous persistence.")

if NEON_URL.startswith("postgresql://"):
    NEON_URL = NEON_URL.replace("postgresql://", "postgresql+psycopg://", 1)

session_service = DatabaseSessionService(db_url=NEON_URL)

# --- Global Index DB Setup (DYNAMIC PERSISTENCE) ---
engine = create_engine(NEON_URL)

def init_db():
    with engine.begin() as conn:
        # Table 1: Remembers which dataset you currently have selected
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS active_dataset (
                chat_id BIGINT PRIMARY KEY,
                dataset_key TEXT NOT NULL
            )
        """))
        # Table 2: Remembers the row index for EACH dataset independently
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dataset_indexes (
                chat_id BIGINT,
                dataset_key TEXT,
                current_index INTEGER NOT NULL,
                PRIMARY KEY (chat_id, dataset_key)
            )
        """))

async def get_active_ds_key(chat_id: int) -> str:
    def _get():
        with engine.connect() as conn:
            result = conn.execute(text("SELECT dataset_key FROM active_dataset WHERE chat_id = :c"), {"c": chat_id}).fetchone()
            return result[0] if result else DEFAULT_DS_KEY
    return await asyncio.to_thread(_get)

async def set_active_ds_key(chat_id: int, ds_key: str):
    def _set():
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO active_dataset (chat_id, dataset_key)
                VALUES (:c, :d)
                ON CONFLICT (chat_id) DO UPDATE SET dataset_key = EXCLUDED.dataset_key
            """), {"c": chat_id, "d": ds_key})
    await asyncio.to_thread(_set)

async def get_persistent_index(chat_id: int, ds_key: str) -> int:
    def _get():
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_index FROM dataset_indexes WHERE chat_id = :c AND dataset_key = :d"), 
                                  {"c": chat_id, "d": ds_key}).fetchone()
            return result[0] if result else 0
    return await asyncio.to_thread(_get)

async def set_persistent_index(chat_id: int, ds_key: str, new_index: int):
    def _set():
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO dataset_indexes (chat_id, dataset_key, current_index)
                VALUES (:c, :d, :i)
                ON CONFLICT (chat_id, dataset_key) DO UPDATE SET current_index = EXCLUDED.current_index
            """), {"c": chat_id, "d": ds_key, "i": new_index})
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

# --- State Management ---
active_sessions = {}

# --- TELEGRAM UI CONTROLLERS ---
async def send_menu(chat_id: int, bot: Bot):
    keyboard = []
    
    # 1. Action Button
    keyboard.append([InlineKeyboardButton("🚀 Clear Memory & Process Next Row", callback_data="cmd_new")])
    
    # 2. Dynamic Dataset Buttons
    for key, ds_path in DATASETS.items():
        # Clean up the name for the button display
        display_name = ds_path.split('/')[-1].replace("-", " ").title()
        keyboard.append([InlineKeyboardButton(f"📁 {display_name}", callback_data=f"setds_{key}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Fetch current state to show in the menu
    active_key = await get_active_ds_key(chat_id)
    current_idx = await get_persistent_index(chat_id, active_key)
    active_name = DATASETS.get(active_key, DATASETS[DEFAULT_DS_KEY]).split('/')[-1]
    
    text = f"🎛 **Archives Control Panel**\n\n**Active Target:** `{active_name}`\n**Next Row:** `{current_idx}`\n\nSelect a dataset below or start processing:"
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode="Markdown")

async def handle_callback(update: Update, bot: Bot):
    query = update.callback_query
    chat_id = query.message.chat.id
    await query.answer() 
    
    data = query.data
    
    if data == "cmd_new":
        await process_new_command(chat_id, bot)
        return
        
    if data.startswith("setds_"):
        new_ds_key = data.split("_")[1]
        await set_active_ds_key(chat_id, new_ds_key)
        
        current_idx = await get_persistent_index(chat_id, new_ds_key)
        ds_name = DATASETS.get(new_ds_key, DATASETS[DEFAULT_DS_KEY]).split('/')[-1]
        
        await bot.send_message(
            chat_id=chat_id, 
            text=f"✅ **Dataset Locked:** `{ds_name}`\n**Resuming from Row:** `{current_idx}`\n\nClick 'Clear Memory & Process Next Row' in the menu or send /new to begin.",
            parse_mode="Markdown"
        )

# --- EXECUTION PIPELINE ---
async def process_new_command(chat_id: int, bot: Bot):
    """Handles memory clearing for both the /new command and the inline button."""
    active_ds_key = await get_active_ds_key(chat_id)
    current_idx = await get_persistent_index(chat_id, active_ds_key)
    ds_name = DATASETS.get(active_ds_key, DATASETS[DEFAULT_DS_KEY]).split('/')[-1]
    
    active_sessions[chat_id] = f"archive_run_{uuid.uuid4().hex[:8]}"
    await bot.send_message(
        chat_id=chat_id, 
        text=f"🔄 Memory cleared. Securely processing **Row {current_idx}** of `{ds_name}`...",
        parse_mode="Markdown"
    )
    
    # Simulate a blank text trigger to start the pipeline
    class MockMessage:
        def __init__(self):
            self.text = ""
            self.chat = type('obj', (object,), {'id': chat_id})
    class MockUpdate:
        def __init__(self, chat_id):
            self.effective_chat = type('obj', (object,), {'id': chat_id})
            self.message = MockMessage()
            self.callback_query = None
            
    await run_pipeline(MockUpdate(chat_id), bot)


async def run_pipeline(update: Update, bot: Bot):
    chat_id = update.effective_chat.id
    msg_text = update.message.text.strip() if update.message and update.message.text else ""
    
    if msg_text == "/new":
        await process_new_command(chat_id, bot)
        return

    # 1. Fetch exact state
    active_ds_key = await get_active_ds_key(chat_id)
    active_dataset_path = DATASETS.get(active_ds_key, DATASETS[DEFAULT_DS_KEY])
    
    manual_row_match = re.search(r'(?:row|index)\s+(\d+)', msg_text.lower())
    if manual_row_match:
        await set_persistent_index(chat_id, active_ds_key, int(manual_row_match.group(1)))
        
    current_persistent_index = await get_persistent_index(chat_id, active_ds_key)
    
    if chat_id not in active_sessions:
        active_sessions[chat_id] = f"archive_run_{uuid.uuid4().hex[:8]}"
    current_session_id = active_sessions[chat_id]
    
    # 2. INJECT DYNAMIC CONTEXT
    system_directive = f"\n\n[SYSTEM DIRECTIVE: The exact dataset you MUST fetch is '{active_dataset_path}'. The exact row index is {current_persistent_index}. Override any defaults.]"
    injected_msg_text = msg_text + system_directive
    
    msg_content = types.Content(role="user", parts=[types.Part.from_text(text=injected_msg_text)])
    
    # Explicitly AWAIT the session check and creation, using str(chat_id) for isolated sessions
    try:
        current_session = await session_service.get_session(app_name="igbo-archives-agent-hq", user_id=str(chat_id), session_id=current_session_id)
        if not current_session:
            await session_service.create_session(app_name="igbo-archives-agent-hq", user_id=str(chat_id), session_id=current_session_id)
    except Exception:
        await session_service.create_session(app_name="igbo-archives-agent-hq", user_id=str(chat_id), session_id=current_session_id)

    try:
        async for event in runner.run_async(user_id=str(chat_id), session_id=current_session_id, new_message=msg_content):
            author = event.author
            
            if author and author not in ["user", "system"]:
                event_text = ""
                if event.content and event.content.parts:
                    event_text = "".join([p.text for p in event.content.parts if hasattr(p, 'text') and p.text]).strip()

                if event_text:
                    await bot.send_message(chat_id=chat_id, text=f"{author.upper()}:\n{event_text}")
                    
                    if author == "publisher" and "successfully published" in event_text.lower():
                        new_index = current_persistent_index + 1
                        await set_persistent_index(chat_id, active_ds_key, new_index)
                        await bot.send_message(
                            chat_id=chat_id,
                            text=f"✅ Row completed! Target Index permanently advanced to {new_index} for this dataset.\nOpen /menu to process the next row."
                        )

        # Cleanup image file
        try:
            current_session = await session_service.get_session(app_name="igbo-archives-agent-hq", user_id=str(chat_id), session_id=current_session_id)
            if current_session:
                image_to_cleanup = current_session.state.get("image_path")
                if image_to_cleanup and os.path.exists(image_to_cleanup):
                    os.remove(image_to_cleanup)
        except Exception:
            pass

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        if len(error_msg) > 4000:
            error_msg = error_msg[:4000] + "\n...[Error Truncated]"
        await bot.send_message(chat_id, error_msg)


# --- Webhook Mode (Render Web Service) ---
app = FastAPI()
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
tg_bot = Bot(token=bot_token) if bot_token else None

@app.post("/webhook")
async def telegram_webhook(request: Request):
    payload = await request.json()
    update = Update.de_json(payload, tg_bot)
    
    if update.callback_query:
        asyncio.create_task(handle_callback(update, tg_bot))
    elif update.message and update.message.text:
        if update.message.text.startswith("/menu") or update.message.text.startswith("/start"):
            asyncio.create_task(send_menu(update.effective_chat.id, tg_bot))
        else:
            asyncio.create_task(run_pipeline(update, tg_bot))
            
    return {"status": "ok"}

@app.get("/")
def health():
    return {"status": "Raw Archiving Hive is ACTIVE on Render", "mode": "Webhook"}

# --- Polling Mode (Local Dev) ---
async def handle_polling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text if update.message else ""
    if text.startswith("/menu") or text.startswith("/start"):
        await send_menu(update.effective_chat.id, context.bot)
    else:
        await run_pipeline(update, context.bot)

async def handle_polling_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_callback(update, context.bot)

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
            
            tg_app.add_handler(CommandHandler(["start", "menu"], handle_polling))
            tg_app.add_handler(CallbackQueryHandler(handle_polling_callback))
            tg_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_polling))
            
            tg_app.run_polling()
        else:
            print("CRITICAL: TELEGRAM_BOT_TOKEN not found.")
