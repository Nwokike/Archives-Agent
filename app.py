import sys
import os
import asyncio
import time
import tempfile
from datetime import datetime
from dotenv import load_dotenv

# 1. OS-Agnostic Cache Path
HF_CACHE_DIR = os.path.join(tempfile.gettempdir(), "hf_cache")
os.environ["HF_HUB_CACHE"] = HF_CACHE_DIR

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from fastapi import FastAPI, Request
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from agents.orchestrator.agent import orchestrator
from agents.schema import get_initial_state
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

from google.genai import types
from google.adk.events.event import Event

load_dotenv()

# --- Master Configuration ---
NEON_URL = os.getenv("NEON_DATABASE_URL")
if not NEON_URL:
    raise ValueError("NEON_DATABASE_URL required for autonomous persistence.")

if NEON_URL.startswith("postgresql://"):
    NEON_URL = NEON_URL.replace("postgresql://", "postgresql+psycopg://", 1)

session_service = DatabaseSessionService(db_url=NEON_URL)

runner = Runner(
    app_name="igbo-archives-agent-hq",
    agent=orchestrator,
    session_service=session_service
)

STATIC_SESSION_ID = "global_archive_tracker"
DATASET_ID = "nwokikeonyeka/maa-cambridge-south-eastern-nigeria"

# --- ADK Event Bubbling Fix (UI Callback Scope Bug) ---
async def before_agent_callback(ctx):
    ctx.state["active_agent"] = ctx.agent_name
    # Modifying state forces ADK to bubble an Event to the runner root!
    return None

# 2. Fixed Imports
from agents.fetcher.agent import data_fetcher, taxonomy_mapper
from agents.vision.agent import vision
from agents.synthesis.agent import writer, critic
from agents.publisher.agent import publisher

# 3. Protected Callbacks: Only apply to agents that don't already have one
for ag in [data_fetcher, vision, writer, critic, publisher]:
    ag.before_agent_callback = before_agent_callback

# 4. Corrected Status Map Keys
STATUS_MAP = {
    "data_fetcher": ("⚙️ Fetching Metadata", "✅ Data Fetched"),
    "taxonomy_mapper": ("🗺️ Mapping Taxonomy", "✅ Taxonomy Mapped"),
    "vision_analyst": ("👁️ Visual Analysis", "🖼️ Visual Report Done"),
    "synthesis_writer": ("✍️ Drafting Record", "📄 Draft Written"),
    "historical_validator": ("⚖️ Validating Draft", "⚖️ Record Approved"),
    "publisher": ("🚀 Final Publishing", "✨ Archive Published!")
}

async def update_telegram_status(chat_id: int, msg_id: int, state: dict, bot: Bot):
    last_ui_update = state.get("last_ui_update", 0)
    current_time = time.time()
    if current_time - last_ui_update < 2: return

    lines = []
    active = state.get("active_agent", "")
    completed = state.get("completed_agents", [])
    
    for agent, (in_prog, done) in STATUS_MAP.items():
        if agent in completed: lines.append(f"[✅] {done}")
        elif agent == active: lines.append(f"[..] {in_prog}...")
        else: lines.append(f"[  ] {in_prog}")
            
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=f"⚙️ **System: {state.get('dataset_id', 'HF-Archive')}**\nStatus: Processing Row {state.get('current_index', 0)}\n\n" + "\n".join(lines),
            parse_mode="Markdown"
        )
        state["last_ui_update"] = current_time
    except: pass

