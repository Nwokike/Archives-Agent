import json
from google_adk import LLMAgent, LoopAgent, Node
from ..schema import PipelineState

class WriterAgent(LLMAgent):
    model = "gemini-3-flash"
    system_prompt = "Synthesize a draft JSON payload."
    async def run(self, state: PipelineState):
        prompt = f"Metadata: {json.dumps(state.hf_metadata)}\nVision: {state.vision_report}"
        response = await self.generate_content(prompt)
        try:
            state.draft_payload = json.loads(response.text)
            return True
        except: return False

class CriticAgent(LLMAgent):
    model = "gemini-3.1-flash-lite"
    system_prompt = "Validate draft. Reply APPROVED or corrections."
    async def run(self, state: PipelineState):
        response = await self.generate_content(f"Draft: {json.dumps(state.draft_payload)}")
        return "APPROVED" in response.text.upper()

class SynthesisLoop(LoopAgent):
    nodes = [Node(WriterAgent(), id="writer"), Node(CriticAgent(), id="critic")]
    max_iterations = 3
    def should_continue(self, state: PipelineState):
        return "APPROVED" not in state.status and state.loop_count < self.max_iterations
