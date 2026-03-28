import sys
import os
import asyncio
import time
import tempfile
import json
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
from agents.orchestrator.agent import orchestrator
from agents.orchestrator.fetcher.agent import data_fetcher
from agents.orchestrator.taxonomy.agent import taxonomy_mapper
from agents.orchestrator.vision.agent import execute_vision_analysis 
from agents.orchestrator.synthesis.agent import writer, critic
from agents.orchestrator.publisher.agent import publisher

# Safely import the new researcher agent
try:
    from agents.orchestrator.research.agent import researcher
    has_researcher = True
except ImportError:
    has_researcher = False

runner = Runner(
    app_name="igbo-archives-agent-hq",
    agent=orchestrator,
    session_service=session_service
)

STATIC_SESSION_ID = "global_archive_tracker"
DATASET_ID = "nwokikeonyeka/maa-cambridge-south-eastern-nigeria"

# --- ADK Event Bubbling Fix ---
async def before_agent_callback(ctx):
    ctx.state["active_agent"] = ctx.agent_name
    return None

# Protected Callbacks: Dynamically includes researcher if it exists
agent_list = [data_fetcher, taxonomy_mapper, writer, critic, publisher]
if has_researcher:
    agent_list.append(researcher)

for ag in agent_list:
    if getattr(ag, "before_agent_callback", None) is None:
        ag.before_agent_callback = before_agent_callback


# --- Main Pipeline Execution ---
async def run_pipeline(update: Update, bot: Bot):
    chat_id = update.effective_chat.id
    status_msg = await bot.send_message(chat_id, "📡 *Archives Hive Activated*\n_Connecting to agents..._", parse_mode="Markdown")

    final_payload = {}
    image_to_cleanup = None
    full_output = ""
    
    tracker_messages = [] 
    last_update_time = 0
    
    msg_content = types.Content(role="user", parts=[types.Part.from_text(text=update.message.text)])
    
    try:
        async for event in runner.run_async(user_id=DATASET_ID, session_id=STATIC_SESSION_ID, new_message=msg_content):
            author = event.author
            if author and author not in ["user", "system"]:
                
                # Extract Text Content Safely
                event_text = ""
                if event.content and event.content.parts:
                    event_text = "".join([p.text for p in event.content.parts if hasattr(p, 'text') and p.text]).strip()

                func_calls = event.get_function_calls()
                func_responses = event.get_function_responses()
                
                # Format Raw Output
                raw_detail = ""
                if func_calls:
                    tools = ", ".join([f"{fc.name}({fc.args})" for fc in func_calls])
                    raw_detail = f"🛠️ Calling: {tools}"
                elif func_responses:
                    raw_detail = "📥 Data Received"
                elif event_text:
                    if author == "orchestrator":
                        full_output += event_text
                    raw_detail = event_text
                
                if not raw_detail and event.is_final_response():
                    raw_detail = "(Finished)"
                
                if raw_detail:
                    tracker_messages.append(f"• {author.upper()}:\n{raw_detail}")

                # Format & Throttled Edit
                now = time.time()
                if now - last_update_time >= 1.2:
                    display_text = "\n\n".join(tracker_messages)
                    if len(display_text) > 3500:
                        display_text = "...\n" + display_text[-3500:]
                        
                    full_text = f"📡 Archives Hive Activity\n\n{display_text}"
                    
                    try:
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=status_msg.message_id,
                            text=full_text,
                            parse_mode=None
                        )
                        last_update_time = now
                    except: pass

            # Persistence tracking (Synchronous retrieval fix)
            try:
                current_session = session_service.get_session(
                    app_name="igbo-archives-agent-hq", 
                    user_id=DATASET_ID, 
                    session_id=STATIC_SESSION_ID
                )
                if current_session:
                    image_to_cleanup = current_session.state.get("image_path")
                    final_payload = current_session.state.get("archive", {}) 
            except Exception as e:
                pass

    except Exception as e:
        await bot.send_message(chat_id, f"⚠️ **Hive Error:** {str(e)}")
    finally:
        try: await bot.delete_message(chat_id, status_msg.message_id)
        except: pass
        
        if final_payload:
            title = final_payload.get("title", "Untitled")
            slug = final_payload.get("slug", "pending")
            link = f"https://igboarchives.ng/archives/{slug}/"
            
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ **Archiving Complete**\n\n**Title**: {title}\n🔗 [View on Platform]({link})",
                parse_mode="Markdown"
            )
        elif full_output:
            await bot.send_message(chat_id, full_output)
        else:
            await bot.send_message(chat_id, "🏁 **Pipeline Finished** (No records processed)")

        if image_to_cleanup and os.path.exists(image_to_cleanup):
            try: os.remove(image_to_cleanup)
            except: pass


# --- Webhook Mode (Cloud Run) ---
app = FastAPI()
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
tg_bot = Bot(token=bot_token) if bot_token else None

@app.post("/webhook")
async def telegram_webhook(request: Request):
    payload = await request.json()
    
    if os.getenv("K_SERVICE"):
        # Cloud Run: push to Cloud Tasks (RESTORED)
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
    """The Cloud Tasks execution endpoint (RESTORED)"""
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
        import uvicorn
        port = int(os.environ.get("PORT", 8080))
        print(f"Starting server on port {port} (Webhook Mode)")
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        if bot_token:
            from telegram.request import HTTPXRequest
            print("Starting Telegram Bot (Polling Mode) for local dev...")
            request = HTTPXRequest(connect_timeout=30, read_timeout=30)
            tg_app = ApplicationBuilder().token(bot_token).request(request).build()
            tg_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_polling))
            tg_app.run_polling()
        else:
            print("CRITICAL: TELEGRAM_BOT_TOKEN not found.")