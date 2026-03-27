import os
from google.adk.agents import Agent, Context, SequentialAgent
from google.adk.models.lite_llm import LiteLlm

# --- The Pipeline (Sequential Steps) ---
from .fetcher.agent import data_fetcher, taxonomy_mapper
from .vision.agent import vision
from .synthesis.agent import synthesis_loop
from .publisher.agent import publisher

archive_pipeline = SequentialAgent(
    name="execute_archive_pipeline",
    sub_agents=[data_fetcher, taxonomy_mapper, vision, synthesis_loop, publisher],
    description="The Master Archiving Pipeline. Executes extraction, taxonomy injection, analysis, synthesis, and publication."
)

TARGET_DATASET = os.getenv("TARGET_DATASET", "nwokikeonyeka/maa-cambridge-south-eastern-nigeria")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# --- The Orchestrator (Root Agent) ---

orchestrator_model = LiteLlm(
    model="groq/moonshotai/kimi-k2-instruct",
    api_key=GROQ_API_KEY,
    # RESILIENCE: Fallback chain of high-capacity Groq models
    fallbacks=["groq/openai/gpt-oss-120b", "groq/meta-llama/llama-3.3-70b-versatile"]
)

def bootstrap_state(callback_context: Context):
    """Ensures critical state variables exist for template substitution (adk web compat)."""
    state = callback_context.state
    if "current_index" not in state:
        state["current_index"] = 0
    if "dataset_id" not in state:
        state["dataset_id"] = TARGET_DATASET

orchestrator = Agent(
    name="orchestrator",
    model=orchestrator_model, 
    description="The root supervisor for the Igbo Archives Autonomous Ingestion System.",
    sub_agents=[archive_pipeline],
    before_agent_callback=bootstrap_state,
    instruction="""
ROLE:
You are the Chief Orchestrator of the Igbo Archives Autonomous Ingestion System.

GOAL:
Listen to the user's command, trigger the `execute_archive_pipeline` tool, and report the final result back to the user.

AVAILABLE DATA:
- Target Dataset: {dataset_id}
- Current Unarchived Index: {current_index} (This is natively available to you from the session state).

STRICT RULES:
1. STATE CHECK: If the user explicitly provides a row index (e.g., "Post row 5"), use it. Otherwise, use the `Current Unarchived Index` ({current_index}).
2. NO AI SPEAK: Do not use flowery language. Keep your responses clinical, professional, and brief.
3. HONEST NULL: Acknowledge missing data gracefully; do not invent details.

TOOL MANDATE:
When the user requests to post or archive, you MUST call your tool `transfer_to_execute_archive_pipeline`. Once the pipeline finishes, summarize the final outcome to the user based on the system state.
"""
)

root_agent = orchestrator