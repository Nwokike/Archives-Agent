import os
from google_adk import SequentialAgent
from mcp import call_tool as mcp_call_tool
from agents.schema import PipelineState

# --- Publisher Agent (Agent E) ---
class PublisherAgent(SequentialAgent):
    """Agent E: Final Sequential Worker."""
    model = "gemini-2.5-flash-lite"
    
    async def step_publish_archive(self, state: PipelineState):
        if not state.draft_payload: return False
        try:
            payload = state.draft_payload.copy()
            payload["image"] = f"file://{state.image_path}"
            resp = await mcp_call_tool("igbo-archives", "create_archives", {"body": payload})
            if resp.get("status") == "success":
                state.status = "SUCCESS"
                return True
            return False
        except: return False

    async def step_cleanup(self, state: PipelineState):
        if state.image_path and os.path.exists(state.image_path):
            os.remove(state.image_path)
        return True
