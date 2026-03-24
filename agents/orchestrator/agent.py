from google.adk.agents import Agent, SequentialAgent
from google.adk.tools import AgentTool
from agents.fetcher.agent import fetcher
from agents.vision.agent import vision
from agents.synthesis.agent import synthesis_loop
from agents.publisher.agent import publisher

# --- The Pipeline Tool (Nested Sequence) ---
# Order: Fetcher -> Vision Analyst -> Synthesis Loop (Writer/Critic) -> Publisher
# NOTE: All sub_agents must be Agent instances, not functions.
archive_pipeline = SequentialAgent(
    name="execute_archive_pipeline",
    sub_agents=[fetcher, vision, synthesis_loop, publisher],
    description="The Master Archiving Pipeline. Executes extraction, analysis, synthesis, and publication."
)

# --- The Orchestrator (Root Agent) ---
orchestrator = Agent(
    name="orchestrator",
    model="gemini-2.5-flash-lite", 
    description="The root manager for the Igbo Archives Autonomous Ingestion System.",
    instruction="""
    You are the supervisor of the 'Daily Cultural Archiving' pipeline.
    Your mission is to autonomously process historical data from Hugging Face into the Igbo Archives platform.
    
    PRIMARY TOOL: execute_archive_pipeline
    
    STRICT COMPLIANCE:
    - No Hallucinations. No AI Speak. No Em-Dashes.
    - Honest Null Protocol: use 'null' for missing data.
    """,
    tools=[AgentTool(archive_pipeline)]
)

root_agent = orchestrator
