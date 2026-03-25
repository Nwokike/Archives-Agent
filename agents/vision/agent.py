import os
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

# Agent B: The Vision Analyst (Quarantined)
vision_model = LiteLlm(
    model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
    api_key=os.getenv("GROQ_API_KEY")
)

# Note: This agent MUST NOT be passed the original HF description to ensure unbiased visual reporting.
vision = Agent(
    name="vision_analyst",
    model=vision_model,
    description="Agent B: A quarantined visual analyst specialized in meticulous object identification.",
    instruction="""
    Analyze the provided image meticulously. 
    You are FORBIDDEN from relying on external text descriptions.
    Your ONLY input is the 'image_path' and the cultural metadata from the state. 
    IF there is an 'hf_description' in the state, IGNORE IT COMPLETELY to avoid bias.
    Generate a visual-only report. Return 'null' for any uncertain fields; NEVER invent data.
    """
)
