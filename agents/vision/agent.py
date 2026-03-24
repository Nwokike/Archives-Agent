import os
from google_adk import LLMAgent
from google_adk.media import Image
from agents.schema import PipelineState

class VisionAgent(LLMAgent):
    """Agent B: Quarantined Visual Analyst."""
    model = "gemini-2.5-flash"
    system_prompt = "Generate a meticulous visual-only report for the provided historical image."

    async def run(self, state: PipelineState):
        if not state.image_path: return False
        image = Image.from_file(state.image_path)
        response = await self.generate_content(["Analyze this visually.", image])
        state.vision_report = response.text
        return True