async def run_pipeline(update: Update, bot: Bot):
    chat_id = update.effective_chat.id
    status_msg = await bot.send_message(chat_id, "📡 *Archives Hive Activated*\n_Connecting to agents..._", parse_mode="Markdown")

    # For final reporting/cleanup
    final_payload = {}
    image_to_cleanup = None
    full_output = ""
    
    # Dynamic Streaming State
    hive_steps = [] # List of dicts: {"agent": str, "status": "working"|"done", "detail": str}
    last_update_time = 0
    
    # --- Fix 'role' error by wrapping message ---
    msg_content = types.Content(role="user", parts=[types.Part(text=update.message.text)])
    
    print(f"DEBUG: Starting Runner for {DATASET_ID} with message: {update.message.text}")
    
    try:
        from google.adk.utils._debug_output import print_event
        async for event in runner.run_async(user_id=DATASET_ID, session_id=STATIC_SESSION_ID, new_message=msg_content):
            # Console logs (the "Everything on Logs" part)
            print_event(event)

            author = event.author
            if author and author not in ["user", "system"]:
                # 1. Update/Add Hive Step
                current_step = None
                if hive_steps and hive_steps[-1]["agent"] == author:
                    current_step = hive_steps[-1]
                else:
                    # New agent started. Mark previous as done.
                    if hive_steps: hive_steps[-1]["status"] = "done"
                    current_step = {"agent": author, "status": "working", "detail": "Starting..."}
                    hive_steps.append(current_step)
                
                # 2. Extract Text Content Safely
                event_text = ""
                if event.content and event.content.parts:
                    event_text = "".join([p.text for p in event.content.parts if p.text]).strip()

                func_calls = event.get_function_calls()
                func_responses = event.get_function_responses()
                
                # 3. Update Step Details (Log-style)
                if func_calls:
                    tools = ", ".join([fc.name for fc in func_calls])
                    current_step["detail"] = f"🛠️ Calling: `{tools}`"
                elif func_responses:
                    current_step["detail"] = "📥 Data Received"
                elif event_text:
                    if author == "orchestrator":
                        full_output += event_text
                    snippet = event_text[:45].replace("\n", " ")
                    current_step["detail"] = f"💭 {snippet}..."
                
                if event.is_final_response():
                    current_step["status"] = "done"
                    if "detail" not in current_step or current_step["detail"] == "Starting...":
                        current_step["detail"] = "✅ Complete"

                # 4. Format & Throttled Edit
                now = time.time()
                if now - last_update_time >= 1.2:
                    display_lines = ["📡 *Archives Hive Activity*", ""]
                    for step in hive_steps[-5:]: # Show last 5 steps for focus
                        icon = "⚡" if step["status"] == "working" else "🔵"
                        name = step["agent"].replace("_", " ").upper()
                        display_lines.append(f"{icon} *{name}*\n└ {step['detail']}")
                    
                    try:
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=status_msg.message_id,
                            text="\n".join(display_lines),
                            parse_mode="Markdown"
                        )
                        last_update_time = now
                    except: pass

            # Persistence tracking
            current_session = await session_service.get_session(
                app_name="igbo-archives-agent-hq", 
                user_id=DATASET_ID, 
                session_id=STATIC_SESSION_ID
            )
            image_to_cleanup = current_session.state.get("image_path")
            final_payload = current_session.state.get("draft_payload", {})

    except Exception as e:
        await bot.send_message(chat_id, f"⚠️ **Hive Error:** {str(e)}")
    finally:
        # Final cleanup: Replace thinking with result
        try: await bot.delete_message(chat_id, status_msg.message_id)
        except: pass
        
        if final_payload:
            title = final_payload.get("title", "Untitled")
            category = final_payload.get("category_name", "General")
            slug = final_payload.get("slug", "pending")
            link = f"https://igboarchives.ng/archives/{slug}/"
            
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ **Archiving Complete**\n\n**Title**: {title}\n**Category**: {category}\n\n🔗 [View on Platform]({link})",
                parse_mode="Markdown"
            )
        elif full_output:
            # If orchestrator sent a direct chat response
            await bot.send_message(chat_id, full_output)
        else:
            await bot.send_message(chat_id, "🏁 **Pipeline Finished** (No records processed)")

        # ADK persistent memory is now managed natively inside the Publisher agent tools.
        # This prevents double-incrementing when multiple agents touch the state.

        if image_to_cleanup and os.path.exists(image_to_cleanup):
            try: os.remove(image_to_cleanup)
            except: pass

# --- Webhook Mode (Cloud Run) ---
app = FastAPI()
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
tg_bot = Bot(token=bot_token) if bot_token else None

@app.post("/webhook")
async def telegram_webhook(request: Request):
    import json
    payload = await request.json()
    
    if os.getenv("K_SERVICE"):
        # Cloud Run: push to Cloud Tasks
        from google.cloud import tasks_v2
        client = tasks_v2.CloudTasksClient()
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "project-id")
        location = os.getenv("GCP_LOCATION", "us-central1")
        queue = os.getenv("GCP_QUEUE", "archives-queue")
        url = os.getenv("WORKER_URL", "https://your-cloud-run-url/worker")
        
        parent = client.queue_path(project, location, queue)
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-type": "application/json"},
                "body": json.dumps(payload).encode()
            }
        }
        try:
            client.create_task(request={"parent": parent, "task": task})
        except Exception as e:
            print(f"Error publishing to Cloud Tasks: {e}")
            update = Update.de_json(payload, tg_bot)
            if update.message and update.message.text:
                asyncio.create_task(run_pipeline(update, tg_bot))
    else:
        update = Update.de_json(payload, tg_bot)
        if update.message and update.message.text:
            asyncio.create_task(run_pipeline(update, tg_bot))
    return {"status": "ok"}

@app.post("/worker")
async def telegram_worker(request: Request):
    payload = await request.json()
    update = Update.de_json(payload, tg_bot)
    if update.message and update.message.text:
        await run_pipeline(update, tg_bot)
    return {"status": "completed"}

@app.get("/")
def health():
    return {"status": "Archiving Hive is ACTIVE", "mode": "Webhook"}

# --- Polling Mode (Local Dev) ---
async def handle_polling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await run_pipeline(update, context.bot)

if __name__ == "__main__":
    if os.getenv("K_SERVICE") or os.getenv("TELEGRAM_WEBHOOK_URL"):
        # PRODUCTION MODE
        import uvicorn
        port = int(os.environ.get("PORT", 8080))
        print(f"Starting server on port {port} (Webhook Mode)")
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        # LOCAL MODE
        if bot_token:
            from telegram.request import HTTPXRequest
            print("Starting Telegram Bot (Polling Mode) for local dev...")
            # Increased timeouts for spotty network (e.g. Enugu, Nigeria)
            request = HTTPXRequest(connect_timeout=30, read_timeout=30)
            tg_app = ApplicationBuilder().token(bot_token).request(request).build()
            tg_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_polling))
            tg_app.run_polling()
        else:
            print("CRITICAL: TELEGRAM_BOT_TOKEN not found.")
