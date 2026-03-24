import os
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from agents.orchestrator.agent import orchestrator
from agents.schema import get_initial_state
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

load_dotenv()

# --- Master Configuration ---
NEON_URL = os.getenv("NEON_DATABASE_URL")
if not NEON_URL:
    raise ValueError("NEON_DATABASE_URL required for autonomous persistence.")

session_service = DatabaseSessionService(db_url=NEON_URL)

runner = Runner(
    app_name="igbo-archives-agent-hq",
    agent=orchestrator,
    session_service=session_service
)

# --- Dynamic UI (Telegram Streaming) ---
STATUS_MAP = {
    "fetcher_taxonomist": ("⚙️ Fetching Metadata", "✅ Data Fetched"),
    "vision_analyst": ("👁️ Visual Analysis", "🖼️ Visual Report Done"),
    "writer": ("✍️ Drafting Record", "📄 Draft Written"),
    "historical_validator": ("⚖️ Validating Draft", "⚖️ Record Approved"),
    "publisher": ("🚀 Final Publishing", "✨ Archive Published!")
}

async def update_telegram_status(update: Update, context: ContextTypes.DEFAULT_TYPE, msg_id: int, state: dict):
    last_ui_update = state.get("last_ui_update", 0)
    current_time = time.time()
    if current_time - last_ui_update < 3: return

    lines = []
    active = state.get("active_agent", "")
    completed = state.get("completed_agents", [])
    
    for agent, (in_prog, done) in STATUS_MAP.items():
        if agent in completed: lines.append(f"[✅] {done}")
        elif agent == active: lines.append(f"[..] {in_prog}...")
        else: lines.append(f"[  ] {in_prog}")
            
    try:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=msg_id,
            text=f"⚙️ **System: {state.get('dataset_id', 'HF-Archive')}**\nStatus: Processing Row {state.get('current_index', 0)}\n\n" + "\n".join(lines),
            parse_mode="Markdown"
        )
        state["last_ui_update"] = current_time
    except: pass

# --- Callbacks ---
def before_agent_callback(callback_context):
    state = callback_context.state
    state["active_agent"] = callback_context.agent_name
    return None

def after_agent_callback(callback_context):
    state = callback_context.state
    completed = state.get("completed_agents", [])
    if callback_context.agent_name not in completed:
        completed.append(callback_context.agent_name)
    state["completed_agents"] = completed
    state["active_agent"] = ""
    return None

orchestrator.before_agent_callback = before_agent_callback
orchestrator.after_agent_callback = after_agent_callback

# --- Handler ---
async def handle_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dataset_id = "nwokikeonyeka/maa-cambridge-south-eastern-nigeria"
    session_id = f"job_{int(time.time())}"
    status_msg = await update.message.reply_text(f"🚀 **Initializing Archive Pipeline**\nTarget: {dataset_id}")

    initial_state = get_initial_state()
    initial_state["dataset_id"] = dataset_id 
    
    session_service.create_session(
        app_name="igbo-archives-agent-hq",
        user_id=dataset_id,
        session_id=session_id,
        state=initial_state
    )

    image_to_cleanup = None
    final_payload = {}
    try:
        async for event in runner.run_async(user_id=dataset_id, session_id=session_id, new_message=update.message.text):
            session = session_service.get_session("igbo-archives-agent-hq", dataset_id, session_id)
            image_to_cleanup = session.state.get("image_path")
            final_payload = session.state.get("draft_payload", {})
            await update_telegram_status(update, context, status_msg.message_id, session.state)

    except Exception as e:
        await update.message.reply_text(f"⚠️ **Pipeline Aborted:** {str(e)}")
    finally:
        # Final Reveal (Clause 4: Replacing bullet points with summary)
        if final_payload:
            title = final_payload.get("title", "Untitled")
            category = final_payload.get("category_name", "General")
            slug = final_payload.get("slug", "pending")
            link = f"https://igboarchives.ng/archives/{slug}/"
            
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text=f"✅ **Cultural Archiving Complete**\n\n**Title**: {title}\n**Category**: {category}\n\n🔗 **View on Platform**: {link}",
                parse_mode="Markdown"
            )

        if image_to_cleanup and os.path.exists(image_to_cleanup):
            try: os.remove(image_to_cleanup)
            except: pass

if __name__ == "__main__":
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if bot_token:
        print("Archiving Hive is ACTIVE.")
        tg_app = ApplicationBuilder().token(bot_token).build()
        tg_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_trigger))
        tg_app.run_polling()
    else:
        print("CRITICAL: TELEGRAM_BOT_TOKEN not found.")
