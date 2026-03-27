import os
import PIL.Image
from google.genai import types
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

# --- Configuration ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# --- Model ---
vision_model = LiteLlm(
    model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
    api_key=GROQ_API_KEY,
)

# --- Multimodal Injection ---
async def inject_image(callback_context) -> types.Content:
    """Reads the downloaded image from disk and injects it into the LLM context."""
    ctx = callback_context
    image_path = ctx.state.get("image_path")
    
    if not image_path or not os.path.exists(image_path):
        raise RuntimeError(f"FATAL: Vision Agent aborted. Valid image not found at path: {image_path}")
        
    try:
        img = PIL.Image.open(image_path)
        return types.Content(
            role="user", 
            parts=[
                types.Part.from_text(text="Perform your visual analysis on this image according to your system instructions."),
                types.Part(img)
            ]
        )
    except Exception as e:
        raise RuntimeError(f"FATAL: Vision Agent aborted. Could not process image file: {str(e)}")


async def save_vision_to_state(ctx, agent_response: types.Content) -> types.Content:
    """
    Automatically saves the raw vision report to the session state 
    before it is returned to the Orchestrator.
    """
    if agent_response and agent_response.parts:
        # Extract the pure text from the vision model's response
        text = "".join([p.text for p in agent_response.parts if hasattr(p, 'text') and p.text])
        ctx.state["vision_report"] = text
        
    return agent_response
    
# --- Agent B: The Vision Analyst (Quarantined) ---
vision = Agent(
    name="vision_analyst",
    model=vision_model,
    description="Agent B: A quarantined visual analyst specialized in meticulous object identification.",
    before_agent_callback=inject_image,
    after_agent_callback=save_vision_to_state,
    instruction="""
ROLE:
You are an Elite Cultural Heritage Visual Analyst.

GOAL:
Meticulously examine the provided image and extract a purely visual, unbiased cultural report.

STRICT RULES:
1. NO HALLUCINATION: DO NOT invent historical context, names, locations, or events that are not explicitly visible in the photograph.
2. TONE: Output your analysis as a highly detailed, clinical, and objective observational report.
"""
)
