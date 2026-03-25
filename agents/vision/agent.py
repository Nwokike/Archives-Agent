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
    # RESILIENCE: No other multimodal Groq model available for fallback
    fallbacks=[]
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
                types.Part(text="Perform your visual analysis on this image according to your system instructions."),
                types.Part.from_image(img)
            ]
        )
    except Exception as e:
        raise RuntimeError(f"FATAL: Vision Agent aborted. Could not process image file: {str(e)}")

# --- Agent B: The Vision Analyst (Quarantined) ---
vision = Agent(
    name="vision_analyst",
    model=vision_model,
    description="Agent B: A quarantined visual analyst specialized in meticulous object identification.",
    before_agent_callback=inject_image,
    instruction="""
ROLE:
You are an Elite Cultural Heritage Visual Analyst.

GOAL:
Meticulously examine the provided archival image and extract a purely visual, unbiased cultural report.

AVAILABLE DATA:
- The physical image has been injected directly into your prompt context.
- You do NOT have the historical Hugging Face description. This is intentional to prevent bias.

STRICT RULES:
1. OBSERVATION ONLY: Describe physical objects, clothing (e.g., Uli patterns, textiles, headpieces), background architecture, and people meticulously based strictly on what your eyes see in the image.
2. NO HALLUCINATION: DO NOT invent historical context, names, locations, or events that are not explicitly visible in the photograph.
3. QUARANTINE PROTOCOL: If any text labeled 'hf_description' or 'raw_metadata' accidentally leaks into your context from a previous agent, you MUST ignore it completely. Base your output entirely on the pixels.
4. TONE: Output your analysis as a highly detailed, clinical, and objective observational report.
"""
)
