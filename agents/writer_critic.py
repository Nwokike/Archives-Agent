import json
from google_adk import LLMAgent, LoopAgent, Node
from agents.schema import PipelineState

# --- Writer Agent (Agent C) ---
class WriterAgent(LLMAgent):
    """
    Agent C: Synthesis Loop Node 1.
    Merges HF Metadata, Vision Report, and MCP Taxonomies into a draft JSON.
    """
    model = "gemini-3-flash"
    
    system_prompt = """
    You are the Lead Cultural Archivist. Synthesize a draft JSON payload.
    Match HF 'photographer' with MCP Author ID if possible.
    """

    async def run(self, state: PipelineState):
        prompt = f"""
        HF Metadata: {json.dumps(state.hf_metadata)}
        Vision Report: {state.vision_report}
        Live Taxonomies: {json.dumps(state.taxonomies)}
        """
        response = await self.generate_content(prompt)
        try:
            state.draft_payload = json.loads(response.text)
            return True
        except:
            return False

# --- Critic Agent (Agent D) ---
class CriticAgent(LLMAgent):
    """Agent D: Loop Node 2 (Evaluator)."""
    model = "gemini-3.1-flash-lite"
    system_prompt = "Validate the Writer's draft entry against ground truth. Reply APPROVED or corrections."

    async def run(self, state: PipelineState):
        prompt = f"Draft: {json.dumps(state.draft_payload)}\nGround Truth: {json.dumps(state.taxonomies)}"
        response = await self.generate_content(prompt)
        if "APPROVED" in response.text.upper():
            return True
        else:
            state.corrections = response.text
            return False

class SynthesisLoop(LoopAgent):
    """Max 3 iterations of Write/Critic refinement."""
    nodes = [
        Node(WriterAgent(), id="writer"),
        Node(CriticAgent(), id="critic")
    ]
    max_iterations = 3
    
    def should_continue(self, state: PipelineState):
        return "APPROVED" not in state.status and state.loop_count < self.max_iterations
