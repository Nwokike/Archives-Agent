import os
from google.adk.agents import Agent, Context
from google.adk.models.lite_llm import LiteLlm

# --- The Pipeline (Sequential Steps) ---
from agents.fetcher.agent import data_fetcher, taxonomy_mapper
from agents.vision.agent import vision
from agents.synthesis.agent import synthesis_loop
from agents.publisher.agent import publisher
from google.adk.agents import SequentialAgent

archive_pipeline = SequentialAgent(
    name="execute_archive_pipeline",
    sub_agents=[data_fetcher, taxonomy_mapper, vision, synthesis_loop, publisher],
    description="The Master Archiving Pipeline. Executes extraction, taxonomy injection, analysis, synthesis, and publication."
)

TARGET_DATASET = os.getenv("TARGET_DATASET", "nwokikeonyeka/maa-cambridge-south-eastern-nigeria")

# --- The Orchestrator (Root Agent) ---

orchestrator_model = LiteLlm(
    model="groq/moonshotai/kimi-k2-instruct-0905",
    api_key=os.getenv("GROQ_API_KEY")
)

def bootstrap_state(callback_context: Context):
    """Ensures critical state variables exist for template substitution (adk web compat)."""
    state = callback_context.state
    if "current_index" not in state:
        state["current_index"] = 0
    if "dataset_id" not in state:
        state["dataset_id"] = os.getenv("TARGET_DATASET", "nwokikeonyeka/maa-cambridge-south-eastern-nigeria")

orchestrator = Agent(
    name="orchestrator",
    model=orchestrator_model, 
    description="The root supervisor for the Igbo Archives Autonomous Ingestion System.",
    sub_agents=[archive_pipeline],
    before_agent_callback=bootstrap_state,
    instruction="""
    You are the Orchestrator of the 'Daily Cultural Archiving' pipeline.
    Your mission is to autonomously process historical data from Hugging Face into the Igbo Archives platform.
    
    NATIVE PERSISTENCE AWARENESS:
    - Target Dataset: {dataset_id}
    - Current Unarchived Index: {current_index}
    
    CRITICAL ROUTING RULES:
    1. STATE CHECK: If the user provides an index, use it. Otherwise, you can use the 'Current Unarchived Index' ({current_index}) which is natively available to you from the session state.
    2. DELEGATION: If the user wants to start archiving or if it's the natural next step, CALL 'transfer_to_execute_archive_pipeline' to start the process for the target row.
    3. COMMUNICATION: Maintain academic neutrality. Avoid conversational filler.
    
    STRICT COMPLIANCE:
    - Honest Null Protocol: Use JSON `null` for missing data.
    - No Hallucinations. No AI Speak. No Em-Dashes.
    """
)

root_agent = orchestrator