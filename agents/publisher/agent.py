import os
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import ToolContext
from agents.mcp_client import call_mcp_tool

# Tool: Final Publication to Igbo Archives
async def create_archives_submission(payload: dict, image_path: str, tool_context: ToolContext, critic_status: str = "") -> dict:
    """Publishes the validated archival record to the central platform. MUST include critic_status."""
    if "APPROVED" not in critic_status:
        return {"status": "FAILURE", "error": f"FATAL: Critic did not approve this payload. Received status: {critic_status}"}
    try:
        # Prepare the body based on the REST API documentation
        body = payload.copy()
        if image_path:
            body["image"] = f"file://{image_path}"
        
        # Call the MCP tool 'create_archives'
        response = await call_mcp_tool("igbo-archives", "create_archives", {"body": body})
        
        # --- AUTONOMOUS PERSISTENCE: Save progress for tomorrow ---
        # Increment index in shared memory so Orchestrator knows where to pick up
        tool_context.state["current_index"] = tool_context.state.get("current_index", 0) + 1
        
        return {"status": "SUCCESS", "message": "Archived successfully.", "id": response.get("id")}
    except Exception as e:
        return {"status": "FAILURE", "error": str(e)}

# Publisher Agent
publisher_model = LiteLlm(
    model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
    api_key=os.getenv("GROQ_API_KEY")
)

publisher = Agent(
    name="publisher",
    model=publisher_model,
    description="Agent E: The final record publisher.",
    tools=[create_archives_submission],
    instruction="""
    3. COMMIT: If the draft is 'APPROVED', call the `create_archives_submission` tool. You MUST pass the critic's output exactly to the `critic_status` argument.
    4. ABORT: If the 'APPROVED' status is missing or the Validator has feedback, do NOT call the tool and return a failure message.
    
    If failed, report the error exactly.
    """
)
