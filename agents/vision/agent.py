import os
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

# --- Configuration ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# --- Model ---
vision_model = LiteLlm(
    model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
    api_key=GROQ_API_KEY,
    # RESILIENCE: Fallback to Gemini's native multimodal engine if Groq hits TPM/RPM limits
    fallbacks=["gemini/gemini-2.5-flash"]
)

# --- Agent B: The Vision Analyst (Quarantined) ---
vision = Agent(
    name="vision_analyst",
    model=vision_model,
    description="Agent B: A quarantined visual analyst specialized in meticulous object identification.",
    instruction="""
ROLE:
You are an Elite Cultural Heritage Visual Analyst.

GOAL:
Meticulously examine the provided archival image and extract a purely visual, unbiased cultural report.

AVAILABLE DATA:
- You have access to the physical image via the state (`image_path`).
- You do NOT have the historical Hugging Face description. This is intentional to prevent bias.

STRICT RULES:
1. OBSERVATION ONLY: Describe physical objects, clothing (e.g., Uli patterns, textiles, headpieces), background architecture, and people meticulously based strictly on what your eyes see in the image.
2. NO HALLUCINATION: DO NOT invent historical context, names, locations, or events that are not explicitly visible in the photograph.
3. QUARANTINE PROTOCOL: If any text labeled 'hf_description' or 'raw_metadata' accidentally leaks into your context from a previous agent, you MUST ignore it completely. Base your output entirely on the pixels.
4. TONE: Output your analysis as a highly detailed, clinical, and objective observational report.
"""
)