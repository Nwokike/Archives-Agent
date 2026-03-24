import os
from google_adk import LLMAgent
from google_adk.media import Image
from agents.schema import PipelineState

# --- Vision Analyst Agent (Agent B) ---
class VisionAgent(LLMAgent):
    """
    Agent B: Sequential Worker (Quarantined).
    Analyzes the image without seeing metadata to ensure unbiased visual reporting.
    """
    model = "gemini-2.5-flash"
    
    system_prompt = """
    You are a meticulous Visual Anthropologist. 
    Task: Generate a detailed visual-only report for the provided historical image from South Eastern Nigeria.
    
    Constraints:
    - Describe only what is visible in the pixels.
    - Focus on: Subjects, Clothing/Wrappers, Objects, Environment, and Composition.
    - DO NOT guess identities or historical data not visible.
    - Format: Semantic bullet points.
    """

    async def run(self, state: PipelineState):
        if not state.image_path or not os.path.exists(state.image_path):
            state.status = "error: image not found for vision analysis"
            return False
            
        print("👁️ Vision: Analyzing image (Quarantined)...")
        image = Image.from_file(state.image_path)
        
        response = await self.generate_content([
            "Analyze this historical document image visually. Provide a meticulous report.",
            image
        ])
        
        state.vision_report = response.text
        print("✅ Vision: Analysis complete.")
        return True
